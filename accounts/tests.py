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
