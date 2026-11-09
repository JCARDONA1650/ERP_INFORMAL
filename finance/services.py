"""Resumen financiero por proyecto. Las monedas NO se convierten: se totaliza por moneda."""
from decimal import Decimal

from django.db.models import Sum

from .models import ProjectExpense, ProjectIncome

ZERO = Decimal("0.00")


def _totals(qs, date_from=None, date_to=None) -> dict:
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return {
        row["currency"]: row["total"]
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
        (row["category"], row["currency"]): row["total"]
        for row in qs.values("category", "currency").annotate(total=Sum("amount"))
    }
