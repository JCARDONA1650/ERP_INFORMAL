from datetime import date, timedelta

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.views import APIView

from accounts.roles import ADMINISTRADOR, RRHH, user_has_role
from accounts.services import audit
from finance.services import expenses_by_category, project_summary
from payroll.models import PayrollPeriod
from projects.models import Project
from projects.services import projects_for
from reports.exports import (
    LedgerTooLarge,
    Table,
    attendance_table,
    finance_ledger_table,
    finance_table,
    payroll_table,
    to_pdf,
    to_xlsx,
)
from reports.services import attendance_rows

from .attendance import IsStaffRole
from .permissions import IsAdministrador, IsBackoffice

MAX_RANGE_DAYS = 366
CONTENT_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


def _file_response(table: Table, fmt: str) -> HttpResponse:
    if fmt not in CONTENT_TYPES:
        raise serializers.ValidationError({"detail": "Formato no soportado. Usa xlsx o pdf."})
    content = to_xlsx(table) if fmt == "xlsx" else to_pdf(table)
    response = HttpResponse(content, content_type=CONTENT_TYPES[fmt])
    response["Content-Disposition"] = f'attachment; filename="{table.filename}.{fmt}"'
    response["Cache-Control"] = "no-store"  # contiene datos de personal y de dinero
    return response


def _parse_date(request, name, required=True):
    raw = request.query_params.get(name)
    if not raw:
        if required:
            raise serializers.ValidationError({"detail": f"{name} es obligatorio (AAAA-MM-DD)."})
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise serializers.ValidationError({"detail": f"{name} debe tener formato AAAA-MM-DD."}) from exc


class PayrollReportView(APIView):
    permission_classes = [IsBackoffice]

    def get(self, request, pk, fmt):
        period = get_object_or_404(PayrollPeriod.objects.select_related("project"), pk=pk)
        response = _file_response(payroll_table(period), fmt)
        audit(request.user, "exportar", "PayrollPeriod", period.pk, f"nómina {fmt}")
        return response


class AttendanceReportView(APIView):
    """Backoffice: todo. Supervisor: solo sus proyectos."""

    permission_classes = [IsStaffRole]

    def get(self, request, fmt):
        date_from, date_to = _parse_date(request, "date_from"), _parse_date(request, "date_to")
        if date_to < date_from:
            raise serializers.ValidationError({"detail": "date_to no puede ser menor que date_from."})
        if date_to - date_from > timedelta(days=MAX_RANGE_DAYS):
            raise serializers.ValidationError({"detail": f"El rango máximo es de {MAX_RANGE_DAYS} días."})

        project = employee = None
        if raw := request.query_params.get("project"):
            project = raw if raw.isdigit() else None
            if project is None:
                raise serializers.ValidationError({"detail": "project debe ser un número."})
        if raw := request.query_params.get("employee"):
            if not raw.isdigit():
                raise serializers.ValidationError({"detail": "employee debe ser un número."})
            employee = raw

        scope = None if user_has_role(request.user, ADMINISTRADOR, RRHH) else projects_for(request.user)
        rows = attendance_rows(
            date_from, date_to, project=project, employee=employee, projects=scope
        )
        response = _file_response(attendance_table(rows, date_from, date_to), fmt)
        audit(request.user, "exportar", "Attendance", "", f"asistencia {fmt} {date_from}..{date_to}")
        return response


class FinanceReportView(APIView):
    permission_classes = [IsAdministrador]

    def get(self, request, pk, fmt):
        project = get_object_or_404(Project, pk=pk)
        date_from = _parse_date(request, "date_from", required=False)
        date_to = _parse_date(request, "date_to", required=False)
        table = finance_table(
            project,
            project_summary(project, date_from, date_to),
            expenses_by_category(project, date_from, date_to),
            date_from,
            date_to,
        )
        response = _file_response(table, fmt)
        audit(request.user, "exportar", "Project", project.pk, f"finanzas {fmt}")
        return response


class FinanceLedgerReportView(APIView):
    """Registro global de ingresos y gastos (todos los proyectos o `?project=`), con fechas opcionales."""

    permission_classes = [IsAdministrador]

    def get(self, request, fmt):
        project = None
        if raw := request.query_params.get("project"):
            if not raw.isdigit():
                raise serializers.ValidationError({"detail": "project debe ser un número."})
            project = get_object_or_404(Project, pk=int(raw))
        date_from = _parse_date(request, "date_from", required=False)
        date_to = _parse_date(request, "date_to", required=False)
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError({"detail": "La fecha inicial no puede ser mayor que la final."})
        try:
            table = finance_ledger_table(project, date_from, date_to)
        except LedgerTooLarge as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc
        response = _file_response(table, fmt)
        audit(request.user, "exportar", "Project", project.pk if project else "", f"registro financiero {fmt}")
        return response
