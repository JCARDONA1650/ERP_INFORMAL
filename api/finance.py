from datetime import date

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import mixins, serializers, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.models import ProjectExpense, ProjectIncome
from finance.services import expenses_by_category, project_summary, record_movement, update_movement
from projects.models import Project

from .permissions import IsAdministrador


class _MovementSerializer(serializers.ModelSerializer):
    created_by = serializers.SlugRelatedField(slug_field="username", read_only=True)
    currency = serializers.ChoiceField(
        choices=ProjectIncome._meta.get_field("currency").choices, required=False, allow_blank=True
    )

    base_fields = ["id", "project", "date", "amount", "currency", "description", "created_by", "created_at"]

    def validate(self, attrs):
        if self.instance is not None and "project" in attrs and attrs["project"] != self.instance.project:
            raise serializers.ValidationError(
                {"project": "No se puede mover un movimiento a otro proyecto."}
            )
        return attrs

    def create(self, validated):
        if not validated.get("currency"):
            validated.pop("currency", None)  # el modelo usa la moneda del contrato
        return record_movement(self.Meta.model, self.context["request"].user, **validated)

    def update(self, instance, validated):
        validated.pop("project", None)
        return update_movement(instance, self.context["request"].user, **validated)


class IncomeSerializer(_MovementSerializer):
    class Meta:
        model = ProjectIncome
        fields = _MovementSerializer.base_fields
        read_only_fields = ["id", "created_by", "created_at"]


class ExpenseSerializer(_MovementSerializer):
    class Meta:
        model = ProjectExpense
        fields = _MovementSerializer.base_fields + ["category"]
        read_only_fields = ["id", "created_by", "created_at"]


class _MovementViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Sin borrado: un error se corrige editando; todo cambio queda auditado."""

    permission_classes = [IsAdministrador]
    model = None

    def get_queryset(self):
        qs = self.model.objects.select_related("project", "created_by")
        p = self.request.query_params
        filters = {
            "project": "project_id",
            "date_from": "date__gte",
            "date_to": "date__lte",
            "currency": "currency",
            "category": "category",
        }
        try:
            for param, lookup in filters.items():
                if (value := p.get(param)) and (param != "category" or hasattr(self.model, "category")):
                    qs = qs.filter(**{lookup: value})
        except (ValueError, TypeError, DjangoValidationError) as exc:
            raise serializers.ValidationError({"detail": "Filtro con valor inválido."}) from exc
        return qs.order_by("-date", "-id")


class IncomeViewSet(_MovementViewSet):
    model = ProjectIncome
    serializer_class = IncomeSerializer


class ExpenseViewSet(_MovementViewSet):
    model = ProjectExpense
    serializer_class = ExpenseSerializer


class ProjectFinanceSummaryView(APIView):
    """Ingresos, gastos y balance del proyecto, por moneda (sin convertir)."""

    permission_classes = [IsAdministrador]

    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        try:
            date_from = self._date(request, "date_from")
            date_to = self._date(request, "date_to")
        except ValueError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc

        summary = project_summary(project, date_from, date_to)
        by_category = expenses_by_category(project, date_from, date_to)
        return Response(
            {
                "project": {"id": project.pk, "name": project.name},
                "contract": {
                    "value": str(summary["contract_value"]),
                    "currency": summary["contract_currency"],
                    "billed_pct": None if summary["billed_pct"] is None else str(summary["billed_pct"]),
                },
                "incomes": {c: str(v) for c, v in summary["incomes"].items()},
                "expenses": {c: str(v) for c, v in summary["expenses"].items()},
                "balance": {c: str(v) for c, v in summary["balance"].items()},
                "expenses_by_category": [
                    {"category": cat, "currency": cur, "total": str(total)}
                    for (cat, cur), total in sorted(by_category.items())
                ],
            }
        )

    @staticmethod
    def _date(request, name):
        raw = request.query_params.get(name)
        if not raw:
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError:
            raise ValueError(f"{name} debe tener formato AAAA-MM-DD.")
