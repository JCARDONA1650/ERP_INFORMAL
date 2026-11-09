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
