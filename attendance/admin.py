from django.contrib import admin

from .models import Attendance, AttendanceScan, ProjectLunchRule


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("date", "project", "employee", "check_in", "check_out", "in_zone", "needs_review")
    list_filter = ("project", "needs_review", "in_zone", "date")
    search_fields = ("employee__full_name",)
    list_select_related = ("project", "employee")
    date_hierarchy = "date"


@admin.register(AttendanceScan)
class AttendanceScanAdmin(admin.ModelAdmin):
    list_display = ("server_ts", "employee", "project", "action", "source", "in_zone")
    list_filter = ("source", "action", "in_zone")
    list_select_related = ("project", "employee")
    readonly_fields = ("client_uuid", "server_ts")


@admin.register(ProjectLunchRule)
class ProjectLunchRuleAdmin(admin.ModelAdmin):
    list_display = ("project", "weekday", "start_time", "end_time", "active")
    list_filter = ("project", "weekday", "active")
