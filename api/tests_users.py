from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.roles import ADMINISTRADOR, RRHH, SUPERVISOR, assign_role
from workers.models import Employee


class SupervisorListTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.adm = User.objects.create_user("adm", password="x")
        cls.hr = User.objects.create_user("hr", password="x")
        cls.sup = User.objects.create_user("sup", password="x", first_name="Sara", last_name="Sup")
        cls.inactive = User.objects.create_user("viejo", password="x", is_active=False)
        cls.plain = User.objects.create_user("plain", password="x")
        assign_role(cls.adm, ADMINISTRADOR)
        assign_role(cls.hr, RRHH)
        assign_role(cls.sup, SUPERVISOR)
        assign_role(cls.inactive, SUPERVISOR)

    def test_lista_solo_supervisores_activos(self):
        self.client.force_authenticate(self.adm)
        r = self.client.get("/api/users/supervisors/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, [{"id": self.sup.pk, "username": "sup", "full_name": "Sara Sup"}])
        self.assertNotIn("password", str(r.data))

    def test_backoffice_si_supervisor_y_anonimo_no(self):
        for user, code in ((self.hr, 200), (self.sup, 403), (self.plain, 403)):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get("/api/users/supervisors/").status_code, code)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/users/supervisors/").status_code, 401)


class PaginationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.adm = get_user_model().objects.create_user("adm", password="x")
        assign_role(cls.adm, ADMINISTRADOR)
        Employee.objects.bulk_create([Employee(full_name=f"Persona {chr(65 + i % 26)}{chr(65 + i // 26)}") for i in range(60)])

    def test_por_defecto_25(self):
        self.client.force_authenticate(self.adm)
        r = self.client.get("/api/employees/")
        self.assertEqual((r.data["count"], len(r.data["results"])), (60, 25))

    def test_page_size_configurable_con_tope(self):
        self.client.force_authenticate(self.adm)
        self.assertEqual(len(self.client.get("/api/employees/?page_size=100").data["results"]), 60)
        self.assertEqual(len(self.client.get("/api/employees/?page_size=10").data["results"]), 10)
        # por encima del máximo (200) se recorta; valores inválidos usan el defecto
        self.assertLessEqual(len(self.client.get("/api/employees/?page_size=99999").data["results"]), 200)
        self.assertEqual(len(self.client.get("/api/employees/?page_size=abc").data["results"]), 25)
