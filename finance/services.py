"""Resumen financiero por proyecto. Las monedas NO se convierten: se totaliza por moneda."""
from decimal import Decimal

from django.db.models import Sum

from .models import ProjectExpense, ProjectIncome

ZERO = Decimal("0.00")
CENTS = Decimal("0.01")


def _cents(value) -> Decimal:
    """Normaliza a 2 decimales (SQLite devuelve la suma sin ellos; PostgreSQL sí)."""
    return Decimal(value).quantize(CENTS)


def _totals(qs, date_from=None, date_to=None) -> dict:
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return {
        row["currency"]: _cents(row["total"])
        for row in qs.values("currency").annotate(total=Sum("amount"))
    }


def project_summary(project, date_from=None, date_to=None) -> dict:
    """Ingresos, gastos y balance por moneda (2 consultas agregadas, sin N+1)."""
    incomes = _totals(ProjectIncome.objects.filter(project=project), date_from, date_to)
    expenses = _totals(ProjectExpense.objects.filter(project=project), date_from, date_to)
    balance = {
        cur: incomes.get(cur, ZERO) - expenses.get(cur, ZERO)
        for cur in set(incomes) | set(expenses)
    }
    contract = project.contract_value
    cur = project.contract_currency
    billed_pct = (
        (incomes.get(cur, ZERO) / contract * 100).quantize(Decimal("0.1"))
        if contract > 0 else None
    )
    return {
        "incomes": incomes,
        "expenses": expenses,
        "balance": balance,
        "contract_value": contract,
        "contract_currency": cur,
        "billed_pct": billed_pct,
    }


def expenses_by_category(project, date_from=None, date_to=None) -> dict:
    qs = ProjectExpense.objects.filter(project=project)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return {
        (row["category"], row["currency"]): _cents(row["total"])
        for row in qs.values("category", "currency").annotate(total=Sum("amount"))
    }


# ───────────────── Vista global / por proyecto con serie temporal ─────────────────
import datetime as _dt  # noqa: E402

from django.db.models.functions import TruncDay, TruncMonth, TruncWeek  # noqa: E402

GROUPS = {"day": TruncDay, "week": TruncWeek, "month": TruncMonth}
MAX_FILLED_POINTS = 1000


def _scoped(model, project, date_from, date_to):
    qs = model.objects.all()
    if project is not None:
        qs = qs.filter(project=project)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs


def _next_period(day, group):
    if group == "day":
        return day + _dt.timedelta(days=1)
    if group == "week":
        return day + _dt.timedelta(days=7)
    return (day.replace(day=28) + _dt.timedelta(days=4)).replace(day=1)  # primer día del mes siguiente


def default_group(start, end) -> str:
    """Agrupación según el largo del rango: día (≤ 31 días), semana (≤ 180) o mes."""
    if not start or not end:
        return "day"
    span = (end - start).days
    return "day" if span <= 31 else "week" if span <= 180 else "month"


def finance_series(project, date_from, date_to, group, currency) -> list[dict]:
    """Serie por periodo en una moneda: ingresos, gastos, neto y balance acumulado del rango."""
    trunc = GROUPS[group]
    flows = {}
    for kind, model in (("income", ProjectIncome), ("expense", ProjectExpense)):
        rows = (
            _scoped(model, project, date_from, date_to).filter(currency=currency)
            .annotate(period=trunc("date")).values("period").annotate(total=Sum("amount"))
        )
        for row in rows:
            flows.setdefault(row["period"], {"income": ZERO, "expense": ZERO})[kind] = _cents(row["total"])
    if not flows:
        return []

    periods = sorted(flows)
    filled, cursor = [], periods[0]
    while cursor <= periods[-1] and len(filled) <= MAX_FILLED_POINTS:
        filled.append(cursor)
        cursor = _next_period(cursor, group)
    if cursor <= periods[-1]:  # rango enorme: se omiten los periodos sin movimientos
        filled = periods

    points, running = [], ZERO
    for period in filled:
        income = flows.get(period, {}).get("income", ZERO)
        expense = flows.get(period, {}).get("expense", ZERO)
        running += income - expense
        points.append({
            "period": period.isoformat(), "income": str(income), "expense": str(expense),
            "net": str(income - expense), "cumulative": str(running),
        })
    return points


