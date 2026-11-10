import datetime as dt
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from projects.models import Project
from workers.models import Employee

from .models import Attendance, AttendanceScan, ProjectLunchRule
from .services import net_worked_minutes, round_punch_to_hour

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
    def hour(self, h, m, s=0, exit_=False):
        r = round_punch_to_hour(dt.datetime(2026, 11, 2, h, m, s, tzinfo=TZ), is_exit=exit_)
        return (r.hour, r.minute)

    def test_redondea_a_la_hora_mas_cercana(self):
        self.assertEqual(self.hour(5, 10), (5, 0))
        self.assertEqual(self.hour(5, 29, 59), (5, 0))
        self.assertEqual(self.hour(5, 31), (6, 0))
        self.assertEqual(self.hour(18, 50, exit_=True), (19, 0))
        self.assertEqual(self.hour(18, 20, exit_=True), (18, 0))

    def test_en_la_mitad_exacta_favorece_al_trabajador(self):
        self.assertEqual(self.hour(5, 30), (5, 0))  # ingreso: baja
        self.assertEqual(self.hour(18, 30, exit_=True), (19, 0))  # salida: sube

    def test_cruza_el_dia_y_conserva_la_zona_horaria(self):
        r = round_punch_to_hour(dt.datetime(2026, 11, 2, 23, 50, tzinfo=TZ), is_exit=True)
        self.assertEqual((r.day, r.hour), (3, 0))


class WorkedMinutesTests(BaseCase):
    def test_sin_regla_lunes_descuenta_hora_si_mas_de_5h(self):
        a = self.day(MONDAY, (7, 0), (16, 0))  # 9h bruto -> 8h
        self.assertEqual(a.worked_minutes(), 480)
        self.assertEqual(a.worked_hhmm(), "08:00")

    def test_marcaciones_se_redondean_a_la_hora_antes_de_calcular(self):
        # 5:10 → 5:00 y 18:50 → 19:00 = 14 h brutas; sin regla de almuerzo descuenta 1 h (L-V, > 5 h)
        a = self.day(MONDAY, (5, 10), (18, 50))
        self.assertEqual(a.worked_minutes(), 13 * 60)
        # con almuerzo configurado de 1 h el resultado es el mismo
        ProjectLunchRule.objects.create(
            project=self.project, weekday=0, start_time=dt.time(12), end_time=dt.time(13)
        )
        self.assertEqual(net_worked_minutes(a), 13 * 60)

    def test_se_paga_hora_trabajada_sin_recargos(self):
        # 10 h netas = 10 × tarifa; no hay horas extra aunque la jornada sea larga
        a = self.day(SATURDAY, (6, 0), (16, 0))
        self.assertEqual(a.worked_minutes(), 600)

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


from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402

from projects.models import ProjectSite  # noqa: E402

from .qr import QRTokenError, make_qr_token, verify_qr_token  # noqa: E402
from .services import ScanError, register_scan  # noqa: E402


class QRTokenTests(BaseCase):
    def test_token_valido_del_dia(self):
        verify_qr_token(self.project, make_qr_token(self.project))

    def test_token_de_otro_proyecto_falla(self):
        other = Project.objects.create(name="Otro")
        with self.assertRaises(QRTokenError):
            verify_qr_token(other, make_qr_token(self.project))

    def test_token_de_otro_dia_falla(self):
        yesterday = dt.date.today() - dt.timedelta(days=1)
        with self.assertRaises(QRTokenError):
            verify_qr_token(self.project, make_qr_token(self.project, yesterday))

    def test_token_manipulado_o_vacio_falla(self):
        with self.assertRaises(QRTokenError):
            verify_qr_token(self.project, make_qr_token(self.project) + "x")
        with self.assertRaises(QRTokenError):
            verify_qr_token(self.project, "")


