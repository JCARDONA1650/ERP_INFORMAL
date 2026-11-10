import tempfile

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from accounts.models import AuditLog
from accounts.roles import ADMINISTRADOR, RRHH, SUPERVISOR, assign_role
from attendance.models import Attendance, AttendanceScan
from projects.models import Project, ProjectSite
from workers.models import Employee

from .tests_scan import png

_MEDIA = tempfile.mkdtemp(prefix="media_test_")
URL = "/api/attendance/manual/"
CTX = "/api/attendance/manual/context/"


@override_settings(MEDIA_ROOT=_MEDIA)
class ManualScanTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.sup = User.objects.create_user("sup", password="x")
        cls.other_sup = User.objects.create_user("sup2", password="x")
        cls.adm = User.objects.create_user("adm", password="x")
        cls.hr = User.objects.create_user("hr", password="x")
        assign_role(cls.sup, SUPERVISOR)
        assign_role(cls.other_sup, SUPERVISOR)
        assign_role(cls.adm, ADMINISTRADOR)
        assign_role(cls.hr, RRHH)
        cls.project = Project.objects.create(name="Montego")
        ProjectSite.objects.create(
            project=cls.project, latitude="28.500000", longitude="-81.400000", radius_m=150
        )
        cls.other = Project.objects.create(name="Torre Norte")
        cls.project.supervisors.add(cls.sup)
        cls.other.supervisors.add(cls.other_sup)
        cls.ana = Employee.objects.create(full_name="Ana Gomez")
        cls.project.employees.add(cls.ana)

    def setUp(self):
        cache.clear()

    def post(self, user, data=None):
        self.client.force_authenticate(user)
        payload = {
            "project": self.project.pk, "employee": self.ana.pk, "action": "in",
            "latitude": 28.5, "longitude": -81.4, "photo": png(),
        }
        payload.update(data or {})
        payload = {k: v for k, v in payload.items() if v is not None}
        return self.client.post(URL, payload, format="multipart")

    def test_supervisor_marca_a_un_trabajador_de_su_proyecto(self):
        r = self.post(self.sup)
        self.assertEqual(r.status_code, 201, r.data)
        att = Attendance.objects.get(project=self.project, employee=self.ana)
        self.assertEqual(att.check_in_source, "manual")
        self.assertTrue(att.evidence_photo)
        scan = AttendanceScan.objects.get()
        self.assertEqual(scan.source, "manual")
        self.assertEqual(scan.verification_reference, "manual:sup")
        self.assertTrue(AuditLog.objects.filter(action="marcar_manual", user=self.sup).exists())

    def test_salida_con_el_mismo_flujo(self):
        self.post(self.sup)
        r = self.post(self.sup, {"action": "out"})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNotNone(Attendance.objects.get().check_out)

    def test_administrador_marca_en_cualquier_proyecto(self):
        self.assertEqual(self.post(self.adm).status_code, 201)

    def test_rrhh_no_puede_marcar(self):
        self.assertEqual(self.post(self.hr).status_code, 403)
        self.client.force_authenticate(self.hr)
        self.assertEqual(self.client.get(CTX).status_code, 403)

    def test_sin_sesion_es_401(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(URL, {}, format="multipart").status_code, 401)

    def test_supervisor_ajeno_al_proyecto_es_rechazado(self):
        r = self.post(self.other_sup)
        self.assertEqual(r.status_code, 400)
        self.assertIn("project", r.data)
        self.assertFalse(Attendance.objects.exists())

    def test_trabajador_no_asignado_es_rechazado(self):
        stranger = Employee.objects.create(full_name="Externo")
        r = self.post(self.sup, {"employee": stranger.pk})
        self.assertEqual(r.status_code, 400)
        self.assertIn("employee", r.data)

    def test_fuera_de_zona_se_rechaza_con_politica_block(self):
        r = self.post(self.sup, {"latitude": 28.6, "longitude": -81.4})
        self.assertEqual(r.status_code, 409)
        self.assertIn("fuera de la zona", r.data["detail"])

    def test_sin_gps_se_rechaza_con_politica_block(self):
        r = self.post(self.sup, {"latitude": None, "longitude": None})
        self.assertEqual(r.status_code, 409)

    def test_foto_obligatoria_por_defecto(self):
        r = self.post(self.sup, {"photo": None})
        self.assertEqual(r.status_code, 400)
        self.assertIn("photo", r.data)

    def test_foto_opcional_si_el_proyecto_lo_permite(self):
        Project.objects.filter(pk=self.project.pk).update(photo_required=False)
        r = self.post(self.sup, {"photo": None})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(Attendance.objects.get().evidence_photo)

    def test_contexto_lista_solo_proyectos_y_trabajadores_atendibles(self):
        self.client.force_authenticate(self.sup)
        r = self.client.get(CTX)
        self.assertEqual(r.status_code, 200)
        self.assertEqual([p["name"] for p in r.data], ["Montego"])
        self.assertEqual(r.data[0]["employees"], [{"id": self.ana.pk, "full_name": "Ana Gomez"}])
        self.assertTrue(r.data[0]["photo_required"])
        self.client.force_authenticate(self.adm)
        self.assertEqual(len(self.client.get(CTX).data), 2)

    def test_reintento_con_el_mismo_uuid_no_duplica(self):
        uid = "6f1d1b9e-4d8f-4c3a-9a4e-0f2d3c4b5a69"
        self.assertEqual(self.post(self.sup, {"client_uuid": uid}).status_code, 201)
        r = self.post(self.sup, {"client_uuid": uid})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(AttendanceScan.objects.count(), 1)
