from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """Datos de cuenta propios de la app. Sin fila = comportamiento por defecto."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    # Contraseña temporal (alta o restablecimiento): debe cambiarse en el primer ingreso.
    must_change_password = models.BooleanField(default=False)

    def __str__(self):
        return f"Perfil de {self.user}"


class AuditLog(models.Model):
    """Trazabilidad de acciones sensibles (cierres, ajustes, cambios de tarifa)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    action = models.CharField("Acción", max_length=60)
    entity = models.CharField("Entidad", max_length=60)
    entity_id = models.CharField("ID de entidad", max_length=40, blank=True)
    detail = models.TextField("Detalle", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["entity", "entity_id"])]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.entity}#{self.entity_id}"
