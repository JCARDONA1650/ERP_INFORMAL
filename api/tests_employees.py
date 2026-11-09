import datetime as dt
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.roles import ADMINISTRADOR, RRHH, SUPERVISOR, assign_role
from projects.models import Project
from workers.models import Employee

URL = "/api/employees/"


class EmployeeApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.adm = User.objects.create_user("adm", password="x")
        cls.hr = User.objects.create_user("hr", password="x")
        cls.sup = User.objects.create_user("sup", password="x")
        cls.other = User.objects.create_user("otro", password="x")  # sin rol
        assign_role(cls.adm, ADMINISTRADOR)
        assign_role(cls.hr, RRHH)
        assign_role(cls.sup, SUPERVISOR)
        cls.project = Project.objects.create(name="Montego")
        cls.project.supervisors.add(cls.sup)
        cls.mine = Employee.objects.create(full_name="Ana Gomez", document_id="a-1", hourly_rate="20")
        cls.not_mine = Employee.objects.create(full_name="Beto Ruiz", document_id="b-2")
        cls.project.employees.add(cls.mine)

    def test_sin_token_401(self):
        self.assertEqual(self.client.get(URL).status_code, 401)

    def test_usuario_sin_rol_403(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_backoffice_ve_todos(self):
        for u in (self.adm, self.hr):
            self.client.force_authenticate(u)
            self.assertEqual(self.client.get(URL).data["count"], 2)

    def test_supervisor_solo_ve_los_de_sus_proyectos_y_no_escribe(self):
        self.client.force_authenticate(self.sup)
        r = self.client.get(URL)
        self.assertEqual([e["id"] for e in r.data["results"]], [self.mine.pk])
        self.assertEqual(self.client.get(f"{URL}{self.not_mine.pk}/").status_code, 404)
        self.assertEqual(self.client.post(URL, {"full_name": "Nuevo"}).status_code, 403)
        self.assertEqual(self.client.patch(f"{URL}{self.mine.pk}/", {"position": "x"}).status_code, 403)

    def test_crear_con_tarifa_inicial(self):
        self.client.force_authenticate(self.adm)
        r = self.client.post(URL, {"full_name": "  Carlos   Diaz ", "initial_rate": "25.50"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["full_name"], "Carlos Diaz")
        self.assertEqual(Decimal(r.data["hourly_rate"]), Decimal("25.50"))
        self.assertEqual(Employee.objects.get(pk=r.data["id"]).rate_history.count(), 1)

    def test_nombre_repetido_pide_confirmacion(self):
        self.client.force_authenticate(self.hr)
        r = self.client.post(URL, {"full_name": "ana  gomez"}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["similar"][0]["id"], self.mine.pk)
        r = self.client.post(URL, {"full_name": "ana gomez", "confirm_duplicate": True}, format="json")
        self.assertEqual(r.status_code, 201)

    def test_validaciones_devuelven_400_no_500(self):
        self.client.force_authenticate(self.adm)
        self.assertEqual(self.client.post(URL, {"full_name": "Pedro123"}, format="json").status_code, 400)
        dup = self.client.post(URL, {"full_name": "Otro", "document_id": "A-1"}, format="json")
        self.assertEqual(dup.status_code, 400)

    def test_no_se_edita_la_tarifa_directamente(self):
        self.client.force_authenticate(self.adm)
        r = self.client.patch(f"{URL}{self.mine.pk}/", {"hourly_rate": "99", "position": "Oficial"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.hourly_rate, Decimal("20.00"))
        self.assertEqual(self.mine.position, "Oficial")
        r = self.client.patch(f"{URL}{self.mine.pk}/", {"initial_rate": "5"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_cambio_de_tarifa_con_vigencia_e_historial(self):
        self.client.force_authenticate(self.adm)
        url = f"{URL}{self.mine.pk}/rates/"
        r = self.client.post(url, {"rate": "30", "effective_from": "2026-01-01"}, format="json")
        self.assertEqual(r.status_code, 201)
        r = self.client.post(url, {"rate": "-1", "effective_from": "2026-02-01"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(len(self.client.get(url).data), 1)
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.hourly_rate, Decimal("30.00"))

    def test_supervisor_no_ve_ni_cambia_tarifas(self):
        self.client.force_authenticate(self.sup)
        self.assertEqual(self.client.get(f"{URL}{self.mine.pk}/rates/").status_code, 403)

    def test_desactivar_y_filtrar(self):
        self.client.force_authenticate(self.adm)
        self.assertEqual(self.client.post(f"{URL}{self.mine.pk}/deactivate/").data["active"], False)
        self.assertEqual(self.client.get(URL + "?active=true").data["count"], 1)
        self.assertEqual(self.client.get(URL + "?active=false").data["count"], 1)
        self.client.post(f"{URL}{self.mine.pk}/activate/")
        self.assertTrue(Employee.objects.get(pk=self.mine.pk).active)

    def test_busqueda(self):
        self.client.force_authenticate(self.adm)
        self.assertEqual(self.client.get(URL + "?search=B-2").data["count"], 1)
        self.assertEqual(self.client.get(URL + "?search=gomez").data["count"], 1)

    def test_no_existe_delete(self):
        self.client.force_authenticate(self.adm)
        self.assertEqual(self.client.delete(f"{URL}{self.mine.pk}/").status_code, 405)
