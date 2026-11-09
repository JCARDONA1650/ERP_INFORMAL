"""Roles del sistema. El Empleado no tiene usuario (marca con QR) y el
Super Admin es el superusuario de Django."""
from django.contrib.auth.models import Group

SUPERVISOR = "Supervisor"
ADMINISTRADOR = "Administrador"
RRHH = "RRHH"

ROLE_NAMES = (SUPERVISOR, ADMINISTRADOR, RRHH)


def user_has_role(user, *roles) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=roles).exists()


def assign_role(user, role: str) -> None:
    if role not in ROLE_NAMES:
        raise ValueError(f"Rol desconocido: {role}")
    group, _ = Group.objects.get_or_create(name=role)
    user.groups.add(group)
