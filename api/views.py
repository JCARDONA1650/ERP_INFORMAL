from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import LoginSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


class MeView(APIView):
    """Usuario autenticado y sus roles (el frontend lo usa para guards y menú)."""

    def get(self, request):
        return Response(UserSerializer(request.user).data)


from django.db import connection  # noqa: E402
from rest_framework import status  # noqa: E402
from rest_framework.permissions import AllowAny  # noqa: E402


class HealthView(APIView):
    """Estado del servicio para el balanceador / healthcheck de Docker.
    Sin autenticación ni límite de peticiones; no revela detalles internos."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes: list = []

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:  # noqa: BLE001 - cualquier fallo de BD = no saludable
            return Response({"status": "error"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"status": "ok"})
