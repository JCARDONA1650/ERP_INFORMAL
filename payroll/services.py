"""Reglas de negocio de nómina: cálculo, ajustes y cierre de periodos."""
import logging
from collections import defaultdict
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from accounts.services import audit
from attendance.models import Attendance
from workers.models import PAY_DAILY
from workers.services import rate_for

from .models import STATUS_CLOSED, STATUS_OPEN, PayrollLine, PayrollPeriod

logger = logging.getLogger(__name__)
CENTS = Decimal("0.01")


class PayrollError(Exception):
    """Operación de nómina no permitida (p. ej. periodo cerrado)."""


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def _ensure_open(period: PayrollPeriod):
    if not period.is_open:
        raise PayrollError("El periodo está cerrado y no admite cambios.")


@transaction.atomic
def recalculate_period(period: PayrollPeriod, user=None) -> PayrollPeriod:
    """Recalcula las líneas del periodo desde la asistencia.

    - Por hora: suma día a día minutos * tarifa vigente ese día (soporta cambios
      de tarifa a mitad de periodo).
    - Por día (supervisores): días con horas/ingreso registrados * valor diario.
    - Se conservan los ajustes existentes; una línea sin asistencia pero con
      ajuste se mantiene en cero base para no perder el ajuste.
    """
    _ensure_open(period)

    qs = Attendance.objects.select_related("employee", "project").filter(
        date__range=(period.start_date, period.end_date)
    )
    if period.project_id:
        qs = qs.filter(project=period.project)

    minutes = defaultdict(int)
    days = defaultdict(set)
    amounts = defaultdict(lambda: Decimal("0"))
    employees = {}

    for att in qs:
        emp = att.employee
        worked = att.worked_minutes()
        if worked <= 0 and not att.check_in:
            continue
        employees[emp.pk] = emp
        minutes[emp.pk] += worked
        if att.date not in days[emp.pk]:
            days[emp.pk].add(att.date)
            if emp.pay_type == PAY_DAILY:
                amounts[emp.pk] += emp.daily_rate
        if emp.pay_type != PAY_DAILY:
            amounts[emp.pk] += Decimal(worked) / Decimal(60) * rate_for(emp, att.date)

    existing = {line.employee_id: line for line in period.lines.select_related("employee")}

    for emp_id, line in existing.items():
        if emp_id not in employees:
            if line.adjustment:
                line.minutes, line.days, line.base_amount = 0, 0, Decimal("0.00")
                line.save()
            else:
                line.delete()

    for emp_id, emp in employees.items():
        line = existing.get(emp_id) or PayrollLine(period=period, employee=emp)
        line.minutes = minutes[emp_id]
        line.days = len(days[emp_id])
        line.hourly_rate = rate_for(emp, period.end_date)
        line.currency = emp.currency or "USD"
        line.base_amount = _money(amounts[emp_id])
        line.save()

    audit(user, "recalcular", "PayrollPeriod", period.pk, f"{len(employees)} trabajadores")
    logger.info("Nómina recalculada: periodo=%s trabajadores=%s", period.pk, len(employees))
    return period


@transaction.atomic
def set_adjustment(line: PayrollLine, amount, reason: str, user=None) -> PayrollLine:
    """Aplica un ajuste (+/-) a una línea. Exige motivo y periodo abierto."""
    _ensure_open(line.period)
    amount = Decimal(str(amount))
    if amount != 0 and not reason.strip():
        raise PayrollError("Todo ajuste requiere un motivo.")
    line.adjustment = _money(amount)
    line.notes = reason.strip()
    line.save()
    audit(user, "ajuste", "PayrollLine", line.pk, f"{line.adjustment}: {line.notes}")
    return line


def _amounts_by_project(period: PayrollPeriod) -> dict:
    """{empleado_id: {proyecto_id: monto}} según la asistencia del periodo (mismas reglas que el cálculo)."""
    qs = Attendance.objects.select_related("employee").filter(date__range=(period.start_date, period.end_date))
    if period.project_id:
        qs = qs.filter(project=period.project)
    result: dict = defaultdict(lambda: defaultdict(lambda: Decimal("0")))
    seen_days = defaultdict(set)
    for att in qs.order_by("date", "project_id"):
        emp = att.employee
        worked = att.worked_minutes()
        if worked <= 0 and not att.check_in:
            continue
        if emp.pay_type == PAY_DAILY:
            if att.date not in seen_days[emp.pk]:
                seen_days[emp.pk].add(att.date)
                result[emp.pk][att.project_id] += emp.daily_rate
        else:
            result[emp.pk][att.project_id] += Decimal(worked) / Decimal(60) * rate_for(emp, att.date)
    return result


