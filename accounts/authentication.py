from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication

from .user_admin import must_change_password

# Con contraseña temporal solo se permite ver el perfil y cambiar la clave.
ALLOWED_WHEN_TEMP = ("/api/auth/me/", "/api/auth/change-password/", "/api/auth/refresh/")


class ForcedChangeJWTAuthentication(JWTAuthentication):
    """JWT que bloquea toda la API mientras la contraseña sea temporal."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, _token = result
        if request.path not in ALLOWED_WHEN_TEMP and must_change_password(user):
            exc = PermissionDenied("Debes cambiar tu contraseña temporal antes de continuar.")
            exc.default_code = "password_change_required"
            raise exc
        return result
