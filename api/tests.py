from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.roles import ADMINISTRADOR, RRHH, SUPERVISOR, assign_role, roles_of

from .permissions import IsAdministrador, IsBackoffice, IsSupervisor

PASSWORD = "Clave-de-prueba-123"


class ApiAuthTests(TestCase):
    def setUp(self):
        cache.clear()  # reinicia el límite de peticiones entre pruebas
        User = get_user_model()
        self.client = APIClient()
        self.sup = User.objects.create_user("sup", password=PASSWORD, first_name="Sara", last_name="Sup")
        assign_role(self.sup, SUPERVISOR)

    def login(self, user="sup", password=PASSWORD):
        return self.client.post(reverse("api-login"), {"username": user, "password": password}, format="json")

    def test_login_devuelve_tokens_y_usuario_con_roles(self):
        r = self.login()
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.data)
        self.assertIn("refresh", r.data)
        self.assertEqual(r.data["user"]["roles"], [SUPERVISOR])
        self.assertEqual(r.data["user"]["full_name"], "Sara Sup")

    def test_login_con_clave_incorrecta_es_401(self):
        self.assertEqual(self.login(password="mala").status_code, 401)

    def test_fallo_de_login_se_registra_sin_la_clave(self):
        with self.assertLogs("accounts", level="WARNING") as cm:
            self.login(password="mala")
        self.assertTrue(any("usuario=sup" in line for line in cm.output))
        self.assertFalse(any("mala" in line for line in cm.output))

    def test_me_requiere_token(self):
        self.assertEqual(self.client.get(reverse("api-me")).status_code, 401)

    def test_me_con_token(self):
        access = self.login().data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        r = self.client.get(reverse("api-me"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["username"], "sup")

    def test_refresh_entrega_nuevo_access(self):
        refresh = self.login().data["refresh"]
        r = self.client.post(reverse("api-refresh"), {"refresh": refresh}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.data)

    def test_usuario_inactivo_no_entra(self):
        self.sup.is_active = False
        self.sup.save()
        self.assertEqual(self.login().status_code, 401)

    def test_login_por_limite_de_peticiones(self):
        codes = {self.login(password="mala").status_code for _ in range(35)}
        self.assertIn(429, codes)


class PermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.rf = RequestFactory()
        self.sup = User.objects.create_user("sup", password="x")
        self.adm = User.objects.create_user("adm", password="x")
        self.hr = User.objects.create_user("hr", password="x")
        self.root = User.objects.create_superuser("root", password="x")
        assign_role(self.sup, SUPERVISOR)
        assign_role(self.adm, ADMINISTRADOR)
        assign_role(self.hr, RRHH)

    def allowed(self, perm, user):
        req = self.rf.get("/")
        req.user = user
        return perm().has_permission(req, None)

    def test_cada_rol_solo_pasa_su_permiso(self):
        self.assertTrue(self.allowed(IsSupervisor, self.sup))
        self.assertFalse(self.allowed(IsSupervisor, self.adm))
        self.assertTrue(self.allowed(IsAdministrador, self.adm))
        self.assertFalse(self.allowed(IsAdministrador, self.hr))

    def test_backoffice_es_admin_o_rrhh(self):
        self.assertTrue(self.allowed(IsBackoffice, self.adm))
        self.assertTrue(self.allowed(IsBackoffice, self.hr))
        self.assertFalse(self.allowed(IsBackoffice, self.sup))

    def test_superusuario_pasa_todo(self):
        for perm in (IsSupervisor, IsAdministrador, IsBackoffice):
            self.assertTrue(self.allowed(perm, self.root))

    def test_roles_of(self):
        self.assertEqual(roles_of(self.root), ["SuperAdmin"])
        self.assertEqual(roles_of(self.hr), [RRHH])
