import io
import tempfile
import uuid

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from attendance.models import Attendance, AttendanceScan
from attendance.qr import make_qr_token
from projects.models import Project, ProjectSite
from workers.models import Employee

_MEDIA = tempfile.mkdtemp(prefix="media_test_")


def png(name="f.png", size=(4, 4)):
    buf = io.BytesIO()
    Image.new("RGB", size).save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=_MEDIA)
class ScanApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.project = Project.objects.create(name="Montego")
        ProjectSite.objects.create(
            project=self.project, latitude="28.500000", longitude="-81.400000", radius_m=150
        )
        self.ana = Employee.objects.create(full_name="Ana Gomez")
        self.inactive = Employee.objects.create(full_name="Inactivo Uno", active=False)
        self.outsider = Employee.objects.create(full_name="Externo Dos")
        self.project.employees.add(self.ana, self.inactive)
        self.token = make_qr_token(self.project)
        self.url = f"/api/scan/{self.project.slug}/?t={self.token}"
        self.ctx = f"/api/scan/{self.project.slug}/context/?t={self.token}"

    def post(self, data=None, url=None, **extra):
        payload = {"employee": self.ana.pk, "action": "in", "photo": png()}
        payload.update(data or {})
        payload.update(extra)
        return self.client.post(url or self.url, payload, format="multipart")

    # ── token y contexto ──
    def test_contexto_lista_solo_activos_asignados(self):
        r = self.client.get(self.ctx)
        self.assertEqual(r.status_code, 200)
        self.assertEqual([e["id"] for e in r.data["employees"]], [self.ana.pk])
        self.assertEqual(r.data["project"]["name"], "Montego")
        self.assertNotIn("qr_secret", str(r.data))

    def test_sin_token_o_token_ajeno_es_403(self):
        other = Project.objects.create(name="Otro")
        self.assertEqual(self.client.get(f"/api/scan/{self.project.slug}/context/").status_code, 403)
        bad = f"/api/scan/{self.project.slug}/context/?t={make_qr_token(other)}"
        self.assertEqual(self.client.get(bad).status_code, 403)
        self.assertEqual(self.post(url=f"/api/scan/{self.project.slug}/").status_code, 403)

    def test_proyecto_inexistente_o_inactivo_404(self):
        self.assertEqual(self.client.get(f"/api/scan/no-existe/context/?t=x").status_code, 404)
        self.project.active = False
        self.project.save()
        self.assertEqual(self.client.get(self.ctx).status_code, 404)

    # ── marcación ──
    def test_ingreso_y_salida(self):
        r = self.post()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(Attendance.objects.get().check_in)
        r = self.post({"action": "out", "photo": png("g.png")})
        self.assertEqual(r.status_code, 201)
        self.assertIsNotNone(Attendance.objects.get().check_out)

    def test_foto_obligatoria_y_debe_ser_imagen(self):
        r = self.client.post(self.url, {"employee": self.ana.pk, "action": "in"}, format="multipart")
        self.assertEqual(r.status_code, 400)
        fake = SimpleUploadedFile("x.png", b"no soy una imagen", content_type="image/png")
        self.assertEqual(self.post(photo=fake).status_code, 400)
        self.assertEqual(AttendanceScan.objects.count(), 0)

    def test_foto_muy_grande(self):
        from unittest import mock

        with mock.patch("api.scan.MAX_PHOTO_BYTES", 10):  # cualquier PNG real supera 10 bytes
            r = self.post()
        self.assertEqual(r.status_code, 400)
        self.assertIn("5 MB", str(r.data))
        self.assertEqual(AttendanceScan.objects.count(), 0)

    def test_trabajador_no_asignado_o_inactivo(self):
        self.assertEqual(self.post({"employee": self.outsider.pk}).status_code, 400)
        self.assertEqual(self.post({"employee": self.inactive.pk}).status_code, 400)

    def test_salida_sin_ingreso_409(self):
        r = self.post({"action": "out"})
        self.assertEqual(r.status_code, 409)
        self.assertIn("ingreso", r.data["detail"])

    def test_reintento_offline_no_duplica(self):
        uid = str(uuid.uuid4())
        self.assertEqual(self.post({"client_uuid": uid}).status_code, 201)
        r = self.post({"client_uuid": uid, "photo": png("otra.png")})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["duplicate"])
        self.assertEqual(AttendanceScan.objects.count(), 1)

    def test_el_cliente_no_puede_declararse_manual_o_biometrico(self):
        self.post({"source": "manual"})
        self.assertEqual(AttendanceScan.objects.get().source, "qr")

    def test_fuera_de_zona_marca_revision_sin_bloquear(self):
        r = self.post({"latitude": 28.52, "longitude": -81.4})
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.data["in_zone"])
        self.assertTrue(Attendance.objects.get().needs_review)

    def test_dentro_de_zona(self):
        r = self.post({"latitude": 28.5005, "longitude": -81.4})
        self.assertTrue(r.data["in_zone"])
        self.assertFalse(Attendance.objects.get().needs_review)

    def test_coordenadas_invalidas(self):
        self.assertEqual(self.post({"latitude": 95, "longitude": 0}).status_code, 400)
        self.assertEqual(self.post({"latitude": 28.5}).status_code, 400)  # una sola

    def test_limite_de_peticiones(self):
        codes = {self.client.get(self.ctx).status_code for _ in range(125)}
        self.assertIn(429, codes)
