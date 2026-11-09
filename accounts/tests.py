from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AuthFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="tester", password="Clave-de-prueba-123"
        )

    def test_home_requires_login(self):
        response = self.client.get(reverse("home"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('home')}")

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "INFORMAL ERP")

    def test_login_success_redirects_to_home(self):
        response = self.client.post(
            reverse("login"),
            {"username": "tester", "password": "Clave-de-prueba-123"},
        )
        self.assertRedirects(response, reverse("home"))

    def test_login_wrong_password_shows_error(self):
        response = self.client.post(
            reverse("login"), {"username": "tester", "password": "incorrecta"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Usuario o contraseña inválidos")

    def test_logout_requires_post_and_closes_session(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"))
        self.assertRedirects(
            self.client.get(reverse("home")),
            f"{reverse('login')}?next={reverse('home')}",
        )

    def test_authenticated_user_skips_login_page(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(reverse("login")), reverse("home"))


class RolesTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Group

        self.User = get_user_model()
        self.sup = self.User.objects.create_user("sup", password="x")
        self.root = self.User.objects.create_superuser("root", password="x")
        self.Group = Group

    def test_grupos_de_rol_existen_tras_migrar(self):
        from .roles import ROLE_NAMES

        for name in ROLE_NAMES:
            self.assertTrue(self.Group.objects.filter(name=name).exists())

    def test_assign_role_y_user_has_role(self):
        from .roles import RRHH, SUPERVISOR, assign_role, user_has_role

        assign_role(self.sup, SUPERVISOR)
        self.assertTrue(user_has_role(self.sup, SUPERVISOR))
        self.assertFalse(user_has_role(self.sup, RRHH))
        self.assertTrue(user_has_role(self.root, RRHH))

    def test_assign_role_invalido(self):
        from .roles import assign_role

        with self.assertRaises(ValueError):
            assign_role(self.sup, "Inventado")

    def test_decorador_niega_sin_rol(self):
        from django.core.exceptions import PermissionDenied
        from django.test import RequestFactory

        from .decorators import roles_required
        from .roles import ADMINISTRADOR

        @roles_required(ADMINISTRADOR)
        def vista(request):
            return "ok"

        req = RequestFactory().get("/")
        req.user = self.sup
        with self.assertRaises(PermissionDenied):
            vista(req)
        req.user = self.root
        self.assertEqual(vista(req), "ok")

    def test_audit_registra_y_acepta_anonimo(self):
        from django.contrib.auth.models import AnonymousUser

        from .models import AuditLog
        from .services import audit

        audit(self.sup, "cierre", "PayrollPeriod", 3, "detalle")
        audit(AnonymousUser(), "x", "Y")
        self.assertEqual(AuditLog.objects.count(), 2)
        self.assertIsNone(AuditLog.objects.get(action="x").user)
