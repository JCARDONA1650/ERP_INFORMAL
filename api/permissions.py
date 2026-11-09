from rest_framework.permissions import BasePermission

from accounts.roles import ADMINISTRADOR, RRHH, SUPERVISOR, user_has_role


class HasAnyRole(BasePermission):
    """Base: permite a usuarios con alguno de `allowed_roles` (el superusuario siempre)."""

    allowed_roles: tuple[str, ...] = ()
    message = "No tienes permisos para realizar esta acción."

    def has_permission(self, request, view):
        return user_has_role(request.user, *self.allowed_roles)


class IsSupervisor(HasAnyRole):
    allowed_roles = (SUPERVISOR,)


class IsAdministrador(HasAnyRole):
    allowed_roles = (ADMINISTRADOR,)


class IsRRHH(HasAnyRole):
    allowed_roles = (RRHH,)


class IsBackoffice(HasAnyRole):
    """Administrador o RRHH."""

    allowed_roles = (ADMINISTRADOR, RRHH)
