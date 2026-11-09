from django.contrib import admin

from .models import ProjectExpense, ProjectIncome


class _MovementAdmin(admin.ModelAdmin):
    list_select_related = ("project",)
    date_hierarchy = "date"
    readonly_fields = ("created_by",)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ProjectIncome)
class ProjectIncomeAdmin(_MovementAdmin):
    list_display = ("date", "project", "amount", "currency", "description")
    list_filter = ("project", "currency")


@admin.register(ProjectExpense)
class ProjectExpenseAdmin(_MovementAdmin):
    list_display = ("date", "project", "category", "amount", "currency", "description")
    list_filter = ("project", "category", "currency")
