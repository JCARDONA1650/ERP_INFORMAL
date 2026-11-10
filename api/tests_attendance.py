import datetime as dt
import io
import tempfile
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from accounts.roles import ADMINISTRADOR, RRHH, SUPERVISOR, assign_role
from attendance.models import Attendance, ProjectLunchRule
from payroll.models import PayrollPeriod
from projects.models import Project
from workers.models import Employee

URL = "/api/attendance/"
TZ = ZoneInfo("America/New_York")
_MEDIA = tempfile.mkdtemp(prefix="media_test_")


def png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, "PNG")
    return buf.getvalue()


@override_settings(MEDIA_ROOT=_MEDIA)
class AttendanceApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.adm = User.objects.create_user("adm", password="x")
        cls.hr = User.objects.create_user("hr", password="x")
        cls.sup = User.objects.create_user("sup", password="x")
        cls.norole = User.objects.create_user("norole", password="x")
        assign_role(cls.adm, ADMINISTRADOR)
        assign_role(cls.hr, RRHH)
        assign_role(cls.sup, SUPERVISOR)
        cls.p1 = Project.objects.create(name="Montego")
        cls.p2 = Project.objects.create(name="Torre Norte")
        cls.p1.supervisors.add(cls.sup)
        cls.emp = Employee.objects.create(full_name="Ana Gomez")
        cls.day = dt.date(2026, 11, 2)  # lunes

    def make(self, project, employee=None, day=None, **kw):
        d = day or self.day
        return Attendance.objects.create(
            project=project, employee=employee or self.emp, date=d,
            check_in=dt.datetime(d.year, d.month, d.day, 7, tzinfo=TZ),
            check_out=dt.datetime(d.year, d.month, d.day, 16, tzinfo=TZ), **kw
        )

    # ── acceso ──
    def test_auth_y_rol(self):
        self.assertEqual(self.client.get(URL).status_code, 401)
        self.client.force_authenticate(self.norole)
        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_supervisor_solo_ve_sus_proyectos(self):
        a1, a2 = self.make(self.p1), self.make(self.p2)
        self.client.force_authenticate(self.sup)
        ids = [r["id"] for r in self.client.get(URL).data["results"]]
        self.assertEqual(ids, [a1.pk])
        self.assertEqual(self.client.get(f"{URL}{a2.pk}/").status_code, 404)
        self.assertEqual(self.client.post(f"{URL}{a2.pk}/review/").status_code, 404)

    def test_backoffice_ve_todo(self):
        self.make(self.p1), self.make(self.p2)
        for u in (self.adm, self.hr):
            self.client.force_authenticate(u)
            self.assertEqual(self.client.get(URL).data["count"], 2)

    # ── contenido y filtros ──
    def test_minutos_netos_en_listado(self):
        self.make(self.p1)
        self.client.force_authenticate(self.adm)
        self.assertEqual(self.client.get(URL).data["results"][0]["worked_minutes"], 480)

    def test_filtros(self):
        self.make(self.p1, needs_review=True)
        self.make(self.p2, day=dt.date(2026, 11, 3))
        self.client.force_authenticate(self.adm)
        self.assertEqual(self.client.get(URL + "?needs_review=true").data["count"], 1)
        self.assertEqual(self.client.get(URL + f"?project={self.p2.pk}").data["count"], 1)
        self.assertEqual(self.client.get(URL + "?date_from=2026-11-03").data["count"], 1)
        self.assertEqual(self.client.get(URL + "?date_to=2026-11-02").data["count"], 1)

    def test_filtro_mal_formado_es_400(self):
        self.client.force_authenticate(self.adm)
        self.assertEqual(self.client.get(URL + "?date_from=ayer").status_code, 400)
        self.assertEqual(self.client.get(URL + "?project=abc").status_code, 400)

    def test_listado_sin_n_mas_1(self):
        ProjectLunchRule.objects.create(weekday=0, start_time=dt.time(12), end_time=dt.time(13))
        for i in range(10):
            e = Employee.objects.create(full_name=f"Persona {chr(65 + i)}")
            self.make(self.p1, employee=e)
        self.client.force_authenticate(self.adm)
        with self.assertNumQueries(5):  # 2 de rol + conteo + jornadas(joins) + reglas de almuerzo
            self.client.get(URL)

    # ── foto protegida ──
    def test_foto_solo_con_permisos(self):
        a = self.make(self.p1)
        a.evidence_photo.save("f.png", ContentFile(png_bytes()))
        self.assertEqual(self.client.get(f"{URL}{a.pk}/photo/").status_code, 401)
        self.client.force_authenticate(self.sup)
        r = self.client.get(f"{URL}{a.pk}/")
        self.assertEqual(r.data["photo_url"], f"{URL}{a.pk}/photo/")
        self.assertNotIn("/media/", str(r.data))
        self.assertEqual(self.client.get(r.data["photo_url"]).status_code, 200)
        other_sup = get_user_model().objects.create_user("sup2", password="x")
        assign_role(other_sup, SUPERVISOR)
        self.client.force_authenticate(other_sup)
        self.assertEqual(self.client.get(f"{URL}{a.pk}/photo/").status_code, 404)

    def test_sin_foto_404(self):
        a = self.make(self.p1)
        self.client.force_authenticate(self.adm)
        self.assertIsNone(self.client.get(f"{URL}{a.pk}/").data["photo_url"])
        self.assertEqual(self.client.get(f"{URL}{a.pk}/photo/").status_code, 404)

    # ── revisión ──
    def test_supervisor_revisa_su_jornada(self):
        a = self.make(self.p1, needs_review=True)
        self.client.force_authenticate(self.sup)
        r = self.client.post(f"{URL}{a.pk}/review/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["needs_review"])
        self.assertEqual(r.data["reviewed_by"], "sup")
        self.assertIsNotNone(r.data["reviewed_at"])

    # ── ajuste ──
    def test_supervisor_no_ajusta(self):
        a = self.make(self.p1)
        self.client.force_authenticate(self.sup)
        r = self.client.post(f"{URL}{a.pk}/adjust/", {"minutes": 300, "reason": "x"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_backoffice_ajusta_con_motivo(self):
        a = self.make(self.p1)
        self.client.force_authenticate(self.hr)
        r = self.client.post(f"{URL}{a.pk}/adjust/", {"minutes": 300, "reason": "Salio temprano"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["worked_minutes"], 300)
        self.assertEqual(r.data["manual_note"], "Salio temprano")

    def test_ajuste_validaciones(self):
        a = self.make(self.p1)
        self.client.force_authenticate(self.adm)
        url = f"{URL}{a.pk}/adjust/"
        self.assertEqual(self.client.post(url, {"minutes": 300, "reason": "  "}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"minutes": 300}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"minutes": -5, "reason": "x"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"minutes": 5000, "reason": "x"}, format="json").status_code, 400)

    def test_ajuste_en_nomina_cerrada_409(self):
        a = self.make(self.p1)
        PayrollPeriod.objects.create(
            start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 8),
            created_by=self.adm, status="CLOSED",
        )
        self.client.force_authenticate(self.adm)
        r = self.client.post(f"{URL}{a.pk}/adjust/", {"minutes": 300, "reason": "x"}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_no_se_escribe_por_post_put_delete(self):
        a = self.make(self.p1)
        self.client.force_authenticate(self.adm)
        self.assertEqual(self.client.post(URL, {}, format="json").status_code, 405)
        self.assertEqual(self.client.put(f"{URL}{a.pk}/", {}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(f"{URL}{a.pk}/").status_code, 405)


class ProjectQrApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.sup = User.objects.create_user("sup", password="x")
        self.other = User.objects.create_user("otro", password="x")
        assign_role(self.sup, SUPERVISOR)
        assign_role(self.other, SUPERVISOR)
        self.project = Project.objects.create(name="Montego")
        self.project.supervisors.add(self.sup)

    def test_png_para_supervisor_de_la_obra(self):
        self.client.force_authenticate(self.sup)
        r = self.client.get(f"/api/projects/{self.project.pk}/qr/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertEqual(r["Cache-Control"], "no-store")
        self.assertTrue(r.content.startswith(b"\x89PNG"))

    def test_enlace_de_marcacion_para_supervisor_de_la_obra(self):
        self.client.force_authenticate(self.sup)
        r = self.client.get(f"/api/projects/{self.project.pk}/qr-link/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f"/marcar/{self.project.slug}?t=", r.data["url"])

    def test_otro_supervisor_no_obtiene_el_enlace(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/projects/{self.project.pk}/qr-link/").status_code, 404)

    def test_otro_supervisor_no_obtiene_el_qr(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/projects/{self.project.pk}/qr/").status_code, 404)

    def test_sin_sesion_401(self):
        self.assertEqual(self.client.get(f"/api/projects/{self.project.pk}/qr/").status_code, 401)
