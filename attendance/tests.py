import datetime as dt
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from projects.models import Project
from workers.models import Employee

from .models import Attendance, AttendanceScan, ProjectLunchRule
from .services import net_worked_minutes, round_to_nearest

TZ = ZoneInfo("America/New_York")
MONDAY = dt.date(2026, 11, 2)
SATURDAY = dt.date(2026, 11, 7)


def at(day, h, m=0):
    return dt.datetime(day.year, day.month, day.day, h, m, tzinfo=TZ)


class BaseCase(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Montego")
        self.emp = Employee.objects.create(full_name="Juan Perez", hourly_rate="20")

    def day(self, date, cin, cout, **kw):
        return Attendance.objects.create(
            project=self.project, employee=self.emp, date=date,
            check_in=at(date, *cin), check_out=at(date, *cout), **kw
        )


class RoundingTests(TestCase):
    def test_redondeo_a_30(self):
        self.assertEqual(round_to_nearest(14), 0)
        self.assertEqual(round_to_nearest(15), 30)
        self.assertEqual(round_to_nearest(44), 30)
        self.assertEqual(round_to_nearest(45), 60)
        self.assertEqual(round_to_nearest(-5), 0)


class WorkedMinutesTests(BaseCase):
    def test_sin_regla_lunes_descuenta_hora_si_mas_de_5h(self):
        a = self.day(MONDAY, (7, 0), (16, 0))  # 9h bruto -> 8h
        self.assertEqual(a.worked_minutes(), 480)
        self.assertEqual(a.worked_hhmm(), "08:00")

    def test_sin_regla_jornada_corta_no_descuenta(self):
        a = self.day(MONDAY, (7, 0), (11, 0))
        self.assertEqual(a.worked_minutes(), 240)

    def test_sabado_no_descuenta(self):
        a = self.day(SATURDAY, (7, 0), (15, 0))
        self.assertEqual(a.worked_minutes(), 480)

    def test_regla_global_y_de_proyecto_prioriza_proyecto(self):
        ProjectLunchRule.objects.create(
            weekday=0, start_time=dt.time(12), end_time=dt.time(12, 30)
        )
        a = self.day(MONDAY, (7, 0), (16, 0))
        self.assertEqual(a.worked_minutes(), 510)  # 9h - 30 min de regla global
        ProjectLunchRule.objects.create(
            project=self.project, weekday=0, start_time=dt.time(12), end_time=dt.time(13)
        )
        self.assertEqual(net_worked_minutes(a), 480)

    def test_regla_inactiva_se_ignora(self):
        ProjectLunchRule.objects.create(
            weekday=0, start_time=dt.time(12), end_time=dt.time(12, 30), active=False
        )
        a = self.day(MONDAY, (7, 0), (16, 0))
        self.assertEqual(a.worked_minutes(), 480)

    def test_ajuste_manual_tiene_prioridad_y_exige_motivo(self):
        a = self.day(MONDAY, (7, 0), (16, 0))
        a.manual_minutes = 300
        with self.assertRaises(ValidationError):
            a.save()
        a.manual_note = "Salio temprano"
        a.save()
        self.assertEqual(a.worked_minutes(), 300)

    def test_sin_salida_son_cero_minutos(self):
        a = Attendance.objects.create(
            project=self.project, employee=self.emp, date=MONDAY, check_in=at(MONDAY, 7)
        )
        self.assertEqual(a.worked_minutes(), 0)


class ConstraintsTests(BaseCase):
    def test_salida_antes_de_ingreso_invalida(self):
        with self.assertRaises(ValidationError):
            self.day(MONDAY, (16, 0), (7, 0))

    def test_una_jornada_por_dia(self):
        self.day(MONDAY, (7, 0), (16, 0))
        with self.assertRaises(ValidationError):
            self.day(MONDAY, (8, 0), (17, 0))

    def test_unicidad_a_nivel_de_base_de_datos(self):
        self.day(MONDAY, (7, 0), (16, 0))
        with self.assertRaises(IntegrityError), transaction.atomic():
            Attendance.objects.bulk_create([
                Attendance(project=self.project, employee=self.emp, date=MONDAY)
            ])

    def test_regla_almuerzo_fin_mayor_que_inicio(self):
        with self.assertRaises(ValidationError):
            ProjectLunchRule.objects.create(
                weekday=1, start_time=dt.time(13), end_time=dt.time(12)
            )


class ScanTests(BaseCase):
    def test_scan_idempotente_por_client_uuid(self):
        s = AttendanceScan.objects.create(
            employee=self.emp, project=self.project, action="in", device_ts=at(MONDAY, 7)
        )
        with self.assertRaises(ValidationError):
            AttendanceScan.objects.create(
                client_uuid=s.client_uuid, employee=self.emp, action="in",
                device_ts=at(MONDAY, 7),
            )

    def test_fuente_invalida(self):
        with self.assertRaises(ValidationError):
            AttendanceScan.objects.create(
                employee=self.emp, action="in", device_ts=at(MONDAY, 7), source="huella_cruda"
            )