class RegisterScanTests(BaseCase):
    def test_ingreso_y_salida(self):
        r = register_scan(self.project, self.emp, "in")
        self.assertIsNotNone(r.attendance.check_in)
        self.assertIn(self.emp, self.project.employees.all())
        r = register_scan(self.project, self.emp, "out")
        self.assertIsNotNone(r.attendance.check_out)
        self.assertEqual(AttendanceScan.objects.count(), 2)

    def test_salida_sin_ingreso(self):
        with self.assertRaises(ScanError):
            register_scan(self.project, self.emp, "out")
        self.assertEqual(AttendanceScan.objects.count(), 0)

    def test_reintento_offline_no_duplica(self):
        import uuid

        uid = uuid.uuid4()
        register_scan(self.project, self.emp, "in", client_uuid=uid)
        r = register_scan(self.project, self.emp, "in", client_uuid=uid)
        self.assertTrue(r.duplicate)
        self.assertEqual(AttendanceScan.objects.count(), 1)

    def test_segundo_ingreso_no_cambia_hora(self):
        first = register_scan(self.project, self.emp, "in").attendance.check_in
        again = register_scan(self.project, self.emp, "in").attendance
        self.assertEqual(again.check_in, first)

    def test_trabajador_inactivo(self):
        self.emp.active = False
        self.emp.save()
        with self.assertRaises(ScanError):
            register_scan(self.project, self.emp, "in")

    def test_fuera_de_zona_con_block_rechaza(self):
        ProjectSite.objects.create(
            project=self.project, latitude="28.500000", longitude="-81.400000", radius_m=150
        )  # política por defecto: block
        project = Project.objects.get(pk=self.project.pk)
        with self.assertRaises(ScanError):
            register_scan(project, self.emp, "in", latitude=28.52, longitude=-81.4)
        with self.assertRaises(ScanError):  # sin ubicación tampoco se puede verificar
            register_scan(project, self.emp, "in")
        self.assertFalse(Attendance.objects.exists())

    def test_fuera_de_zona_marca_revision_sin_bloquear(self):
        ProjectSite.objects.create(
            project=self.project, latitude="28.500000", longitude="-81.400000",
            radius_m=150, out_of_zone_policy="review",
        )
        project = Project.objects.get(pk=self.project.pk)
        r = register_scan(project, self.emp, "in", latitude=28.52, longitude=-81.4)
        self.assertFalse(r.in_zone)
        self.assertTrue(r.attendance.needs_review)
        self.assertIsNotNone(r.attendance.check_in)

    def test_dentro_de_zona_no_requiere_revision(self):
        ProjectSite.objects.create(
            project=self.project, latitude="28.500000", longitude="-81.400000", radius_m=150
        )  # con block también se acepta si está dentro
        project = Project.objects.get(pk=self.project.pk)
        r = register_scan(project, self.emp, "in", latitude=28.5005, longitude=-81.4)
        self.assertTrue(r.in_zone)
        self.assertFalse(r.attendance.needs_review)

    def test_sin_ubicacion_no_marca_revision(self):
        r = register_scan(self.project, self.emp, "in")
        self.assertIsNone(r.in_zone)
        self.assertFalse(r.attendance.needs_review)

    def test_foto_se_conserva_si_la_siguiente_marcacion_no_trae(self):
        import tempfile

        from django.test import override_settings
        from PIL import Image
        import io

        buf = io.BytesIO()
        Image.new("RGB", (4, 4)).save(buf, "PNG")
        photo = SimpleUploadedFile("f.png", buf.getvalue(), content_type="image/png")
        with tempfile.TemporaryDirectory() as tmp, override_settings(MEDIA_ROOT=tmp):
            register_scan(self.project, self.emp, "in", photo=photo)
            r = register_scan(self.project, self.emp, "out")
            self.assertTrue(r.attendance.evidence_photo)


from django.contrib.auth import get_user_model  # noqa: E402

from payroll.models import PayrollPeriod  # noqa: E402

from .services import AttendanceLocked, adjust_minutes, review_attendance  # noqa: E402


class ReviewAndAdjustTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user("sup", password="x")

    def test_revisar_registra_quien_y_cuando(self):
        from accounts.models import AuditLog

        a = self.day(MONDAY, (7, 0), (16, 0), needs_review=True)
        review_attendance(a, self.user)
        a.refresh_from_db()
        self.assertFalse(a.needs_review)
        self.assertEqual(a.reviewed_by, self.user)
        self.assertIsNotNone(a.reviewed_at)
        self.assertTrue(AuditLog.objects.filter(action="revisar", entity_id=str(a.pk)).exists())

    def test_ajuste_exige_motivo(self):
        a = self.day(MONDAY, (7, 0), (16, 0))
        with self.assertRaises(ValueError):
            adjust_minutes(a, 300, "  ", self.user)

    def test_ajuste_cambia_minutos_y_audita(self):
        from accounts.models import AuditLog

        a = self.day(MONDAY, (7, 0), (16, 0))
        adjust_minutes(a, 300, "Salio temprano", self.user)
        a.refresh_from_db()
        self.assertEqual(a.worked_minutes(), 300)
        self.assertIn("480 -> 300", AuditLog.objects.get(action="ajustar").detail)

    def test_ajuste_bloqueado_en_nomina_cerrada(self):
        a = self.day(MONDAY, (7, 0), (16, 0))
        PayrollPeriod.objects.create(
            start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 8),
            created_by=self.user, status="CLOSED",
        )
        with self.assertRaises(AttendanceLocked):
            adjust_minutes(a, 300, "Tarde", self.user)

    def test_nomina_cerrada_de_otro_proyecto_no_bloquea(self):
        other = Project.objects.create(name="Otro")
        a = self.day(MONDAY, (7, 0), (16, 0))
        PayrollPeriod.objects.create(
            start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 8),
            project=other, created_by=self.user, status="CLOSED",
        )
        adjust_minutes(a, 300, "Ok", self.user)
        self.assertEqual(Attendance.objects.get(pk=a.pk).manual_minutes, 300)
