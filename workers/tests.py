from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import Employee
from .services import find_similar_names, rate_for, set_rate


class EmployeeModelTests(TestCase):
    def test_normaliza_nombre_y_documento(self):
        e = Employee.objects.create(full_name="  Juan   Perez ", document_id=" ab-12 ")
        self.assertEqual(e.full_name, "Juan Perez")
        self.assertEqual(e.document_id, "AB-12")

    def test_nombre_solo_letras(self):
        with self.assertRaises(ValidationError):
            Employee.objects.create(full_name="Juan 123")

    def test_documento_opcional_y_unico(self):
        Employee.objects.create(full_name="Ana Gomez")
        Employee.objects.create(full_name="Luis Diaz")  # ambos sin documento
        Employee.objects.create(full_name="Pedro Ruiz", document_id="X1")
        with self.assertRaises(ValidationError):
            Employee.objects.create(full_name="Otro Ruiz", document_id="x1")

    def test_tarifa_negativa_rechazada(self):
        with self.assertRaises(ValidationError):
            Employee.objects.create(full_name="Ana Gomez", hourly_rate=Decimal("-1"))

    def test_homonimos_se_permiten_pero_se_detectan(self):
        a = Employee.objects.create(full_name="Carlos Hernandez")
        b = Employee.objects.create(full_name="Carlos Hernandez")
        self.assertNotEqual(a.pk, b.pk)
        self.assertEqual(find_similar_names("carlos  hernandez").count(), 2)
        self.assertEqual(find_similar_names("carlos hernandez", exclude_pk=a.pk).count(), 1)


class RateHistoryTests(TestCase):
    def setUp(self):
        self.emp = Employee.objects.create(full_name="Ana Gomez", hourly_rate=Decimal("20.00"))

    def test_sin_historial_usa_tarifa_actual(self):
        self.assertEqual(rate_for(self.emp, date(2026, 10, 1)), Decimal("20.00"))

    def test_tarifa_por_fecha_de_vigencia(self):
        set_rate(self.emp, "20.00", date(2026, 1, 1))
        set_rate(self.emp, "25.00", date(2026, 10, 8))
        self.assertEqual(rate_for(self.emp, date(2026, 10, 7)), Decimal("20.00"))
        self.assertEqual(rate_for(self.emp, date(2026, 10, 8)), Decimal("25.00"))
        self.assertEqual(rate_for(self.emp, date(2026, 10, 20)), Decimal("25.00"))

    def test_actualiza_tarifa_vigente_si_ya_rige(self):
        set_rate(self.emp, "30.00", timezone.localdate() - timedelta(days=1))
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.hourly_rate, Decimal("30.00"))

    def test_no_actualiza_si_es_futura(self):
        set_rate(self.emp, "40.00", timezone.localdate() + timedelta(days=10))
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.hourly_rate, Decimal("20.00"))
