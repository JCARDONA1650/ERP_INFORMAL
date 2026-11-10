import datetime as dt
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.roles import ADMINISTRADOR, assign_role
from attendance.models import Attendance, ProjectLunchRule
from attendance.services import net_worked_minutes, register_scan
from projects.models import Project
from workers.models import Employee

TZ = ZoneInfo("America/New_York")
URL = "/api/projects/"


class ScheduleApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.adm = get_user_model().objects.create_user("adm", password="x")
        assign_role(cls.adm, ADMINISTRADOR)

    def setUp(self):
        self.client.force_authenticate(self.adm)

    def create(self, **extra):
        body = {"name": "Obra", "work_days": [0, 1, 2, 3, 4, 5], "work_start": "07:00", "work_end": "17:00",
                "lunch_start": "13:00", "lunch_end": "14:00"}
        body.update(extra)
        return self.client.post(URL, body, format="json")

    def test_crea_proyecto_con_jornada_y_almuerzo(self):
        r = self.create()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["work_days"], [0, 1, 2, 3, 4, 5])
        self.assertEqual((r.data["work_start"], r.data["work_end"]), ("07:00:00", "17:00:00"))
        self.assertEqual((r.data["lunch_start"], r.data["lunch_end"]), ("13:00", "14:00"))
        self.assertFalse(r.data["lunch_custom"])
        project = Project.objects.get(pk=r.data["id"])
        self.assertEqual(project.lunch_rules.count(), 6)  # lunes a sábado
        self.assertEqual({x.weekday for x in project.lunch_rules.all()}, {0, 1, 2, 3, 4, 5})

    def test_sin_jornada_no_restringe_ni_crea_almuerzo(self):
        r = self.client.post(URL, {"name": "Libre"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["work_days"], [])
        self.assertIsNone(r.data["lunch_start"])
        self.assertFalse(Project.objects.get(pk=r.data["id"]).outside_schedule(timezone.now()))

    def test_editar_y_quitar_almuerzo(self):
        pid = self.create().data["id"]
        r = self.client.patch(f"{URL}{pid}/", {"lunch_start": "12:00", "lunch_end": "13:00"}, format="json")
        self.assertEqual((r.data["lunch_start"], r.data["lunch_end"]), ("12:00", "13:00"))
        r = self.client.patch(f"{URL}{pid}/", {"lunch_start": None, "lunch_end": None}, format="json")
        self.assertIsNone(r.data["lunch_start"])
        self.assertEqual(ProjectLunchRule.objects.filter(project_id=pid).count(), 0)

    def test_si_no_se_envia_almuerzo_no_se_toca(self):
        pid = self.create().data["id"]
        self.client.patch(f"{URL}{pid}/", {"name": "Obra B"}, format="json")
        self.assertEqual(ProjectLunchRule.objects.filter(project_id=pid).count(), 6)

    def test_reglas_distintas_por_dia_se_marcan_personalizadas(self):
        pid = self.create(work_days=[], lunch_start=None, lunch_end=None).data["id"]
        ProjectLunchRule.objects.create(project_id=pid, weekday=0, start_time=dt.time(12), end_time=dt.time(13))
        ProjectLunchRule.objects.create(project_id=pid, weekday=1, start_time=dt.time(13), end_time=dt.time(14))
        r = self.client.get(f"{URL}{pid}/")
        self.assertTrue(r.data["lunch_custom"])
        self.assertIsNone(r.data["lunch_start"])

    def test_validaciones(self):
        self.assertEqual(self.create(work_days=[7]).status_code, 400)
        self.assertEqual(self.create(work_days=["lunes"]).status_code, 400)
        self.assertEqual(self.create(work_end="06:00").status_code, 400)
        self.assertEqual(self.create(work_end=None).status_code, 400)
        self.assertEqual(self.create(lunch_end="12:00").status_code, 400)
        self.assertEqual(self.create(lunch_end=None).status_code, 400)

    def test_el_almuerzo_se_descuenta_de_las_horas_netas(self):
        pid = self.create().data["id"]
        project = Project.objects.get(pk=pid)
        emp = Employee.objects.create(full_name="Ana")
        day = dt.date(2026, 11, 2)  # lunes
        att = Attendance.objects.create(
            project=project, employee=emp, date=day,
            check_in=dt.datetime(2026, 11, 2, 7, tzinfo=TZ), check_out=dt.datetime(2026, 11, 2, 16, tzinfo=TZ),
        )
        self.assertEqual(net_worked_minutes(att), 8 * 60)  # 9 h brutas - 1 h de almuerzo


class OffScheduleScanTests(APITestCase):
    def setUp(self):
        self.emp = Employee.objects.create(full_name="Ana")

    def project(self, work_days):
        p = Project.objects.create(name="Obra", work_days=work_days)
        p.employees.add(self.emp)
        return p

    def test_marcar_en_dia_no_laboral_queda_para_revision(self):
        today = timezone.localdate().weekday()
        p = self.project([(today + 1) % 7])
        res = register_scan(p, self.emp, "in")
        self.assertTrue(res.attendance.needs_review)
        self.assertIn("fuera de la jornada", res.message)

    def test_marcar_en_dia_laboral_no_requiere_revision(self):
        p = self.project([timezone.localdate().weekday()])
        res = register_scan(p, self.emp, "in")
        self.assertFalse(res.attendance.needs_review)
        self.assertNotIn("jornada", res.message)

    def test_fuera_de_horario_queda_para_revision(self):
        p = Project.objects.create(name="Noche", work_start=dt.time(0, 0), work_end=dt.time(0, 1))
        p.employees.add(self.emp)
        local = timezone.localtime()
        if local.time() <= dt.time(0, 1):  # evita el borde justo después de medianoche
            self.skipTest("ejecución a medianoche")
        self.assertTrue(register_scan(p, self.emp, "in").attendance.needs_review)
