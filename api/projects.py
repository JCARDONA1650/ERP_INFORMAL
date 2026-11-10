from io import BytesIO
from urllib.parse import urlencode

import qrcode
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpResponse
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.roles import ADMINISTRADOR, RRHH, SUPERVISOR, user_has_role
from projects.models import Project, ProjectSite
from attendance.qr import make_qr_token
from projects.services import projects_for, save_project_site
from workers.models import Employee

from .permissions import BackofficeWriteSupervisorRead

User = get_user_model()


class ProjectSiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectSite
        fields = ["latitude", "longitude", "radius_m", "out_of_zone_policy", "address"]


class ProjectSerializer(serializers.ModelSerializer):
    site = ProjectSiteSerializer(required=False, allow_null=True)
    supervisors = serializers.PrimaryKeyRelatedField(
        many=True, queryset=User.objects.filter(is_active=True), required=False
    )
    employees = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Employee.objects.all(), required=False
    )

    class Meta:
        model = Project
        # qr_secret se omite a propósito: firma el QR y nunca sale por la API.
        fields = [
            "id", "name", "slug", "contract_value", "contract_currency",
            "active", "site", "supervisors", "employees",
        ]
        read_only_fields = ["id", "slug"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.setdefault("site", None)  # proyecto sin zona definida
        return data

    def validate_supervisors(self, users):
        """Solo usuarios con rol Supervisor pueden asignarse como supervisores."""
        for user in users:
            if not user.groups.filter(name=SUPERVISOR).exists():
                raise serializers.ValidationError(
                    f"El usuario '{user.get_username()}' no tiene el rol Supervisor."
                )
        return users

    @transaction.atomic
    def create(self, validated):
        site = validated.pop("site", None)
        supervisors = validated.pop("supervisors", [])
        employees = validated.pop("employees", [])
        project = Project.objects.create(**validated)
        project.supervisors.set(supervisors)
        project.employees.set(employees)
        if site:
            save_project_site(project, site)
        return project

    @transaction.atomic
    def update(self, instance, validated):
        has_site = "site" in validated
        site = validated.pop("site", None)
        supervisors = validated.pop("supervisors", None)
        employees = validated.pop("employees", None)
        for key, value in validated.items():
            setattr(instance, key, value)
        instance.save()
        if supervisors is not None:
            instance.supervisors.set(supervisors)
        if employees is not None:
            instance.employees.set(employees)
        if has_site:
            save_project_site(instance, site)
        # Se relee para no devolver zona/relaciones en caché ya desactualizadas.
        return self.Meta.model.objects.select_related("site").prefetch_related(
            "supervisors", "employees"
        ).get(pk=instance.pk)


class ProjectViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Proyectos. No se borran: se desactivan con `active=false`."""

    serializer_class = ProjectSerializer
    permission_classes = [BackofficeWriteSupervisorRead]

    def get_queryset(self):
        user = self.request.user
        qs = Project.objects.all() if user_has_role(user, ADMINISTRADOR, RRHH) else projects_for(user)
        if (active := self.request.query_params.get("active")) in ("true", "false"):
            qs = qs.filter(active=(active == "true"))
        return qs.select_related("site").prefetch_related("supervisors", "employees").order_by("name")

    @staticmethod
    def _marking_link(project) -> str:
        return (
            f"{settings.FRONTEND_BASE_URL}/marcar/{project.slug}?"
            + urlencode({"t": make_qr_token(project)})
        )

    @action(detail=True, methods=["get"], url_path="qr-link")
    def qr_link(self, request, pk=None):
        """Enlace de marcación del día (el mismo que codifica el QR), para compartirlo o copiarlo."""
        return Response({"url": self._marking_link(self.get_object())})

    @action(detail=True, methods=["get"], url_path="qr")
    def qr(self, request, pk=None):
        """PNG del QR de marcación del día. Lo ve el Supervisor de la obra o el backoffice."""
        link = self._marking_link(self.get_object())
        buffer = BytesIO()
        qrcode.make(link, box_size=10, border=4).save(buffer, format="PNG")
        response = HttpResponse(buffer.getvalue(), content_type="image/png")
        response["Cache-Control"] = "no-store"  # el token cambia cada día
        return response
