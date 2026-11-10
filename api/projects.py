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
from projects.services import project_lunch, projects_for, save_project_site, set_project_lunch
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
    # Almuerzo: un horario para los días laborales. Solo escritura; la lectura sale en to_representation.
    lunch_start = serializers.TimeField(write_only=True, required=False, allow_null=True)
    lunch_end = serializers.TimeField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Project
        # qr_secret se omite a propósito: firma el QR y nunca sale por la API.
        fields = [
            "id", "name", "slug", "contract_value", "contract_currency",
            "active", "photo_required", "work_days", "work_start", "work_end",
            "lunch_start", "lunch_end", "site", "supervisors", "employees",
        ]
        read_only_fields = ["id", "slug"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.setdefault("site", None)  # proyecto sin zona definida
        start, end, custom = project_lunch(instance)
        data["lunch_start"] = start.strftime("%H:%M") if start else None
        data["lunch_end"] = end.strftime("%H:%M") if end else None
        data["lunch_custom"] = custom  # reglas distintas por día (administrador): no se editan aquí
        return data

    def validate(self, attrs):
        # Mismas reglas del modelo, para responder 400 y no 500.
        days = attrs.get("work_days")
        if days is not None and any(
            not isinstance(d, int) or isinstance(d, bool) or d < 0 or d > 6 for d in days
        ):
            raise serializers.ValidationError({"work_days": "Los días laborales deben ser de 0 (lunes) a 6 (domingo)."})
        start, end = attrs.get("work_start"), attrs.get("work_end")
        if "work_start" in attrs or "work_end" in attrs:
            start = attrs.get("work_start", getattr(self.instance, "work_start", None))
            end = attrs.get("work_end", getattr(self.instance, "work_end", None))
            if (start is None) != (end is None):
                raise serializers.ValidationError({"work_end": "Indica la hora de inicio y la de fin de la jornada."})
            if start and end and end <= start:
                raise serializers.ValidationError({"work_end": "La hora de fin de la jornada debe ser mayor que la de inicio."})
        l_start, l_end = attrs.get("lunch_start"), attrs.get("lunch_end")
        if ("lunch_start" in attrs or "lunch_end" in attrs):
            if (l_start is None) != (l_end is None):
                raise serializers.ValidationError({"lunch_end": "Indica la hora de inicio y la de fin del almuerzo."})
            if l_start and l_end and l_end <= l_start:
                raise serializers.ValidationError({"lunch_end": "La hora final del almuerzo debe ser mayor que la inicial."})
        return attrs

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
        has_lunch = "lunch_start" in validated or "lunch_end" in validated
        lunch = (validated.pop("lunch_start", None), validated.pop("lunch_end", None))
        project = Project.objects.create(**validated)
        project.supervisors.set(supervisors)
        project.employees.set(employees)
        if site:
            save_project_site(project, site)
        if has_lunch:
            set_project_lunch(project, *lunch)
        return project

    @transaction.atomic
    def update(self, instance, validated):
        has_site = "site" in validated
        site = validated.pop("site", None)
        supervisors = validated.pop("supervisors", None)
        employees = validated.pop("employees", None)
        has_lunch = "lunch_start" in validated or "lunch_end" in validated
        lunch = (validated.pop("lunch_start", None), validated.pop("lunch_end", None))
        for key, value in validated.items():
            setattr(instance, key, value)
        instance.save()
        if has_lunch:
            set_project_lunch(instance, *lunch)
        if supervisors is not None:
            instance.supervisors.set(supervisors)
        if employees is not None:
            instance.employees.set(employees)
        if has_site:
            save_project_site(instance, site)
        # Se relee para no devolver zona/relaciones en caché ya desactualizadas.
        return self.Meta.model.objects.select_related("site").prefetch_related(
            "supervisors", "employees", "lunch_rules"
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
        return (
            qs.select_related("site")
            .prefetch_related("supervisors", "employees", "lunch_rules")
            .order_by("name")
        )

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
