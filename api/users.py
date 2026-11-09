from django.contrib.auth import get_user_model
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.roles import SUPERVISOR

from .permissions import IsBackoffice


class SupervisorListView(APIView):
    """Usuarios activos con rol Supervisor, para asignarlos a proyectos."""

    permission_classes = [IsBackoffice]

    def get(self, request):
        users = (
            get_user_model()
            .objects.filter(is_active=True, groups__name=SUPERVISOR)
            .order_by("first_name", "last_name", "username")
        )
        return Response(
            [
                {"id": u.pk, "username": u.get_username(), "full_name": u.get_full_name() or u.get_username()}
                for u in users
            ]
        )
