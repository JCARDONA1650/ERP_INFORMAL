from .models import AuditLog


def audit(user, action: str, entity: str, entity_id="", detail: str = "") -> AuditLog:
    """Registra una acción sensible. `user` puede ser None (procesos del sistema)."""
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    return AuditLog.objects.create(
        user=user, action=action, entity=entity, entity_id=str(entity_id), detail=detail
    )
