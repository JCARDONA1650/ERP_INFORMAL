from django.contrib import admin

from .models import PayrollLine, PayrollPeriod


class PayrollLineInline(admin.TabularInline):
    model = PayrollLine
    extra = 0
    readonly_fields = ("employee", "minutes", "days", "hourly_rate", "currency", "base_amount")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    """El cálculo y el cierre se hacen con los servicios (recalculate_period/close_period),
    que auditan la operación; aquí el estado y las fechas de cierre son de solo lectura."""

    list_display = ("start_date", "end_date", "project", "status", "closed_by")
    list_filter = ("status", "project")
    readonly_fields = ("status", "created_by", "closed_at", "closed_by")
    inlines = [PayrollLineInline]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return obj is None or obj.is_open
