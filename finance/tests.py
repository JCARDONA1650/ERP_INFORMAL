import datetime as dt
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from projects.models import Project

from .models import ProjectExpense, ProjectIncome
from .services import expenses_by_category, project_summary


class FinanceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("admin", password="x")
        self.project = Project.objects.create(
            name="Montego", contract_value="1000", contract_currency="USD"
        )
        self.day = dt.date(2026, 11, 2)

    def income(self, amount, **kw):
        return ProjectIncome.objects.create(
            project=self.project, date=self.day, amount=amount, created_by=self.user, **kw
        )

    def expense(self, amount, **kw):
        return ProjectExpense.objects.create(
            project=self.project, date=self.day, amount=amount, created_by=self.user, **kw
        )

    def test_moneda_por_defecto_es_la_del_contrato(self):
        self.assertEqual(self.income("100").currency, "USD")
        self.project.contract_currency = "COP"
        self.project.save()
        self.assertEqual(self.expense("50").currency, "COP")

    def test_monto_negativo_invalido(self):
        with self.assertRaises(ValidationError):
            self.income("-1")

    def test_resumen_por_moneda_sin_convertir(self):
        self.income("400")
        self.income("100", currency="COP")
        self.expense("150", category="materials")
        s = project_summary(self.project)
        self.assertEqual(s["incomes"], {"USD": Decimal("400.00"), "COP": Decimal("100.00")})
        self.assertEqual(s["balance"]["USD"], Decimal("250.00"))
        self.assertEqual(s["balance"]["COP"], Decimal("100.00"))
        self.assertEqual(s["billed_pct"], Decimal("40.0"))

    def test_filtro_por_fechas(self):
        self.income("400")
        ProjectIncome.objects.create(
            project=self.project, date=dt.date(2026, 12, 1), amount="50", created_by=self.user
        )
        s = project_summary(self.project, date_to=dt.date(2026, 11, 30))
        self.assertEqual(s["incomes"]["USD"], Decimal("400.00"))

    def test_proyecto_sin_contrato_no_calcula_porcentaje(self):
        p = Project.objects.create(name="Sin contrato")
        self.assertIsNone(project_summary(p)["billed_pct"])

    def test_gastos_por_categoria(self):
        self.expense("10", category="meals")
        self.expense("5", category="meals")
        self.expense("20", category="tools")
        r = expenses_by_category(self.project)
        self.assertEqual(r[("meals", "USD")], Decimal("15.00"))
        self.assertEqual(r[("tools", "USD")], Decimal("20.00"))
