import datetime as dt

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.roles import ADMINISTRADOR, RRHH, SUPERVISOR, assign_role
from finance.models import ProjectExpense, ProjectIncome
from projects.models import Project

URL = "/api/finance/overview/"


def d(day):
    return dt.date(2026, 11, day)


class FinanceOverviewTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.adm = User.objects.create_user("adm", password="x")
        cls.hr = User.objects.create_user("hr", password="x")
        cls.sup = User.objects.create_user("sup", password="x")
        assign_role(cls.adm, ADMINISTRADOR)
        assign_role(cls.hr, RRHH)
        assign_role(cls.sup, SUPERVISOR)
        cls.a = Project.objects.create(name="Alfa", contract_value="1000", contract_currency="USD")
        cls.b = Project.objects.create(name="Beta", contract_value="0", contract_currency="USD")
        cls.c = Project.objects.create(name="Vacio")
        ProjectIncome.objects.create(project=cls.a, date=d(2), amount="500", currency="USD", created_by=cls.adm)
        ProjectIncome.objects.create(project=cls.b, date=d(4), amount="200", currency="USD", created_by=cls.adm)
        ProjectIncome.objects.create(project=cls.b, date=d(4), amount="1000000", currency="COP", created_by=cls.adm)
        ProjectExpense.objects.create(project=cls.a, date=d(2), amount="120", currency="USD", created_by=cls.adm, category="materials")
        ProjectExpense.objects.create(project=cls.a, date=d(5), amount="80", currency="USD", created_by=cls.adm, category="meals")
        ProjectExpense.objects.create(project=cls.b, date=d(9), amount="50", currency="USD", created_by=cls.adm, category="materials")

    def setUp(self):
        self.client.force_authenticate(self.adm)

    def test_solo_el_administrador_accede(self):
        for user in (self.hr, self.sup):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(URL).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(URL).status_code, 401)

    def test_global_totaliza_todos_los_proyectos_por_moneda(self):
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data["scope"])
        self.assertEqual(r.data["currencies"], ["COP", "USD"])
        self.assertEqual(r.data["totals"]["incomes"], {"USD": "700.00", "COP": "1000000.00"})
        self.assertEqual(r.data["totals"]["expenses"], {"USD": "250.00"})
        self.assertEqual(r.data["totals"]["balance"]["USD"], "450.00")
        self.assertEqual([p["project"]["name"] for p in r.data["projects"]], ["Alfa", "Beta", "Vacio"])

    def test_detalle_por_proyecto_y_facturado(self):
        rows = {p["project"]["name"]: p for p in self.client.get(URL).data["projects"]}
        self.assertEqual(rows["Alfa"]["balance"]["USD"], "300.00")
        self.assertEqual(rows["Alfa"]["contract"]["billed_pct"], "50.0")
        self.assertIsNone(rows["Beta"]["contract"]["billed_pct"])
        self.assertEqual(rows["Vacio"]["incomes"], {})

    def test_un_proyecto_filtra_totales_y_serie(self):
        r = self.client.get(URL, {"project": self.a.pk})
        self.assertEqual(r.data["scope"], {"id": self.a.pk, "name": "Alfa"})
        self.assertEqual([p["project"]["name"] for p in r.data["projects"]], ["Alfa"])
        self.assertEqual(r.data["totals"]["incomes"], {"USD": "500.00"})
        self.assertEqual(r.data["series"]["points"][-1]["cumulative"], "300.00")

    def test_rango_de_fechas(self):
        r = self.client.get(URL, {"date_from": "2026-11-04", "date_to": "2026-11-30"})
        self.assertEqual(r.data["totals"]["incomes"]["USD"], "200.00")
        self.assertEqual(r.data["totals"]["expenses"]["USD"], "130.00")

    def test_serie_diaria_rellena_dias_sin_movimientos_y_acumula(self):
        s = self.client.get(URL, {"group": "day"}).data["series"]
        self.assertEqual(s["currency"], "USD")  # USD por defecto
        self.assertEqual(s["group"], "day")
        by = {p["period"]: p for p in s["points"]}
        self.assertEqual(len(s["points"]), 8)  # del 2 al 9
        self.assertEqual(by["2026-11-02"]["income"], "500.00")
        self.assertEqual(by["2026-11-02"]["net"], "380.00")
        self.assertEqual(by["2026-11-03"]["net"], "0.00")  # día vacío
        self.assertEqual(by["2026-11-03"]["cumulative"], "380.00")
        self.assertEqual(s["points"][-1]["cumulative"], "450.00")

    def test_serie_semanal_y_mensual(self):
        weekly = self.client.get(URL, {"group": "week"}).data["series"]["points"]
        self.assertEqual([p["period"] for p in weekly], ["2026-11-02", "2026-11-09"])  # lunes
        self.assertEqual(weekly[0]["income"], "700.00")
        monthly = self.client.get(URL, {"group": "month"}).data["series"]["points"]
        self.assertEqual([p["period"] for p in monthly], ["2026-11-01"])
        self.assertEqual(monthly[0]["cumulative"], "450.00")

    def test_grupo_automatico_segun_el_rango(self):
        self.assertEqual(self.client.get(URL).data["series"]["group"], "day")
        wide = self.client.get(URL, {"date_from": "2026-01-01", "date_to": "2026-12-31"}).data["series"]["group"]
        self.assertEqual(wide, "month")

    def test_serie_en_otra_moneda(self):
        s = self.client.get(URL, {"currency": "COP"}).data["series"]
        self.assertEqual(s["currency"], "COP")
        self.assertEqual(s["points"][-1]["cumulative"], "1000000.00")

    def test_sin_movimientos_devuelve_serie_vacia(self):
        ProjectIncome.objects.all().delete()
        ProjectExpense.objects.all().delete()
        r = self.client.get(URL)
        self.assertEqual(r.data["series"], {"currency": None, "group": "day", "points": []})
        self.assertEqual(r.data["currencies"], [])

    def test_gastos_por_categoria(self):
        cats = {(c["category"], c["currency"]): c["total"] for c in self.client.get(URL).data["expenses_by_category"]}
        self.assertEqual(cats[("materials", "USD")], "170.00")

    def test_validaciones(self):
        self.assertEqual(self.client.get(URL, {"project": "abc"}).status_code, 400)
        self.assertEqual(self.client.get(URL, {"project": 9999}).status_code, 404)
        self.assertEqual(self.client.get(URL, {"date_from": "mañana"}).status_code, 400)
        self.assertEqual(self.client.get(URL, {"date_from": "2026-12-01", "date_to": "2026-11-01"}).status_code, 400)
        self.assertEqual(self.client.get(URL, {"group": "year"}).status_code, 400)

    def test_consultas_constantes(self):
        for i in range(6):
            Project.objects.create(name=f"P{i}")
        with self.assertNumQueries(11):  # sin N+1: no crece con la cantidad de proyectos
            self.client.get(URL)
