"""Datos de reportes (asistencia y nómina). Solo construyen estructuras; la
presentación y exportación (Excel/PDF) se agregan en la capa de API."""
from collections import defaultdict
from decimal import Decimal

from attendance.models import Attendance
from attendance.services import lunch_from_map, lunch_minutes_map, net_worked_minutes


def attendance_rows(date_from, date_to, project=None, employee=None, projects=None) -> list[dict]:
    """Jornadas del rango con minutos netos. Consultas constantes (sin N+1)."""
    qs = Attendance.objects.select_related("project", "employee").filter(
        date__range=(date_from, date_to)
    )
    if project:
        qs = qs.filter(project=project)
    if employee:
        qs = qs.filter(employee=employee)
    if projects is not None:  # restringe a un conjunto (p. ej. proyectos de un supervisor)
        qs = qs.filter(project__in=projects)

    lunch = lunch_minutes_map()
    rows = []
    for a in qs.order_by("date", "project__name", "employee__full_name"):
        rule = lunch_from_map(lunch, a.project_id, a.date)
        rows.append({
            "date": a.date,
            "project": a.project.name,
            "employee": a.employee.full_name,
            "check_in": a.check_in,
            "check_out": a.check_out,
            "minutes": net_worked_minutes(a, lunch_minutes=rule),
            "in_zone": a.in_zone,
            "needs_review": a.needs_review,
            "manual": a.manual_minutes is not None,
        })
    return rows


def attendance_totals(rows: list[dict]) -> dict:
    """Minutos totales por trabajador y jornadas pendientes de revisión."""
    per_employee = defaultdict(int)
    for r in rows:
        per_employee[r["employee"]] += r["minutes"]
    return {
        "minutes_by_employee": dict(per_employee),
        "total_minutes": sum(per_employee.values()),
        "pending_review": sum(1 for r in rows if r["needs_review"]),
    }


def payroll_rows(period) -> list[dict]:
    return [
        {
            "employee": line.employee.full_name,
            "document_id": line.employee.document_id,
            "hours": line.hours_hhmm,
            "days": line.days,
            "hourly_rate": line.hourly_rate,
            "currency": line.currency,
            "base_amount": line.base_amount,
            "adjustment": line.adjustment,
            "notes": line.notes,
            "total": line.total,
        }
        for line in period.lines.select_related("employee")
    ]


def payroll_totals(rows: list[dict]) -> dict:
    """Total a pagar por moneda (sin conversión)."""
    totals = defaultdict(lambda: Decimal("0.00"))
    for r in rows:
        totals[r["currency"]] += r["total"]
    return dict(totals)
