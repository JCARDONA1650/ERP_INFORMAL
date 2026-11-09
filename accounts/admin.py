from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Bitácora de solo lectura: no se crea, edita ni borra desde el admin."""

    list_display = ("created_at", "user", "action", "entity", "entity_id")
    list_filter = ("action", "entity")
    search_fields = ("detail", "entity_id", "user__username")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
