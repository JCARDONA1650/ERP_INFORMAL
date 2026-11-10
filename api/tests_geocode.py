from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from accounts.roles import ADMINISTRADOR, RRHH, SUPERVISOR, assign_role
from api import geocode

NOMINATIM = [
    {"display_name": "400 South Orange Avenue, Orlando, Florida, United States", "lat": "28.538336", "lon": "-81.379234"},
    {"display_name": "sin coordenadas"},
]


class GeocodeApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.adm = User.objects.create_user("adm", password="x")
        cls.sup = User.objects.create_user("sup", password="x")
        assign_role(cls.adm, ADMINISTRADOR)
        assign_role(cls.sup, SUPERVISOR)

    def setUp(self):
        cache.clear()

    def test_solo_backoffice(self):
        self.assertEqual(self.client.get("/api/geocode/search/?q=orlando").status_code, 401)
        self.client.force_authenticate(self.sup)
        self.assertEqual(self.client.get("/api/geocode/search/?q=orlando").status_code, 403)

    def test_busca_y_normaliza_resultados(self):
        self.client.force_authenticate(self.adm)
        with mock.patch.object(geocode, "_fetch", return_value=NOMINATIM) as fetch:
            r = self.client.get("/api/geocode/search/?q=  400 S Orange   Ave Orlando ")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["results"], [
            {"label": "400 South Orange Avenue, Orlando, Florida, United States", "latitude": 28.538336, "longitude": -81.379234}
        ])
        params = fetch.call_args.args[1]
        self.assertEqual(params["q"], "400 S Orange Ave Orlando")
        self.assertEqual(params["countrycodes"], "us")

    def test_cachea_la_misma_consulta(self):
        self.client.force_authenticate(self.adm)
        with mock.patch.object(geocode, "_fetch", return_value=NOMINATIM) as fetch:
            self.client.get("/api/geocode/search/?q=orlando city hall")
            self.client.get("/api/geocode/search/?q=Orlando City Hall")
        self.assertEqual(fetch.call_count, 1)

    def test_valida_la_consulta(self):
        self.client.force_authenticate(self.adm)
        self.assertEqual(self.client.get("/api/geocode/search/?q=ab").status_code, 400)
        self.assertEqual(self.client.get("/api/geocode/search/?q=" + "x" * 201).status_code, 400)

    def test_servicio_caido_devuelve_502(self):
        self.client.force_authenticate(self.adm)
        with mock.patch.object(geocode, "_fetch", side_effect=geocode.GeocoderUnavailable):
            r = self.client.get("/api/geocode/search/?q=orlando")
        self.assertEqual(r.status_code, 502)
        self.assertIn("servicio de direcciones", r.data["detail"])

    def test_reverse(self):
        self.client.force_authenticate(self.adm)
        with mock.patch.object(geocode, "_fetch", return_value={"display_name": "Orlando City Hall"}):
            r = self.client.get("/api/geocode/reverse/?lat=28.5383&lon=-81.3792")
        self.assertEqual(r.data, {"address": "Orlando City Hall"})
        self.assertEqual(self.client.get("/api/geocode/reverse/?lat=95&lon=0").status_code, 400)
        self.assertEqual(self.client.get("/api/geocode/reverse/").status_code, 400)

    def test_rrhh_tambien_puede(self):
        rrhh = get_user_model().objects.create_user("hr", password="x")
        assign_role(rrhh, RRHH)
        self.client.force_authenticate(rrhh)
        with mock.patch.object(geocode, "_fetch", return_value=[]):
            self.assertEqual(self.client.get("/api/geocode/search/?q=orlando").status_code, 200)
