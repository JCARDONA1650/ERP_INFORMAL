from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import FileResponse, Http404
from django.urls import reverse
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.roles import ADMINISTRADOR, RRHH, SUPERVISOR, user_has_role
from attendance.models import Attendance
from attendance.services import (
    AttendanceLocked,
    adjust_minutes,
    lunch_from_map,
    lunch_minutes_map,
    net_worked_minutes,
    review_attendance,
)

from .permissions import HasAnyRole, IsBackoffice


class IsStaffRole(HasAnyRole):
    """Cualquier rol con usuario: Supervisor, Administrador o RRHH."""

    allowed_roles = (SUPERVISOR, ADMINISTRADOR, RRHH)


class AttendanceSerializer(serializers.ModelSerializer):
    project = serializers.SerializerMethodField()
    employee = serializers.SerializerMethodField()
    worked_minutes = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()
    reviewed_by = serializers.SlugRelatedField(slug_field="username", read_only=True)

    class Meta:
        model = Attendance
        fields = [
            "id", "date", "project", "employee",
            "check_in", "check_out", "check_in_source", "check_out_source",
            "in_zone", "needs_review", "reviewed_by", "reviewed_at",
            "manual_minutes", "manual_note", "worked_minutes", "photo_url", "notes",
        ]
        read_only_fields = fields

    def get_project(self, obj):
        return {"id": obj.project_id, "name": obj.project.name}

    def get_employee(self, obj):
        return {"id": obj.employee_id, "full_name": obj.employee.full_name}

    def get_worked_minutes(self, obj) -> int:
        # El mapa de almuerzo se carga una sola vez por petición (sin N+1).
        lunch = lunch_from_map(self.context["lunch_map"], obj.project_id, obj.date)
        return net_worked_minutes(obj, lunch_minutes=lunch)

    def get_photo_url(self, obj):
        # La foto no se sirve como archivo público: se pide por un endpoint con permisos.
        if not obj.evidence_photo:
            return None
        return reverse("attendance-photo", kwargs={"pk": obj.pk})


class AdjustSerializer(serializers.Serializer):
    minutes = serializers.IntegerField(min_value=0, max_value=24 * 60)
    reason = serializers.CharField(max_length=200)

    def validate_reason(self, value):
        if not value.strip():
            raise serializers.ValidationError("Todo ajuste manual requiere un motivo.")
        return value


class AttendanceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Jornadas para revisión. Backoffice ve todo; el Supervisor, solo sus proyectos."""

    serializer_class = AttendanceSerializer
    permission_classes = [IsStaffRole]

    def get_queryset(self):
        user = self.request.user
        qs = Attendance.objects.select_related("project", "employee", "reviewed_by")
        if not user_has_role(user, ADMINISTRADOR, RRHH):
            qs = qs.filter(project__supervisors=user)

        p = self.request.query_params
        filters = {
            "project": "project_id",
            "employee": "employee_id",
            "date_from": "date__gte",
            "date_to": "date__lte",
        }
        try:
            for param, lookup in filters.items():
                if value := p.get(param):
                    qs = qs.filter(**{lookup: value})
        except (ValueError, TypeError, DjangoValidationError) as exc:  # id o fecha mal formados
            raise serializers.ValidationError({"detail": "Filtro con valor inválido."}) from exc
        if (nr := p.get("needs_review")) in ("true", "false"):
            qs = qs.filter(needs_review=(nr == "true"))
        return qs.order_by("-date", "project__name", "employee__full_name")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["lunch_map"] = lunch_minutes_map()
        return ctx

    @action(detail=True, methods=["get"], url_path="photo")
    def photo(self, request, pk=None):
        att = self.get_object()
        if not att.evidence_photo:
            raise Http404
        return FileResponse(att.evidence_photo.open("rb"))

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        att = review_attendance(self.get_object(), request.user)
        return Response(self.get_serializer(att).data)

    @action(detail=True, methods=["post"], permission_classes=[IsBackoffice])
    def adjust(self, request, pk=None):
        serializer = AdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            att = adjust_minutes(
                self.get_object(),
                serializer.validated_data["minutes"],
                serializer.validated_data["reason"],
                request.user,
            )
        except AttendanceLocked as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(self.get_serializer(att).data)
