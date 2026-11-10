from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from accounts.models import AuditLog
from accounts.roles import ADMINISTRADOR, RRHH, SUPERVISOR, assign_role, roles_of

URL = "/api/users/"
User = get_user_model()


class UserAdminApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = User.objects.create_superuser("root", password="Clave-Root-123")
        cls.adm = User.objects.create_user("adm", password="Clave-Adm-123")
        cls.adm2 = User.objects.create_user("adm2", password="Clave-Adm2-123")
        cls.hr = User.objects.create_user("hr", password="Clave-Hr-123")
        cls.sup = User.objects.create_user("sup", password="Clave-Sup-123")
        assign_role(cls.adm, ADMINISTRADOR)
        assign_role(cls.adm2, ADMINISTRADOR)
        assign_role(cls.hr, RRHH)
        assign_role(cls.sup, SUPERVISOR)

    def setUp(self):
        cache.clear()

    def as_(self, user):
        self.client.force_authenticate(user)

    # ── permisos ──
    def test_solo_administrador_gestiona_usuarios(self):
        self.assertEqual(self.client.get(URL).status_code, 401)
        for user in (self.hr, self.sup):
            self.as_(user)
            self.assertEqual(self.client.get(URL).status_code, 403)
            self.assertEqual(self.client.post(URL, {}, format="json").status_code, 403)

    def test_listado_oculta_superusuarios_al_administrador(self):
        self.as_(self.adm)
        r = self.client.get(URL)
        names = [u["username"] for u in r.data["results"]]
        self.assertNotIn("root", names)
        self.assertEqual(r.data["roles"], [RRHH, SUPERVISOR])
        self.as_(self.root)
        self.assertIn("root", [u["username"] for u in self.client.get(URL).data["results"]])

    # ── alta ──
    def test_alta_con_clave_temporal_y_cambio_obligatorio(self):
        self.as_(self.adm)
        r = self.client.post(URL, {"username": "nuevo", "role": SUPERVISOR, "first_name": "Nora"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        temp = r.data["temp_password"]
        user = User.objects.get(username="nuevo")
        self.assertTrue(user.check_password(temp))
        self.assertTrue(r.data["must_change_password"])
        self.assertEqual(roles_of(user), [SUPERVISOR])
        log = AuditLog.objects.get(action="crear_usuario")
        self.assertNotIn(temp, log.detail)  # la clave nunca va a la bitácora

    def test_administrador_no_crea_administradores_pero_superadmin_si(self):
        self.as_(self.adm)
        r = self.client.post(URL, {"username": "a3", "role": ADMINISTRADOR}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(User.objects.filter(username="a3").exists())
        self.as_(self.root)
        self.assertEqual(self.client.post(URL, {"username": "a3", "role": ADMINISTRADOR}, format="json").status_code, 201)

    def test_alta_rechaza_duplicado_y_rol_invalido(self):
        self.as_(self.adm)
        self.assertEqual(self.client.post(URL, {"username": "SUP", "role": RRHH}, format="json").status_code, 400)
        self.assertEqual(self.client.post(URL, {"username": "x1", "role": "Dios"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(URL, {"role": RRHH}, format="json").status_code, 400)

    # ── cambio de rol / activación ──
    def test_cambia_rol_y_deja_un_solo_rol(self):
        self.as_(self.adm)
        r = self.client.patch(f"{URL}{self.sup.pk}/", {"role": RRHH}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(roles_of(User.objects.get(pk=self.sup.pk)), [RRHH])

    def test_administrador_no_toca_a_otro_administrador_ni_al_superusuario(self):
        self.as_(self.adm)
        self.assertEqual(self.client.patch(f"{URL}{self.adm2.pk}/", {"role": RRHH}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(f"{URL}{self.root.pk}/", {"is_active": False}, format="json").status_code, 404)
        self.assertEqual(self.client.post(f"{URL}{self.adm2.pk}/reset-password/").status_code, 400)
        self.as_(self.root)
        self.assertEqual(self.client.patch(f"{URL}{self.adm2.pk}/", {"role": RRHH}, format="json").status_code, 200)

    def test_no_puede_cambiarse_rol_ni_desactivarse_a_si_mismo(self):
        self.as_(self.adm)
        self.assertEqual(self.client.patch(f"{URL}{self.adm.pk}/", {"role": RRHH}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(f"{URL}{self.adm.pk}/", {"is_active": False}, format="json").status_code, 400)

    def test_desactivar_y_reactivar(self):
        self.as_(self.adm)
        self.client.patch(f"{URL}{self.hr.pk}/", {"is_active": False}, format="json")
        self.assertFalse(User.objects.get(pk=self.hr.pk).is_active)
        self.client.patch(f"{URL}{self.hr.pk}/", {"is_active": True}, format="json")
        self.assertTrue(User.objects.get(pk=self.hr.pk).is_active)

    # ── restablecer clave y cambio obligatorio (JWT real) ──
    def login(self, username, password):
        self.client.force_authenticate(None)
        return self.client.post("/api/auth/login/", {"username": username, "password": password}, format="json")

    def test_reset_obliga_a_cambiar_y_bloquea_el_resto_de_la_api(self):
        self.as_(self.adm)
        temp = self.client.post(f"{URL}{self.hr.pk}/reset-password/").data["temp_password"]
        self.assertFalse(User.objects.get(pk=self.hr.pk).check_password("Clave-Hr-123"))

        r = self.login("hr", temp)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["user"]["must_change_password"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

        # Bloqueado: no puede usar la API...
        blocked = self.client.get("/api/projects/")
        self.assertEqual(blocked.status_code, 403)
        # ...salvo ver su perfil y cambiar la clave.
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)

        bad = self.client.post("/api/auth/change-password/", {"current_password": temp, "new_password": "123"}, format="json")
        self.assertEqual(bad.status_code, 400)
        ok = self.client.post(
            "/api/auth/change-password/", {"current_password": temp, "new_password": "Nueva-Clave-987"}, format="json"
        )
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertFalse(self.client.get("/api/auth/me/").data["must_change_password"])
        self.assertEqual(self.client.get("/api/projects/").status_code, 200)
        self.client.credentials()

    def test_cambio_de_clave_exige_la_actual_y_una_distinta(self):
        self.as_(self.hr)
        url = "/api/auth/change-password/"
        r = self.client.post(url, {"current_password": "mal", "new_password": "Nueva-Clave-987"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post(url, {"current_password": "Clave-Hr-123", "new_password": "Clave-Hr-123"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_usuario_desactivado_no_puede_ingresar(self):
        self.as_(self.adm)
        self.client.patch(f"{URL}{self.sup.pk}/", {"is_active": False}, format="json")
        self.assertEqual(self.login("sup", "Clave-Sup-123").status_code, 401)
