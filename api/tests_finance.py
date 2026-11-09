import datetime as dt
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import AuditLog
from accounts.roles import ADMINISTRADOR, RRHH, SUPERVISOR, assign_role
from finance.models import ProjectExpense, ProjectIncome
from projects.models import Project

INC, EXP = "/api/finance/incomes/", "/api/finance/expenses/"


class FinanceApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.adm = User.objects.create_user("adm", password="x")
        cls.hr = User.objects.create_user("hr", password="x")
        cls.sup = User.objects.create_user("sup", password="x")
        assign_role(cls.adm, ADMINISTRADOR)
        assign_role(cls.hr, RRHH)
        assign_role(cls.sup, SUPERVISOR)
        cls.project = Project.objects.create(name="Montego", contract_value="1000", contract_currency="USD")
        cls.other = Project.objects.create(name="Otro")

    def income(self, **kw):
        data = {"project": self.project.pk, "date": "2026-11-02", "amount": "400.00", "description": "Anticipo"}
        data.update(kw)
        return self.client.post(INC, data, format="json")

    def expense(self, **kw):
        data = {"project": self.project.pk, "date": "2026-11-03", "amount": "150.00", "category": "materials"}
        data.update(kw)
        return self.client.post(EXP, data, format="json")

    # ── permisos ──
    def test_solo_administrador(self):
        self.assertEqual(self.client.get(INC).status_code, 401)
        for user in (self.hr, self.sup):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(INC).status_code, 403)
            self.assertEqual(self.client.get(EXP).status_code, 403)
            self.assertEqual(self.client.get(f"/api/projects/{self.project.pk}/finance/").status_code, 403)
            self.assertEqual(self.income().status_code, 403)

    # ── crear ──
    def test_crear_ingreso_con_moneda_del_contrato_y_auditoria(self):
        self.client.force_authenticate(self.adm)
        r = self.income()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["currency"], "USD")
        self.assertEqual(r.data["created_by"], "adm")
        self.assertTrue(AuditLog.objects.filter(action="crear", entity="ProjectIncome").exists())

    def test_crear_gasto_con_categoria_y_moneda_propia(self):
        self.client.force_authenticate(self.adm)
        r = self.expense(currency="COP", category="transport")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["currency"], r.data["category"]), ("COP", "transport"))

    def test_validaciones_son_400(self):
        self.client.force_authenticate(self.adm)
        self.assertEqual(self.income(amount="-5").status_code, 400)
        self.assertEqual(self.income(project=9999).status_code, 400)
        self.assertEqual(self.income(currency="EUR").status_code, 400)
        self.assertEqual(self.expense(category="inventada").status_code, 400)
        self.assertEqual(ProjectIncome.objects.count(), 0)

    # ── editar / no borrar ──
    def test_editar_audita_el_cambio(self):
        self.client.force_authenticate(self.adm)
        mid = self.income().data["id"]
        r = self.client.patch(f"{INC}{mid}/", {"amount": "450.00"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(r.data["amount"]), Decimal("450.00"))
        log = AuditLog.objects.get(action="editar")
        self.assertIn("400.00 -> 450.00", log.detail)

    def test_editar_sin_cambios_no_audita(self):
        self.client.force_authenticate(self.adm)
        mid = self.income().data["id"]
        self.client.patch(f"{INC}{mid}/", {"amount": "400.00"}, format="json")
        self.assertFalse(AuditLog.objects.filter(action="editar").exists())

    def test_no_se_mueve_a_otro_proyecto(self):
        self.client.force_authenticate(self.adm)
        mid = self.income().data["id"]
        r = self.client.patch(f"{INC}{mid}/", {"project": self.other.pk}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(ProjectIncome.objects.get(pk=mid).project, self.project)

    def test_no_se_puede_borrar(self):
        self.client.force_authenticate(self.adm)
        mid = self.income().data["id"]
        self.assertEqual(self.client.delete(f"{INC}{mid}/").status_code, 405)
        self.assertTrue(ProjectIncome.objects.filter(pk=mid).exists())

    # ── filtros ──
    def test_filtros(self):
        self.client.force_authenticate(self.adm)
        self.expense(category="materials")
        self.expense(category="meals", date="2026-12-01")
        self.expense(project=self.other.pk, category="meals")
        self.assertEqual(self.client.get(EXP).data["count"], 3)
        self.assertEqual(self.client.get(EXP + f"?project={self.project.pk}").data["count"], 2)
        self.assertEqual(self.client.get(EXP + "?category=meals").data["count"], 2)
        self.assertEqual(self.client.get(EXP + "?date_from=2026-12-01").data["count"], 1)
        self.assertEqual(self.client.get(EXP + "?date_from=ayer").status_code, 400)

    # ── resumen ──
    def test_resumen_por_moneda_y_categoria(self):
        self.client.force_authenticate(self.adm)
        self.income(amount="400")
        self.income(amount="100", currency="COP")
        self.expense(amount="150", category="materials")
        self.expense(amount="50", category="meals")
        r = self.client.get(f"/api/projects/{self.project.pk}/finance/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["incomes"], {"USD": "400.00", "COP": "100.00"})
        self.assertEqual(r.data["balance"]["USD"], "200.00")
        self.assertEqual(r.data["contract"]["billed_pct"], "40.0")
        cats = {(c["category"], c["currency"]): c["total"] for c in r.data["expenses_by_category"]}
        self.assertEqual(cats[("materials", "USD")], "150.00")

    def test_resumen_con_rango_y_errores(self):
        self.client.force_authenticate(self.adm)
        self.income(amount="400")
        self.income(amount="50", date="2026-12-10")
        url = f"/api/projects/{self.project.pk}/finance/"
        self.assertEqual(self.client.get(url + "?date_to=2026-11-30").data["incomes"]["USD"], "400.00")
        self.assertEqual(self.client.get(url + "?date_from=x").status_code, 400)
        self.assertEqual(self.client.get("/api/projects/9999/finance/").status_code, 404)

    def test_resumen_proyecto_sin_contrato(self):
        self.client.force_authenticate(self.adm)
        r = self.client.get(f"/api/projects/{self.other.pk}/finance/")
        self.assertIsNone(r.data["contract"]["billed_pct"])
