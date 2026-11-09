from collections import defaultdict
from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from payroll.models import PayrollLine, PayrollPeriod
from payroll.services import PayrollError, close_period, recalculate_period, set_adjustment
from projects.models import Project

from .permissions import IsAdministrador, IsBackoffice


class PayrollLineSerializer(serializers.ModelSerializer):
    employee = serializers.SerializerMethodField()
    hours = serializers.CharField(source="hours_hhmm", read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = PayrollLine
        fields = [
            "id", "employee", "minutes", "hours", "days", "hourly_rate",
            "currency", "base_amount", "adjustment", "notes", "total",
        ]
        read_only_fields = fields

    def get_employee(self, line):
        e = line.employee
        return {"id": e.pk, "full_name": e.full_name, "document_id": e.document_id}


class PayrollPeriodSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, allow_null=True
    )
    project_name = serializers.CharField(source="project.name", read_only=True, default=None)
    closed_by = serializers.SlugRelatedField(slug_field="username", read_only=True)

    class Meta:
        model = PayrollPeriod
        fields = [
            "id", "start_date", "end_date", "project", "project_name",
            "status", "created_at", "closed_at", "closed_by",
        ]
        read_only_fields = ["id", "status", "created_at", "closed_at", "closed_by"]
        # La unicidad (incluido "todos los proyectos") la valida el modelo y la API la
        # devuelve como 400; el validador automático de DRF exigiría `project`.
        validators: list = []

    def validate(self, attrs):
        start, end = attrs.get("start_date"), attrs.get("end_date")
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "La fecha final no puede ser menor que la inicial."})
        return attrs


class PayrollPeriodDetailSerializer(PayrollPeriodSerializer):
    lines = PayrollLineSerializer(many=True, read_only=True)
    totals = serializers.SerializerMethodField()

    class Meta(PayrollPeriodSerializer.Meta):
        fields = PayrollPeriodSerializer.Meta.fields + ["lines", "totals"]
        read_only_fields = fields

    def get_totals(self, period) -> dict:
        """Total a pagar por moneda (sin conversión)."""
        totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        for line in period.lines.all():
            totals[line.currency] += line.total
        return {cur: str(amount) for cur, amount in totals.items()}


class AdjustmentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    reason = serializers.CharField(max_length=200, allow_blank=True)


class PayrollPeriodViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Periodos de nómina. Sin borrado. Solo Admin/RRHH; el cierre, solo Administrador."""

    permission_classes = [IsBackoffice]

    def get_queryset(self):
        qs = PayrollPeriod.objects.select_related("project", "closed_by")
        if self.action == "retrieve":
            qs = qs.prefetch_related("lines__employee")
        p = self.request.query_params
        if (st := p.get("status")) in ("OPEN", "CLOSED"):
            qs = qs.filter(status=st)
        if project := p.get("project"):
            qs = qs.filter(project_id=project) if project.isdigit() else qs.none()
        return qs.order_by("-start_date", "-id")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PayrollPeriodDetailSerializer
        return PayrollPeriodSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def _detail(self, period):
        fresh = self.get_queryset().prefetch_related("lines__employee").get(pk=period.pk)
        return Response(PayrollPeriodDetailSerializer(fresh).data)

    @action(detail=True, methods=["post"])
    def recalculate(self, request, pk=None):
        period = self.get_object()
        try:
            recalculate_period(period, request.user)
        except PayrollError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return self._detail(period)

    @action(detail=True, methods=["post"], permission_classes=[IsAdministrador])
    def close(self, request, pk=None):
        period = self.get_object()
        try:
            close_period(period, request.user)
        except PayrollError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return self._detail(period)


class PayrollLineAdjustView(APIView):
    """Ajuste (+/-) de una línea de nómina. Exige motivo y periodo abierto."""

    permission_classes = [IsBackoffice]

    def post(self, request, pk):
        line = get_object_or_404(PayrollLine.objects.select_related("period", "employee"), pk=pk)
        serializer = AdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            line = set_adjustment(
                line,
                serializer.validated_data["amount"],
                serializer.validated_data["reason"],
                request.user,
            )
        except PayrollError as exc:
            code = status.HTTP_409_CONFLICT if "cerrado" in str(exc) else status.HTTP_400_BAD_REQUEST
            return Response({"detail": str(exc)}, status=code)
        return Response(PayrollLineSerializer(line).data)
