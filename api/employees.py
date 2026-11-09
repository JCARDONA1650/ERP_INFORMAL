from decimal import Decimal

from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.roles import ADMINISTRADOR, RRHH, user_has_role
from workers.models import Employee, RateHistory
from workers.services import find_similar_names, set_rate

from .permissions import BackofficeWriteSupervisorRead, IsBackoffice


class EmployeeSerializer(serializers.ModelSerializer):
    # La tarifa vigente solo cambia por el historial (endpoint /rates/).
    hourly_rate = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    initial_rate = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0"),
        write_only=True, required=False,
        help_text="Tarifa inicial vigente desde hoy (solo al crear).",
    )
    confirm_duplicate = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Employee
        fields = [
            "id", "document_id", "full_name", "position", "pay_type",
            "hourly_rate", "daily_rate", "currency", "active",
            "initial_rate", "confirm_duplicate",
        ]
        read_only_fields = ["id", "active"]

    def validate_full_name(self, value):
        return " ".join(value.strip().split())

    def validate(self, attrs):
        if self.instance is not None and "initial_rate" in attrs:
            raise serializers.ValidationError(
                {"initial_rate": "Para cambiar la tarifa usa el endpoint /rates/."}
            )
        return attrs

    def create(self, validated):
        initial = validated.pop("initial_rate", None)
        validated.pop("confirm_duplicate", None)
        employee = Employee.objects.create(**validated)
        if initial:
            set_rate(employee, initial, timezone.localdate(), user=self.context["request"].user)
            employee.refresh_from_db()
        return employee

    def update(self, instance, validated):
        validated.pop("confirm_duplicate", None)
        for key, value in validated.items():
            setattr(instance, key, value)
        instance.save()
        return instance


class RateHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RateHistory
        fields = ["id", "rate", "effective_from", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_rate(self, value):
        if value < 0:
            raise serializers.ValidationError("La tarifa no puede ser negativa.")
        return value


class EmployeeViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Trabajadores. No se borran (tienen historial): se desactivan."""

    serializer_class = EmployeeSerializer
    permission_classes = [BackofficeWriteSupervisorRead]

    def get_queryset(self):
        user = self.request.user
        qs = Employee.objects.all()
        if not user_has_role(user, ADMINISTRADOR, RRHH):  # supervisor: solo sus proyectos
            qs = qs.filter(projects__supervisors=user).distinct()

        params = self.request.query_params
        if (active := params.get("active")) in ("true", "false"):
            qs = qs.filter(active=(active == "true"))
        if search := params.get("search", "").strip():
            qs = qs.filter(Q(full_name__icontains=search) | Q(document_id__icontains=search))
        return qs.order_by("full_name")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        similar = find_similar_names(serializer.validated_data["full_name"])
        if similar.exists() and not serializer.validated_data.get("confirm_duplicate"):
            return Response(
                {
                    "detail": "Ya existe un trabajador con ese nombre. Si es otra persona, reenvía con confirm_duplicate=true.",
                    "similar": [{"id": e.pk, "full_name": e.full_name, "document_id": e.document_id} for e in similar],
                },
                status=status.HTTP_409_CONFLICT,
            )
        employee = serializer.save()
        return Response(self.get_serializer(employee).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IsBackoffice])
    def deactivate(self, request, pk=None):
        employee = self.get_object()
        employee.active = False
        employee.save()
        return Response(self.get_serializer(employee).data)

    @action(detail=True, methods=["post"], permission_classes=[IsBackoffice])
    def activate(self, request, pk=None):
        employee = self.get_object()
        employee.active = True
        employee.save()
        return Response(self.get_serializer(employee).data)

    @action(detail=True, methods=["get", "post"], url_path="rates",
            permission_classes=[IsBackoffice])
    def rates(self, request, pk=None):
        employee = self.get_object()
        if request.method == "GET":
            data = RateHistorySerializer(employee.rate_history.all(), many=True).data
            return Response(data)
        serializer = RateHistorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = set_rate(
            employee,
            serializer.validated_data["rate"],
            serializer.validated_data["effective_from"],
            user=request.user,
        )
        return Response(RateHistorySerializer(entry).data, status=status.HTTP_201_CREATED)
