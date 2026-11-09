from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .roles import user_has_role


def roles_required(*roles):
    """Restringe una vista a usuarios autenticados con alguno de los roles (o superusuario)."""

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if user_has_role(request.user, *roles):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("No tienes permisos para acceder a esta vista.")

        return _wrapped

    return decorator
