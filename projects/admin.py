from django.contrib import admin

from .models import Project, ProjectSite


class ProjectSiteInline(admin.StackedInline):
    model = ProjectSite
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "contract_value", "contract_currency", "active")
    list_filter = ("active", "contract_currency")
    search_fields = ("name",)
    filter_horizontal = ("supervisors", "employees")
    inlines = [ProjectSiteInline]
    # qr_secret es editable=False: no se muestra ni se edita desde el admin.
