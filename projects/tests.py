from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Project, ProjectSite
from .services import haversine_m, is_in_zone, projects_for, user_can_access_project


class ProjectModelTests(TestCase):
    def test_slug_unico_y_nombre_normalizado(self):
        a = Project.objects.create(name="  Torre   Norte ")
        b = Project.objects.create(name="Torre Norte 2")
        self.assertEqual(a.name, "Torre Norte")
        self.assertEqual(a.slug, "torre-norte")
        self.assertNotEqual(a.slug, b.slug)

    def test_nombre_unico(self):
        Project.objects.create(name="Montego")
        with self.assertRaises(ValidationError):
            Project.objects.create(name="Montego")

    def test_contrato_no_negativo(self):
        with self.assertRaises(ValidationError):
            Project.objects.create(name="X", contract_value=Decimal("-1"))

    def test_qr_secret_se_genera_y_es_distinto(self):
        a = Project.objects.create(name="A")
        b = Project.objects.create(name="B")
        self.assertTrue(a.qr_secret)
        self.assertNotEqual(a.qr_secret, b.qr_secret)


class ZoneTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Montego")

    def test_haversine_distancia_conocida(self):
        # ~111 km por grado de latitud
        d = haversine_m(28.5, -81.4, 29.5, -81.4)
        self.assertAlmostEqual(d / 1000, 111.2, delta=0.5)

    def test_sin_zona_devuelve_none(self):
        self.assertIsNone(is_in_zone(self.project, 28.5, -81.4))

    def test_sin_coordenadas_devuelve_none(self):
        ProjectSite.objects.create(project=self.project, latitude="28.5", longitude="-81.4")
        self.project.refresh_from_db()
        self.assertIsNone(is_in_zone(self.project, None, None))

    def test_dentro_y_fuera_de_zona(self):
        ProjectSite.objects.create(
            project=self.project, latitude="28.500000", longitude="-81.400000", radius_m=150
        )
        project = Project.objects.get(pk=self.project.pk)
        self.assertTrue(is_in_zone(project, 28.5005, -81.4))   # ~55 m
        self.assertFalse(is_in_zone(project, 28.502, -81.4))   # ~222 m

    def test_latitud_fuera_de_rango(self):
        with self.assertRaises(ValidationError):
            ProjectSite.objects.create(project=self.project, latitude="95", longitude="0")


class AccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.sup = User.objects.create_user("sup", password="x")
        self.other = User.objects.create_user("otro", password="x")
        self.root = User.objects.create_superuser("root", password="x")
        self.p1 = Project.objects.create(name="P1")
        self.p2 = Project.objects.create(name="P2")
        self.p1.supervisors.add(self.sup)

    def test_supervisor_solo_ve_sus_proyectos(self):
        self.assertTrue(user_can_access_project(self.sup, self.p1))
        self.assertFalse(user_can_access_project(self.sup, self.p2))
        self.assertEqual(list(projects_for(self.sup)), [self.p1])

    def test_sin_asignacion_no_ve_nada(self):
        self.assertFalse(user_can_access_project(self.other, self.p1))
        self.assertEqual(projects_for(self.other).count(), 0)

    def test_superusuario_ve_todo(self):
        self.assertEqual(projects_for(self.root).count(), 2)