def _split_cents(total: Decimal, weights: dict) -> dict:
    """Reparte `total` (centavos exactos) proporcionalmente a `weights`; la suma siempre es `total`."""
    keys = sorted(weights)
    weight_sum = sum(weights.values())
    if weight_sum <= 0:
        return {keys[0]: total}
    raw = {k: total * weights[k] / weight_sum for k in keys}
    floors = {k: raw[k].quantize(CENTS, rounding=ROUND_FLOOR) for k in keys}
    leftover = int((total - sum(floors.values())) / CENTS)
    for k in sorted(keys, key=lambda k: raw[k] - floors[k], reverse=True)[:leftover]:
        floors[k] += CENTS
    return floors


def payroll_by_project(period: PayrollPeriod) -> dict:
    """{(proyecto_id, moneda): total} que el periodo cerrado aporta como gasto de cada proyecto.
    El base de cada trabajador se reparte según la asistencia; su ajuste (+/-) va al proyecto
    donde generó más. Suma exactamente el total de las líneas."""
    by_emp = _amounts_by_project(period)
    totals: dict = defaultdict(lambda: Decimal("0"))
    for line in period.lines.select_related("employee"):
        weights = dict(by_emp.get(line.employee_id, {}))
        if not weights:
            # Línea sin asistencia (solo ajuste): proyecto del periodo o el primero asignado al trabajador.
            fallback = period.project_id or (
                line.employee.projects.order_by("name").values_list("pk", flat=True).first()
            )
            if fallback is None:
                raise PayrollError(
                    f"{line.employee.full_name} no tiene asistencia ni proyecto asignado: "
                    "no se puede cargar su pago a ningún proyecto."
                )
            weights = {fallback: Decimal("1")}
        parts = _split_cents(line.base_amount, weights)
        main = max(weights, key=lambda k: (weights[k], -k))
        parts[main] = parts.get(main, Decimal("0")) + line.adjustment
        for project_id, amount in parts.items():
            totals[(project_id, line.currency)] += amount
    return totals


def _post_payroll_expenses(period: PayrollPeriod, user) -> int:
    """Registra en Finanzas un gasto de categoría Nómina por proyecto y moneda (fecha = fin del periodo)."""
    from finance.models import ProjectExpense
    from finance.services import record_movement

    created = 0
    for (project_id, currency), amount in sorted(payroll_by_project(period).items()):
        if amount <= 0:
            continue
        record_movement(
            ProjectExpense, user, project_id=project_id, date=period.end_date, amount=_money(amount),
            currency=currency, category="payroll", payroll_period=period,
            description=f"Nómina {period.start_date:%d/%m/%Y} – {period.end_date:%d/%m/%Y}",
        )
        created += 1
    return created


@transaction.atomic
def close_period(period: PayrollPeriod, user) -> PayrollPeriod:
    """Cierra el periodo (queda inmutable) y registra el gasto de nómina en Finanzas por proyecto.
    Solo el Administrador puede reabrirlo (ver `reopen_period`)."""
    _ensure_open(period)
    from finance.models import ProjectExpense

    ProjectExpense.objects.filter(payroll_period=period).delete()  # por si quedó algo de un cierre anterior
    posted = _post_payroll_expenses(period, user)
    period.status = STATUS_CLOSED
    period.closed_at = timezone.now()
    period.closed_by = user
    period.save()
    audit(user, "cerrar", "PayrollPeriod", period.pk, f"{period} · {posted} gasto(s) en Finanzas")
    logger.info("Periodo cerrado: periodo=%s usuario=%s gastos=%s", period.pk, user, posted)
    return period


@transaction.atomic
def reopen_period(period: PayrollPeriod, user) -> PayrollPeriod:
    """Reabre un periodo cerrado por error: elimina los gastos que generó el cierre (quedan en la
    bitácora) para que, al cerrar de nuevo, se registren con las cifras corregidas."""
    if period.is_open:
        raise PayrollError("El periodo ya está abierto.")
    from finance.models import ProjectExpense

    removed = list(ProjectExpense.objects.filter(payroll_period=period).values_list("project_id", "currency", "amount"))
    ProjectExpense.objects.filter(payroll_period=period).delete()
    period.status = STATUS_OPEN
    period.closed_at = None
    period.closed_by = None
    period.save()
    detail = "; ".join(f"proyecto {p} {c} {a}" for p, c, a in removed) or "sin gastos"
    audit(user, "reabrir", "PayrollPeriod", period.pk, f"{period} · gastos eliminados: {detail}")
    logger.warning("Periodo reabierto: periodo=%s usuario=%s gastos_eliminados=%s", period.pk, user, len(removed))
    return period
