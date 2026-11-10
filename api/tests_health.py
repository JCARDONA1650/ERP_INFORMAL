from unittest import mock

from django.db.utils import OperationalError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


class HealthTests(TestCase):
    def test_ok_sin_autenticacion(self):
        r = APIClient().get("/api/health/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, {"status": "ok"})

    def test_sin_limite_de_peticiones(self):
        client = APIClient()
        self.assertTrue(all(client.get("/api/health/").status_code == 200 for _ in range(40)))

    def test_503_si_la_base_de_datos_falla_y_no_filtra_el_error(self):
        with mock.patch("api.views.connection.cursor", side_effect=OperationalError("password=secreta")):
            r = APIClient().get("/api/health/")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.data, {"status": "error"})
        self.assertNotIn("secreta", str(r.content))


@override_settings(SECURE_SSL_REDIRECT=True)
class SslRedirectTests(TestCase):
    def test_redirige_a_https_salvo_el_healthcheck(self):
        client = APIClient()
        self.assertEqual(client.get("/api/health/").status_code, 200)  # exento
        r = client.get("/api/auth/me/")
        self.assertEqual(r.status_code, 301)
        self.assertTrue(r["Location"].startswith("https://"))

    def test_con_cabecera_del_proxy_no_redirige(self):
        r = APIClient().get("/api/auth/me/", secure=True)
        self.assertEqual(r.status_code, 401)  # llegó a la vista (sin token), no se redirigió
