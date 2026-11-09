"""Reglas de negocio de nómina: cálculo, ajustes y cierre de periodos."""
import logging
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from accounts.services import audit
from attendance.models import Attendance
from workers.models import PAY_DAILY
from workers.services import rate_for

from .models import STATUS_CLOSED, PayrollLine, PayrollPeriod

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


@transaction.atomic
def close_period(period: PayrollPeriod, user) -> PayrollPeriod:
    """Cierra el periodo: queda inmutable. Reabrir no está soportado a propósito."""
    _ensure_open(period)
    period.status = STATUS_CLOSED
    period.closed_at = timezone.now()
    period.closed_by = user
    period.save()
    audit(user, "cerrar", "PayrollPeriod", period.pk, str(period))
    logger.info("Periodo cerrado: periodo=%s usuario=%s", period.pk, user)
    return period
