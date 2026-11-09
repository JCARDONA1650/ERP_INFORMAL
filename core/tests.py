from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AdminSmokeTests(TestCase):
    """Cada modelo registrado en el admin debe abrir su listado sin errores."""

    def test_changelists_cargan(self):
        root = get_user_model().objects.create_superuser("root", password="x")
        self.client.force_login(root)
        registered = [
            m for m in admin.site._registry
            if m._meta.app_label in {"accounts", "workers", "projects", "attendance", "payroll", "finance"}
        ]
        self.assertEqual(len(registered), 9)
        for model in registered:
            url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
            self.assertEqual(self.client.get(url).status_code, 200, url)
