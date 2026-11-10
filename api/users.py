from django.contrib.auth import get_user_model
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.roles import SUPERVISOR
from accounts.user_admin import (
    UserAdminError,
    assignable_roles,
    can_manage,
    change_own_password,
    create_user,
    must_change_password,
    reset_password,
    update_user,
    user_role,
)

from .permissions import IsAdministrador, IsBackoffice

User = get_user_model()


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


# ───────────────── Gestión de usuarios (Administrador) ─────────────────
def _row(actor, u) -> dict:
    return {
        "id": u.pk,
        "username": u.get_username(),
        "first_name": u.first_name,
        "last_name": u.last_name,
        "email": u.email,
        "role": "SuperAdmin" if u.is_superuser else user_role(u),
        "is_active": u.is_active,
        "must_change_password": must_change_password(u),
        "can_manage": can_manage(actor, u) and u.pk != actor.pk,
    }


class UserWriteSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, required=False)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    role = serializers.CharField(required=False)
    is_active = serializers.BooleanField(required=False)


def _fail(exc: UserAdminError) -> Response:
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class UserListCreateView(APIView):
    permission_classes = [IsAdministrador]

    def get(self, request):
        users = User.objects.prefetch_related("groups", "profile").order_by("username")
        data = [_row(request.user, u) for u in users if request.user.is_superuser or not u.is_superuser]
        return Response({"roles": list(assignable_roles(request.user)), "results": data})

    def post(self, request):
        s = UserWriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        try:
            user, temp = create_user(
                request.user, username=d.get("username", ""), role=d.get("role", ""),
                first_name=d.get("first_name", ""), last_name=d.get("last_name", ""),
                email=d.get("email", ""),
            )
        except UserAdminError as exc:
            return _fail(exc)
        # La contraseña temporal se muestra una sola vez; no se guarda en claro.
        return Response({**_row(request.user, user), "temp_password": temp}, status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    permission_classes = [IsAdministrador]

    def _target(self, pk):
        return User.objects.filter(pk=pk).first()

    def patch(self, request, pk):
        target = self._target(pk)
        if target is None or (target.is_superuser and not request.user.is_superuser):
            return Response({"detail": "No encontrado."}, status=status.HTTP_404_NOT_FOUND)
        s = UserWriteSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        try:
            update_user(
                request.user, target, role=d.get("role"), is_active=d.get("is_active"),
                first_name=d.get("first_name"), last_name=d.get("last_name"), email=d.get("email"),
            )
        except UserAdminError as exc:
            return _fail(exc)
        target.refresh_from_db()
        return Response(_row(request.user, target))


class UserResetPasswordView(APIView):
    permission_classes = [IsAdministrador]

    def post(self, request, pk):
        target = User.objects.filter(pk=pk).first()
        if target is None or (target.is_superuser and not request.user.is_superuser):
            return Response({"detail": "No encontrado."}, status=status.HTTP_404_NOT_FOUND)
        try:
            temp = reset_password(request.user, target)
        except UserAdminError as exc:
            return _fail(exc)
        return Response({"temp_password": temp})


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


class ChangePasswordView(APIView):
    """Cambio de contraseña propio (también para salir del estado de contraseña temporal)."""

    def post(self, request):
        s = ChangePasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            change_own_password(request.user, s.validated_data["current_password"], s.validated_data["new_password"])
        except UserAdminError as exc:
            return _fail(exc)
        return Response({"detail": "Contraseña actualizada."})
