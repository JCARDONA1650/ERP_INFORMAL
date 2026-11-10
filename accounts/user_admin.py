"""Gestión de usuarios por el Administrador: alta, rol, activación y contraseña temporal.

Reglas:
- El Administrador gestiona RRHH y Supervisor; solo el Super Admin (superusuario)
  crea o modifica Administradores.
- Un usuario tiene un único rol de la app.
- Las contraseñas temporales obligan a cambiarlas en el primer ingreso y nunca se
  guardan en la bitácora.
"""
import secrets
import string

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import UserProfile
from .roles import ADMINISTRADOR, ROLE_NAMES, RRHH, SUPERVISOR, roles_of
from .services import audit

User = get_user_model()

ADMIN_MANAGEABLE_ROLES = (RRHH, SUPERVISOR)
_ALPHABET = string.ascii_letters + string.digits


class UserAdminError(Exception):
    """Operación de gestión de usuarios no permitida o inválida."""


def generate_temp_password(length: int = 12) -> str:
    """Contraseña aleatoria que cumple los validadores de Django."""
    while True:
        candidate = "".join(secrets.choice(_ALPHABET) for _ in range(length))
        if not (any(c.isdigit() for c in candidate) and any(c.isalpha() for c in candidate)):
            continue
        try:
            validate_password(candidate)
        except ValidationError:
            continue
        return candidate


def assignable_roles(actor) -> tuple[str, ...]:
    return ROLE_NAMES if actor.is_superuser else ADMIN_MANAGEABLE_ROLES


def user_role(user) -> str | None:
    roles = [r for r in roles_of(user) if r in ROLE_NAMES]
    return roles[0] if roles else None


def can_manage(actor, target) -> bool:
    """El superusuario gestiona a todos; el Administrador, a RRHH y Supervisor (no superusuarios)."""
    if actor.is_superuser:
        return True
    return not target.is_superuser and user_role(target) in ADMIN_MANAGEABLE_ROLES


def _check_role(actor, role: str) -> None:
    if role not in assignable_roles(actor):
        raise UserAdminError(
            "Solo el Super Admin puede asignar el rol Administrador."
            if role == ADMINISTRADOR
            else f"Rol inválido: {role}."
        )


def _set_role(user, role: str) -> None:
    user.groups.remove(*Group.objects.filter(name__in=ROLE_NAMES))
    group, _ = Group.objects.get_or_create(name=role)
    user.groups.add(group)


def must_change_password(user) -> bool:
    profile = getattr(user, "profile", None)
    return bool(profile and profile.must_change_password)


def _flag(user, value: bool) -> None:
    UserProfile.objects.update_or_create(user=user, defaults={"must_change_password": value})


@transaction.atomic
def create_user(actor, *, username, role, first_name="", last_name="", email="") -> tuple:
    """Crea el usuario con contraseña temporal. Devuelve (usuario, contraseña_temporal)."""
    _check_role(actor, role)
    username = (username or "").strip()
    if not username:
        raise UserAdminError("Ingresa el nombre de usuario.")
    if User.objects.filter(username__iexact=username).exists():
        raise UserAdminError("Ya existe un usuario con ese nombre.")
    temp = generate_temp_password()
    user = User.objects.create_user(
        username=username, password=temp, first_name=first_name.strip(),
        last_name=last_name.strip(), email=email.strip(),
    )
    _set_role(user, role)
    _flag(user, True)
    audit(actor, "crear_usuario", "User", user.pk, f"{username} · rol {role}")
    return user, temp


@transaction.atomic
def update_user(actor, target, *, role=None, is_active=None, first_name=None, last_name=None, email=None):
    if not can_manage(actor, target):
        raise UserAdminError("No tienes permiso para gestionar a este usuario.")
    changes = []
    if role is not None and role != user_role(target):
        if target.pk == actor.pk:
            raise UserAdminError("No puedes cambiar tu propio rol.")
        _check_role(actor, role)
        _set_role(target, role)
        changes.append(f"rol→{role}")
    if is_active is not None and is_active != target.is_active:
        if target.pk == actor.pk:
            raise UserAdminError("No puedes desactivarte a ti mismo.")
        target.is_active = is_active
        changes.append("activado" if is_active else "desactivado")
    for field, value in (("first_name", first_name), ("last_name", last_name), ("email", email)):
        if value is not None and value.strip() != getattr(target, field):
            setattr(target, field, value.strip())
            changes.append(field)
    target.save()
    if changes:
        audit(actor, "editar_usuario", "User", target.pk, f"{target.get_username()}: {', '.join(changes)}")
    return target


@transaction.atomic
def reset_password(actor, target) -> str:
    """Asigna una contraseña temporal nueva y obliga a cambiarla al ingresar."""
    if not can_manage(actor, target):
        raise UserAdminError("No tienes permiso para gestionar a este usuario.")
    if target.pk == actor.pk:
        raise UserAdminError("Cambia tu propia contraseña desde «Cambiar contraseña».")
    temp = generate_temp_password()
    target.set_password(temp)
    target.save(update_fields=["password"])
    _flag(target, True)
    audit(actor, "restablecer_clave", "User", target.pk, target.get_username())
    return temp


@transaction.atomic
def change_own_password(user, current: str, new: str) -> None:
    if not user.check_password(current):
        raise UserAdminError("La contraseña actual no es correcta.")
    if current == new:
        raise UserAdminError("La contraseña nueva debe ser distinta de la actual.")
    try:
        validate_password(new, user)
    except ValidationError as exc:
        raise UserAdminError(" ".join(exc.messages)) from exc
    user.set_password(new)
    user.save(update_fields=["password"])
    _flag(user, False)
    audit(user, "cambiar_clave", "User", user.pk, user.get_username())
