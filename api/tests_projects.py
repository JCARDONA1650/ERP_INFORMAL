from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.roles import ADMINISTRADOR, RRHH, SUPERVISOR, assign_role
from projects.models import Project, ProjectSite
from workers.models import Employee

URL = "/api/projects/"


class ProjectApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.adm = User.objects.create_user("adm", password="x")
        cls.hr = User.objects.create_user("hr", password="x")
        cls.sup = User.objects.create_user("sup", password="x")
        cls.sup2 = User.objects.create_user("sup2", password="x")
        cls.norole = User.objects.create_user("norole", password="x")
        assign_role(cls.adm, ADMINISTRADOR)
        assign_role(cls.hr, RRHH)
        assign_role(cls.sup, SUPERVISOR)
        assign_role(cls.sup2, SUPERVISOR)
        cls.emp = Employee.objects.create(full_name="Ana Gomez")
        cls.p1 = Project.objects.create(name="Montego", contract_value="1000")
        cls.p2 = Project.objects.create(name="Torre Norte")
        cls.p1.supervisors.add(cls.sup)
        cls.p1.employees.add(cls.emp)
        ProjectSite.objects.create(project=cls.p1, latitude="28.5", longitude="-81.4", radius_m=200)

    def test_autenticacion_y_rol(self):
        self.assertEqual(self.client.get(URL).status_code, 401)
        self.client.force_authenticate(self.norole)
        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_backoffice_ve_todos_y_supervisor_solo_los_suyos(self):
        self.client.force_authenticate(self.hr)
        self.assertEqual(self.client.get(URL).data["count"], 2)
        self.client.force_authenticate(self.sup)
        r = self.client.get(URL)
        self.assertEqual([p["id"] for p in r.data["results"]], [self.p1.pk])
        self.assertEqual(self.client.get(f"{URL}{self.p2.pk}/").status_code, 404)

    def test_supervisor_no_escribe(self):
        self.client.force_authenticate(self.sup)
        self.assertEqual(self.client.post(URL, {"name": "X"}, format="json").status_code, 403)
        self.assertEqual(self.client.patch(f"{URL}{self.p1.pk}/", {"active": False}, format="json").status_code, 403)

    def test_qr_secret_no_se_expone(self):
        self.client.force_authenticate(self.adm)
        r = self.client.get(f"{URL}{self.p1.pk}/")
        self.assertNotIn("qr_secret", r.data)
        self.assertNotIn(self.p1.qr_secret, str(r.data))

    def test_representacion_con_y_sin_zona(self):
        self.client.force_authenticate(self.adm)
        self.assertEqual(self.client.get(f"{URL}{self.p1.pk}/").data["site"]["radius_m"], 200)
        self.assertIsNone(self.client.get(f"{URL}{self.p2.pk}/").data["site"])

    def test_crear_con_zona_supervisores_y_trabajadores(self):
        self.client.force_authenticate(self.adm)
        payload = {
            "name": "Nuevo Proyecto", "contract_value": "5000", "contract_currency": "COP",
            "site": {"latitude": "28.500000", "longitude": "-81.400000", "radius_m": 150},
            "supervisors": [self.sup2.pk], "employees": [self.emp.pk],
        }
        r = self.client.post(URL, payload, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        p = Project.objects.get(pk=r.data["id"])
        self.assertEqual(p.slug, "nuevo-proyecto")
        self.assertEqual(list(p.supervisors.all()), [self.sup2])
        self.assertEqual(p.site.radius_m, 150)

    def test_supervisor_debe_tener_rol(self):
        self.client.force_authenticate(self.adm)
        r = self.client.post(URL, {"name": "Y", "supervisors": [self.norole.pk]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Project.objects.filter(name="Y").exists())

    def test_validaciones_son_400(self):
        self.client.force_authenticate(self.adm)
        self.assertEqual(self.client.post(URL, {"name": "Montego"}, format="json").status_code, 400)
        bad = {"name": "Z", "site": {"latitude": "95", "longitude": "0", "radius_m": 100}}
        self.assertEqual(self.client.post(URL, bad, format="json").status_code, 400)
        self.assertFalse(Project.objects.filter(name="Z").exists())  # transacción atómica

    def test_patch_parcial_conserva_zona_y_actualiza_relaciones(self):
        self.client.force_authenticate(self.adm)
        r = self.client.patch(f"{URL}{self.p1.pk}/", {"supervisors": [self.sup2.pk]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.p1.refresh_from_db()
        self.assertEqual(list(self.p1.supervisors.all()), [self.sup2])
        self.assertEqual(self.p1.site.radius_m, 200)
        self.assertEqual(list(self.p1.employees.all()), [self.emp])

    def test_actualizar_y_quitar_zona(self):
        self.client.force_authenticate(self.adm)
        r = self.client.patch(f"{URL}{self.p1.pk}/", {"site": {"radius_m": 300, "latitude": "28.5", "longitude": "-81.4"}}, format="json")
        self.assertEqual(r.data["site"]["radius_m"], 300)
        r = self.client.patch(f"{URL}{self.p1.pk}/", {"site": None}, format="json")
        self.assertIsNone(r.data["site"])
        self.assertFalse(ProjectSite.objects.filter(project=self.p1).exists())

    def test_desactivar_y_filtrar_sin_borrar(self):
        self.client.force_authenticate(self.adm)
        self.client.patch(f"{URL}{self.p2.pk}/", {"active": False}, format="json")
        self.assertEqual(self.client.get(URL + "?active=true").data["count"], 1)
        self.assertEqual(self.client.delete(f"{URL}{self.p2.pk}/").status_code, 405)

    def test_listado_sin_n_mas_1(self):
        User = get_user_model()
        for i in range(8):
            p = Project.objects.create(name=f"Obra {i}")
            p.supervisors.add(self.sup2)
            p.employees.add(self.emp)
            ProjectSite.objects.create(project=p, latitude="28.5", longitude="-81.4")
        self.client.force_authenticate(self.adm)
        with self.assertNumQueries(6):  # 2 chequeos de rol + conteo + proyectos(+site) + supervisores + trabajadores; constante
            self.client.get(URL)
