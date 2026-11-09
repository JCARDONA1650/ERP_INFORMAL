from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from core.constants import CURRENCY_CHOICES

STATUS_OPEN = "OPEN"
STATUS_CLOSED = "CLOSED"
PERIOD_STATUS = ((STATUS_OPEN, "Abierta"), (STATUS_CLOSED, "Cerrada"))

MONEY = dict(max_digits=14, decimal_places=2)


class PayrollPeriod(models.Model):
    """Periodo de nómina. project=None => todos los proyectos."""

    start_date = models.DateField("Inicio")
    end_date = models.DateField("Fin")
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, null=True, blank=True,
        verbose_name="Proyecto (opcional)",
    )
    status = models.CharField(max_length=10, choices=PERIOD_STATUS, default=STATUS_OPEN)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_payroll_periods"
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="closed_payroll_periods",
    )

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["start_date", "end_date", "project"], name="uniq_period_project"
            ),
            # En PostgreSQL NULL != NULL: se refuerza el caso "todos los proyectos".
            models.UniqueConstraint(
                fields=["start_date", "end_date"],
                condition=models.Q(project__isnull=True),
                name="uniq_period_all_projects",
            ),
        ]

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError(
                {"end_date": "La fecha final no puede ser menor que la inicial."}
            )

    @property
    def is_open(self) -> bool:
        return self.status == STATUS_OPEN

    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False)
        super().save(*args, **kwargs)

    def __str__(self):
        scope = self.project.name if self.project_id else "Todos los proyectos"
        return f"{self.start_date} → {self.end_date} • {scope} • {self.status}"


class PayrollLine(models.Model):
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name="lines")
    employee = models.ForeignKey("workers.Employee", on_delete=models.PROTECT)

    minutes = models.PositiveIntegerField(default=0)
    days = models.PositiveIntegerField("Días trabajados", default=0)
    hourly_rate = models.DecimalField(
        "Tarifa por hora (referencia)", **MONEY, validators=[MinValueValidator(Decimal("0"))]
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="USD")
    base_amount = models.DecimalField(
        **MONEY, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0"))]
    )
    adjustment = models.DecimalField("Ajuste (+/-)", **MONEY, default=Decimal("0.00"))
    notes = models.CharField("Motivo del ajuste", max_length=200, blank=True)

    class Meta:
        ordering = ["employee__full_name"]
        constraints = [
            models.UniqueConstraint(fields=["period", "employee"], name="uniq_line_employee")
        ]

    @property
    def hours_hhmm(self) -> str:
        return f"{self.minutes // 60:02d}:{self.minutes % 60:02d}"

    @property
    def total(self) -> Decimal:
        return (self.base_amount + self.adjustment).quantize(Decimal("0.01"))

    def clean(self):
        if self.adjustment and not self.notes.strip():
            raise ValidationError({"notes": "Todo ajuste de nómina requiere un motivo."})

    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.period} • {self.employee} • {self.hours_hhmm} → {self.currency} {self.total}"
