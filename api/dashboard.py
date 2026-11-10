"""Resumen para la pantalla de Inicio, según el rol.

- Supervisor: solo sus proyectos (asistencia y marcaciones del día).
- RRHH: todos los proyectos + trabajadores y nómina.
- Administrador / Super Admin: lo anterior + resumen financiero.
Las cifras se calculan con consultas agregadas (sin N+1)."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.roles import ADMINISTRADOR, RRHH, user_has_role
from attendance.models import Attendance, AttendanceScan
from attendance.services import lunch_from_map, lunch_minutes_map, net_worked_minutes
from finance.models import ProjectExpense, ProjectIncome
from payroll.models import STATUS_OPEN, PayrollPeriod
from projects.models import Project
from projects.services import projects_for
from workers.models import Employee

from .attendance import IsStaffRole

DAYS = 7


def _totals(model, project_ids) -> dict:
    from django.db.models import Sum

    rows = model.objects.filter(project_id__in=project_ids).values("currency").annotate(t=Sum("amount"))
    return {r["currency"]: str(Decimal(r["t"]).quantize(Decimal("0.01"))) for r in rows}


class DashboardView(APIView):
    permission_classes = [IsStaffRole]

    def get(self, request):
        user = request.user
        backoffice = user_has_role(user, ADMINISTRADOR, RRHH)
        today = timezone.localdate()
        start = today - timedelta(days=DAYS - 1)

        projects_qs = Project.objects.filter(active=True) if backoffice else projects_for(user).filter(active=True)
        projects = list(projects_qs.select_related("site").order_by("name"))
        pids = [p.pk for p in projects]

        att = Attendance.objects.filter(project_id__in=pids)
        today_att = att.filter(date=today)

        # Por proyecto: presentes hoy (con ingreso) y pendientes de revisión, en una sola consulta.
        per_project = {
            row["project_id"]: row
            for row in att.values("project_id").annotate(
                present=Count("id", filter=Q(date=today, check_in__isnull=False)),
                pending=Count("id", filter=Q(needs_review=True)),
            )
        }
        assigned = {
            row["pk"]: row["n"]
            for row in Project.objects.filter(pk__in=pids).values("pk").annotate(n=Count("employees"))
        }

        project_rows = []
        for p in projects:
            site = getattr(p, "site", None)
            stats = per_project.get(p.pk, {})
            project_rows.append(
                {
                    "id": p.pk,
                    "name": p.name,
                    "workers": assigned.get(p.pk, 0),
                    "present_today": stats.get("present", 0),
                    "pending_review": stats.get("pending", 0),
                    "site": None if site is None else {
                        "latitude": float(site.latitude),
                        "longitude": float(site.longitude),
                        "radius_m": site.radius_m,
                        "out_of_zone_policy": site.out_of_zone_policy,
                    },
                }
            )

        # Marcaciones de hoy con ubicación (para el mapa).
        scans = (
            AttendanceScan.objects.filter(project_id__in=pids, server_ts__date=today, latitude__isnull=False)
            .select_related("employee", "project")
            .order_by("-server_ts")[:100]
        )
        marks = [
            {
                "employee": s.employee.full_name,
                "project": s.project.name,
                "action": s.action,
                "time": timezone.localtime(s.server_ts).strftime("%H:%M"),
                "latitude": float(s.latitude),
                "longitude": float(s.longitude),
                "in_zone": s.in_zone,
            }
            for s in scans
        ]

        # Horas netas de los últimos 7 días (usa las reglas de almuerzo y redondeo).
        lunch_map = lunch_minutes_map()
        minutes_by_day = {start + timedelta(days=i): 0 for i in range(DAYS)}
        for a in att.filter(date__gte=start, date__lte=today, check_in__isnull=False).select_related("project"):
            minutes_by_day[a.date] += net_worked_minutes(a, lunch_minutes=lunch_from_map(lunch_map, a.project_id, a.date))
        hours = [{"date": d.isoformat(), "hours": round(m / 60, 2)} for d, m in sorted(minutes_by_day.items())]

        data = {
            "role_scope": "backoffice" if backoffice else "supervisor",
            "today": today.isoformat(),
            "attendance": {
                "present_today": today_att.filter(check_in__isnull=False).count(),
                "open_shifts": today_att.filter(check_in__isnull=False, check_out__isnull=True).count(),
                "out_of_zone_today": today_att.filter(in_zone=False).count(),
                "pending_review": att.filter(needs_review=True).count(),
            },
            "projects": project_rows,
            "marks_today": marks,
            "hours_last_days": hours,
        }

        if backoffice:
            data["workers"] = {
                "active": Employee.objects.filter(active=True).count(),
                "inactive": Employee.objects.filter(active=False).count(),
            }
            data["payroll"] = {
                "open_periods": PayrollPeriod.objects.filter(status=STATUS_OPEN).count(),
            }
        if user_has_role(user, ADMINISTRADOR):
            data["finance"] = {
                "incomes": _totals(ProjectIncome, pids),
                "expenses": _totals(ProjectExpense, pids),
            }
        return Response(data)
