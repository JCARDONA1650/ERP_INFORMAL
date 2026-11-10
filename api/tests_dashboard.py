from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.roles import ADMINISTRADOR, RRHH, SUPERVISOR, assign_role
from attendance.services import register_scan
from finance.models import ProjectIncome
from projects.models import Project, ProjectSite
from workers.models import Employee

URL = "/api/dashboard/"


class DashboardApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.adm = User.objects.create_user("adm", password="x")
        cls.hr = User.objects.create_user("hr", password="x")
        cls.sup = User.objects.create_user("sup", password="x")
        cls.sup2 = User.objects.create_user("sup2", password="x")
        cls.none = User.objects.create_user("none", password="x")
        assign_role(cls.adm, ADMINISTRADOR)
        assign_role(cls.hr, RRHH)
        assign_role(cls.sup, SUPERVISOR)
        assign_role(cls.sup2, SUPERVISOR)

        cls.p1 = Project.objects.create(name="Montego", contract_value="1000")
        cls.p2 = Project.objects.create(name="Torre Norte")
        cls.p1.supervisors.add(cls.sup)
        cls.p2.supervisors.add(cls.sup2)
        ProjectSite.objects.create(
            project=cls.p1, latitude="28.5", longitude="-81.4", radius_m=150, out_of_zone_policy="review"
        )
        ana = Employee.objects.create(full_name="Ana Gomez")
        beto = Employee.objects.create(full_name="Beto Ruiz")
        cls.p1.employees.add(ana)
        cls.p2.employees.add(beto)
        register_scan(cls.p1, ana, "in", latitude=28.5005, longitude=-81.4)  # dentro
        register_scan(cls.p1, beto, "in", latitude=28.52, longitude=-81.4)   # fuera -> revisión
        register_scan(cls.p2, beto, "in")
        ProjectIncome.objects.create(project=cls.p1, amount="500", date="2026-01-05", created_by=cls.adm)

    def test_requiere_rol(self):
        self.assertEqual(self.client.get(URL).status_code, 401)
        self.client.force_authenticate(self.none)
        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_administrador_ve_todo_y_finanzas(self):
        self.client.force_authenticate(self.adm)
        d = self.client.get(URL).data
        self.assertEqual(d["role_scope"], "backoffice")
        self.assertEqual(len(d["projects"]), 2)
        self.assertEqual(d["attendance"]["present_today"], 3)
        self.assertEqual(d["attendance"]["out_of_zone_today"], 1)
        self.assertEqual(d["attendance"]["pending_review"], 1)
        self.assertEqual(d["workers"]["active"], 2)
        self.assertEqual(d["finance"]["incomes"], {"USD": "500.00"})
        self.assertEqual(len(d["marks_today"]), 2)  # solo marcaciones con ubicación
        self.assertEqual(len(d["hours_last_days"]), 7)

    def test_rrhh_ve_nomina_pero_no_finanzas(self):
        self.client.force_authenticate(self.hr)
        d = self.client.get(URL).data
        self.assertIn("payroll", d)
        self.assertNotIn("finance", d)

    def test_supervisor_solo_ve_sus_proyectos(self):
        self.client.force_authenticate(self.sup)
        d = self.client.get(URL).data
        self.assertEqual(d["role_scope"], "supervisor")
        self.assertEqual([p["name"] for p in d["projects"]], ["Montego"])
        self.assertEqual(d["attendance"]["present_today"], 2)
        self.assertEqual({m["project"] for m in d["marks_today"]}, {"Montego"})
        self.assertNotIn("finance", d)
        self.assertNotIn("workers", d)
        self.client.force_authenticate(self.sup2)
        self.assertEqual([p["name"] for p in self.client.get(URL).data["projects"]], ["Torre Norte"])

    def test_proyectos_con_conteos_y_zona(self):
        self.client.force_authenticate(self.adm)
        rows = {p["name"]: p for p in self.client.get(URL).data["projects"]}
        self.assertEqual(rows["Montego"]["present_today"], 2)
        self.assertEqual(rows["Montego"]["pending_review"], 1)
        self.assertEqual(rows["Montego"]["site"]["radius_m"], 150)
        self.assertIsNone(rows["Torre Norte"]["site"])

    def test_consultas_constantes(self):
        self.client.force_authenticate(self.adm)
        with self.assertNumQueries(18):  # no crece con la cantidad de proyectos/jornadas
            self.client.get(URL)
