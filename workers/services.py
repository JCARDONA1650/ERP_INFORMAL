"""Reglas de negocio de trabajadores y tarifas."""
import logging
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Employee, RateHistory

logger = logging.getLogger(__name__)


def find_similar_names(full_name, exclude_pk=None):
    """Trabajadores con nombre igual (sin importar mayúsculas ni espacios) para
    alertar de posibles homónimos antes de crear uno nuevo."""
    clean = " ".join((full_name or "").strip().split())
    if not clean:
        return Employee.objects.none()
    qs = Employee.objects.filter(full_name__iexact=clean)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs


def rate_for(employee, on_date: date) -> Decimal:
    """Tarifa por hora vigente en una fecha. Si no hay historial anterior a esa
    fecha, se usa la tarifa actual del trabajador."""
    entry = (
        employee.rate_history.filter(effective_from__lte=on_date)
        .order_by("-effective_from", "-id")
        .first()
    )
    return entry.rate if entry else employee.hourly_rate


@transaction.atomic
def set_rate(employee, rate, effective_from: date, user=None):
    """Registra una tarifa con fecha de vigencia. Si ya rige (fecha <= hoy),
    actualiza la tarifa vigente del trabajador."""
    rate = Decimal(str(rate))
    entry, _ = RateHistory.objects.update_or_create(
        employee=employee,
        effective_from=effective_from,
        defaults={"rate": rate, "created_by": user},
    )
    latest = employee.rate_history.filter(
        effective_from__lte=timezone.localdate()
    ).order_by("-effective_from", "-id").first()
    if latest and employee.hourly_rate != latest.rate:
        employee.hourly_rate = latest.rate
        employee.save()
    logger.info(
        "Tarifa registrada: trabajador=%s tarifa=%s desde=%s", employee.pk, rate, effective_from
    )
    return entry
