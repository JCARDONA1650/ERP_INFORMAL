import datetime as dt
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase

from attendance.models import Attendance, ProjectLunchRule
from payroll.models import PayrollPeriod
from payroll.services import recalculate_period, set_adjustment
from projects.models import Project
from workers.models import Employee

from .services import attendance_rows, attendance_totals, payroll_rows, payroll_totals

TZ = ZoneInfo("America/New_York")


class ReportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("admin", password="x")
        self.project = Project.objects.create(name="Montego")
        self.a = Employee.objects.create(full_name="Ana Gomez", hourly_rate="20")
        self.b = Employee.objects.create(full_name="Beto Ruiz", hourly_rate="10", currency="COP")

    def work(self, emp, day, h_in=7, h_out=15, **kw):
        d = dt.date(2026, 11, day)
        return Attendance.objects.create(
            project=self.project, employee=emp, date=d,
            check_in=dt.datetime(d.year, d.month, d.day, h_in, tzinfo=TZ),
            check_out=dt.datetime(d.year, d.month, d.day, h_out, tzinfo=TZ), **kw
        )

    def test_filas_y_totales_de_asistencia(self):
        self.work(self.a, 3)
        self.work(self.b, 3, needs_review=True)
        rows = attendance_rows(dt.date(2026, 11, 1), dt.date(2026, 11, 30))
        self.assertEqual([r["employee"] for r in rows], ["Ana Gomez", "Beto Ruiz"])
        t = attendance_totals(rows)
        self.assertEqual(t["total_minutes"], 840)  # 2 x 7 h
        self.assertEqual(t["pending_review"], 1)

    def test_regla_de_almuerzo_se_aplica_sin_consultas_por_fila(self):
        ProjectLunchRule.objects.create(
            weekday=1, start_time=dt.time(12), end_time=dt.time(12, 30)
        )
        for d in (3, 10, 17):
            self.work(self.a, d)
        with self.assertNumQueries(2):  # reglas + jornadas
            rows = attendance_rows(dt.date(2026, 11, 1), dt.date(2026, 11, 30))
        self.assertTrue(all(r["minutes"] == 450 for r in rows))  # 8h - 30 min

    def test_filtro_por_trabajador_y_rango(self):
        self.work(self.a, 3)
        self.work(self.b, 4)
        rows = attendance_rows(dt.date(2026, 11, 1), dt.date(2026, 11, 3), employee=self.a)
        self.assertEqual(len(rows), 1)

    def test_nomina_por_moneda(self):
        self.work(self.a, 3)  # 7h * 20 = 140 USD
        self.work(self.b, 3)  # 7h * 10 = 70 COP
        period = PayrollPeriod.objects.create(
            start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 8), created_by=self.user
        )
        recalculate_period(period, self.user)
        set_adjustment(period.lines.get(employee=self.a), "10", "Bono", self.user)
        rows = payroll_rows(period)
        self.assertEqual(payroll_totals(rows), {"USD": Decimal("150.00"), "COP": Decimal("70.00")})
