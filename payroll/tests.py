import datetime as dt
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from projects.models import Project
from workers.models import Employee

from .models import PayrollLine, PayrollPeriod


class PayrollModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("admin", password="x")
        self.emp = Employee.objects.create(full_name="Juan Perez", hourly_rate="20")
        self.project = Project.objects.create(name="Montego")

    def period(self, **kw):
        data = dict(
            start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 8), created_by=self.user
        )
        data.update(kw)
        return PayrollPeriod.objects.create(**data)

    def test_fechas_invertidas_invalidas(self):
        with self.assertRaises(ValidationError):
            self.period(end_date=dt.date(2026, 11, 1))

    def test_periodo_nace_abierto(self):
        self.assertTrue(self.period().is_open)

    def test_unicidad_con_y_sin_proyecto(self):
        self.period()
        with self.assertRaises(ValidationError):
            self.period()
        self.period(project=self.project)
        with self.assertRaises(ValidationError):
            self.period(project=self.project)

    def test_linea_total_y_horas(self):
        line = PayrollLine.objects.create(
            period=self.period(), employee=self.emp, minutes=510,
            hourly_rate="20", base_amount="170.00", adjustment="-10.00", notes="Anticipo",
        )
        self.assertEqual(line.hours_hhmm, "08:30")
        self.assertEqual(line.total, Decimal("160.00"))

    def test_ajuste_exige_motivo(self):
        with self.assertRaises(ValidationError):
            PayrollLine.objects.create(
                period=self.period(), employee=self.emp, hourly_rate="20", adjustment="5.00"
            )

    def test_una_linea_por_trabajador_y_periodo(self):
        p = self.period()
        PayrollLine.objects.create(period=p, employee=self.emp, hourly_rate="20")
        with self.assertRaises(ValidationError):
            PayrollLine.objects.create(period=p, employee=self.emp, hourly_rate="20")


class PayrollServiceTests(TestCase):
    def setUp(self):
        from zoneinfo import ZoneInfo

        from attendance.models import Attendance

        self.tz = ZoneInfo("America/New_York")
        self.Attendance = Attendance
        self.user = get_user_model().objects.create_user("admin", password="x")
        self.project = Project.objects.create(name="Montego")
        self.emp = Employee.objects.create(full_name="Juan Perez", hourly_rate="20")
        self.period = PayrollPeriod.objects.create(
            start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 8), created_by=self.user
        )

    def work(self, emp, day, h_in=7, h_out=15, project=None):
        d = dt.date(2026, 11, day)
        return self.Attendance.objects.create(
            project=project or self.project, employee=emp, date=d,
            check_in=dt.datetime(d.year, d.month, d.day, h_in, tzinfo=self.tz),
            check_out=dt.datetime(d.year, d.month, d.day, h_out, tzinfo=self.tz),
        )

    def test_calcula_horas_por_tarifa(self):
        from .services import recalculate_period

        self.work(self.emp, 3)  # 8h bruto -> 7h neto (L-V descuenta 1h): 420 min
        recalculate_period(self.period, self.user)
        line = self.period.lines.get()
        self.assertEqual(line.minutes, 420)
        self.assertEqual(line.base_amount, Decimal("140.00"))

    def test_cambio_de_tarifa_a_mitad_de_periodo(self):
        from workers.services import set_rate

        from .services import recalculate_period

        set_rate(self.emp, 20, dt.date(2026, 1, 1))
        set_rate(self.emp, 30, dt.date(2026, 11, 5))
        self.work(self.emp, 3)  # 7h * 20 = 140
        self.work(self.emp, 5)  # 7h * 30 = 210
        recalculate_period(self.period, self.user)
        self.assertEqual(self.period.lines.get().base_amount, Decimal("350.00"))

    def test_pago_diario_para_supervisor(self):
        from .services import recalculate_period

        sup = Employee.objects.create(
            full_name="Ana Supervisora", pay_type="daily", daily_rate="150"
        )
        self.work(sup, 3)
        self.work(sup, 4)
        recalculate_period(self.period, self.user)
        line = self.period.lines.get(employee=sup)
        self.assertEqual(line.days, 2)
        self.assertEqual(line.base_amount, Decimal("300.00"))

    def test_recalcular_conserva_ajuste(self):
        from .services import recalculate_period, set_adjustment

        self.work(self.emp, 3)
        recalculate_period(self.period, self.user)
        set_adjustment(self.period.lines.get(), "-10", "Anticipo", self.user)
        self.work(self.emp, 4)
        recalculate_period(self.period, self.user)
        line = self.period.lines.get()
        self.assertEqual(line.adjustment, Decimal("-10.00"))
        self.assertEqual(line.total, Decimal("270.00"))

    def test_filtra_por_proyecto_del_periodo(self):
        from .services import recalculate_period

        other = Project.objects.create(name="Otro")
        self.period.project = self.project
        self.period.save()
        self.work(self.emp, 3, project=other)
        recalculate_period(self.period, self.user)
        self.assertEqual(self.period.lines.count(), 0)

    def test_ajuste_sin_motivo_falla(self):
        from .services import PayrollError, recalculate_period, set_adjustment

        self.work(self.emp, 3)
        recalculate_period(self.period, self.user)
        with self.assertRaises(PayrollError):
            set_adjustment(self.period.lines.get(), "5", "  ", self.user)

    def test_cierre_bloquea_cambios_y_audita(self):
        from accounts.models import AuditLog

        from .services import PayrollError, close_period, recalculate_period

        self.work(self.emp, 3)
        close_period(self.period, self.user)
        self.assertFalse(self.period.is_open)
        self.assertEqual(self.period.closed_by, self.user)
        with self.assertRaises(PayrollError):
            recalculate_period(self.period, self.user)
        with self.assertRaises(PayrollError):
            close_period(self.period, self.user)
        self.assertTrue(AuditLog.objects.filter(action="cerrar").exists())
