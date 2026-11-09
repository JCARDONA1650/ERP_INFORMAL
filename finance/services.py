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
