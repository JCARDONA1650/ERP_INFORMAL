import logging

from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_login_failed, user_logged_out
from django.shortcuts import render

logger = logging.getLogger(__name__)


class AppLoginView(auth_views.LoginView):
    """Inicio de sesión. Redirige a 'home' si el usuario ya está autenticado."""

    template_name = "registration/login.html"
    redirect_authenticated_user = True


@login_required
def home(request):
    """Página de inicio mínima (protegida). Se ampliará en fases posteriores."""
    return render(request, "accounts/home.html")


@receiver(user_logged_in)
def _log_login(sender, user, request, **kwargs):
    logger.info("Inicio de sesión: usuario=%s", user.get_username())


@receiver(user_logged_out)
def _log_logout(sender, user, request, **kwargs):
    if user:
        logger.info("Cierre de sesión: usuario=%s", user.get_username())


@receiver(user_login_failed)
def _log_failed(sender, credentials, request=None, **kwargs):
    # Se registra solo el usuario intentado; nunca la contraseña.
    logger.warning("Intento de acceso fallido: usuario=%s", credentials.get("username", ""))
