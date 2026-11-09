import datetime as dt
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from projects.models import Project
from workers.models import Employee

from .models import PayrollLine, PayrollPeriod


class PayrollModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("admin", password="x")
        self.emp = Employee.objects.create(full_name="Juan Perez", hourly_rate="20")
        self.project = Project.objects.create(name="Montego")

    def period(self, **kw):
        data = dict(
            start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 8), created_by=self.user
        )
        data.update(kw)
        return PayrollPeriod.objects.create(**data)

    def test_fechas_invertidas_invalidas(self):
        with self.assertRaises(ValidationError):
            self.period(end_date=dt.date(2026, 11, 1))

    def test_periodo_nace_abierto(self):
        self.assertTrue(self.period().is_open)

    def test_unicidad_con_y_sin_proyecto(self):
        self.period()
        with self.assertRaises(ValidationError):
            self.period()
        self.period(project=self.project)
        with self.assertRaises(ValidationError):
            self.period(project=self.project)

    def test_linea_total_y_horas(self):
        line = PayrollLine.objects.create(
            period=self.period(), employee=self.emp, minutes=510,
            hourly_rate="20", base_amount="170.00", adjustment="-10.00", notes="Anticipo",
        )
        self.assertEqual(line.hours_hhmm, "08:30")
        self.assertEqual(line.total, Decimal("160.00"))

    def test_ajuste_exige_motivo(self):
        with self.assertRaises(ValidationError):
            PayrollLine.objects.create(
                period=self.period(), employee=self.emp, hourly_rate="20", adjustment="5.00"
            )

    def test_una_linea_por_trabajador_y_periodo(self):
        p = self.period()
        PayrollLine.objects.create(period=p, employee=self.emp, hourly_rate="20")
        with self.assertRaises(ValidationError):
            PayrollLine.objects.create(period=p, employee=self.emp, hourly_rate="20")
