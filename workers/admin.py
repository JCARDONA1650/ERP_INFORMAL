from django.contrib import admin

from .models import Employee, RateHistory


class RateHistoryInline(admin.TabularInline):
    model = RateHistory
    extra = 0
    readonly_fields = ("created_by", "created_at")


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("full_name", "document_id", "position", "pay_type", "hourly_rate", "currency", "active")
    list_filter = ("active", "pay_type", "currency")
    search_fields = ("full_name", "document_id")
    inlines = [RateHistoryInline]