def finance_overview(project=None, date_from=None, date_to=None, group=None, currency=None) -> dict:
    """Totales, detalle por proyecto, gastos por categoría y serie temporal.
    `project=None` es el registro global de todos los proyectos. Las monedas no se convierten."""
    from projects.models import Project

    incomes = _scoped(ProjectIncome, project, date_from, date_to)
    expenses = _scoped(ProjectExpense, project, date_from, date_to)

    def by_project(qs):
        out = {}
        for row in qs.values("project_id", "currency").annotate(total=Sum("amount")):
            out.setdefault(row["project_id"], {})[row["currency"]] = _cents(row["total"])
        return out

    inc, exp = by_project(incomes), by_project(expenses)
    projects = Project.objects.all() if project is None else Project.objects.filter(pk=project.pk)
    rows, tot_inc, tot_exp = [], {}, {}
    for p in projects.order_by("name"):
        pi, pe = inc.get(p.pk, {}), exp.get(p.pk, {})
        for cur, v in pi.items():
            tot_inc[cur] = tot_inc.get(cur, ZERO) + v
        for cur, v in pe.items():
            tot_exp[cur] = tot_exp.get(cur, ZERO) + v
        billed = (
            (pi.get(p.contract_currency, ZERO) / p.contract_value * 100).quantize(Decimal("0.1"))
            if p.contract_value > 0 else None
        )
        rows.append({
            "project": {"id": p.pk, "name": p.name, "active": p.active},
            "contract": {"value": str(p.contract_value), "currency": p.contract_currency,
                         "billed_pct": None if billed is None else str(billed)},
            "incomes": {c: str(v) for c, v in pi.items()},
            "expenses": {c: str(v) for c, v in pe.items()},
            "balance": {c: str(pi.get(c, ZERO) - pe.get(c, ZERO)) for c in set(pi) | set(pe)},
        })

    currencies = sorted(set(tot_inc) | set(tot_exp))
    chosen = currency if currency in currencies else ("USD" if "USD" in currencies else (currencies[0] if currencies else None))
    first = [d for d in (expenses.order_by("date").values_list("date", flat=True).first(),
                         incomes.order_by("date").values_list("date", flat=True).first()) if d]
    last = [d for d in (expenses.order_by("-date").values_list("date", flat=True).first(),
                        incomes.order_by("-date").values_list("date", flat=True).first()) if d]
    start, end = date_from or (min(first) if first else None), date_to or (max(last) if last else None)
    group = group if group in GROUPS else default_group(start, end)

    categories = {
        (r["category"], r["currency"]): _cents(r["total"])
        for r in expenses.values("category", "currency").annotate(total=Sum("amount"))
    }
    return {
        "scope": None if project is None else {"id": project.pk, "name": project.name},
        "currencies": currencies,
        "totals": {
            "incomes": {c: str(v) for c, v in tot_inc.items()},
            "expenses": {c: str(v) for c, v in tot_exp.items()},
            "balance": {c: str(tot_inc.get(c, ZERO) - tot_exp.get(c, ZERO)) for c in currencies},
        },
        "projects": rows,
        "expenses_by_category": [
            {"category": cat, "currency": cur, "total": str(total)} for (cat, cur), total in sorted(categories.items())
        ],
        "series": {
            "currency": chosen,
            "group": group,
            "points": finance_series(project, date_from, date_to, group, chosen) if chosen else [],
        },
    }


# ───────────────── Registro y edición auditados ─────────────────
from django.db import transaction  # noqa: E402

from accounts.services import audit  # noqa: E402

_TRACKED = ("date", "amount", "currency", "description", "category")


def _describe(instance) -> str:
    return f"{instance.__class__.__name__}#{instance.pk} {instance.project_id} {instance.currency} {instance.amount}"


@transaction.atomic
def record_movement(model, user, **data):
    """Crea un ingreso o gasto y lo deja en la bitácora."""
    movement = model.objects.create(created_by=user, **data)
    audit(user, "crear", model.__name__, movement.pk, _describe(movement))
    return movement


@transaction.atomic
def update_movement(movement, user, **changes):
    """Edita un movimiento (el proyecto no cambia) y audita qué cambió, de qué a qué."""
    diffs = []
    for field in _TRACKED:
        if field in changes and getattr(movement, field, None) != changes[field]:
            diffs.append(f"{field}: {getattr(movement, field)} -> {changes[field]}")
            setattr(movement, field, changes[field])
    if diffs:
        movement.save()
        audit(user, "editar", movement.__class__.__name__, movement.pk, "; ".join(diffs))
    return movement
