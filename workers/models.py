from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

from core.constants import CURRENCY_CHOICES

PAY_HOURLY = "hourly"
PAY_DAILY = "daily"
PAY_TYPE_CHOICES = [
    (PAY_HOURLY, "Por hora"),
    (PAY_DAILY, "Por día"),
]

name_validator = RegexValidator(
    regex=r"^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$",
    message="El nombre solo puede contener letras y espacios.",
)

document_validator = RegexValidator(
    regex=r"^[A-Za-z0-9\-\.]+$",
    message="El documento solo puede contener letras, números, guiones o puntos.",
)


class Employee(models.Model):
    """Trabajador. El identificador interno (pk) es lo que identifica a la persona,
    no el nombre: puede haber homónimos."""

    document_id = models.CharField(
        "Documento / ID",
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        validators=[document_validator],
        help_text="Opcional. Puede contener letras, números, guiones o puntos.",
    )
    full_name = models.CharField(
        "Nombre completo", max_length=150, validators=[name_validator]
    )
    position = models.CharField("Cargo", max_length=100, blank=True)

    pay_type = models.CharField(
        "Tipo de pago", max_length=10, choices=PAY_TYPE_CHOICES, default=PAY_HOURLY
    )
    hourly_rate = models.DecimalField(
        "Tarifa por hora vigente",
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    daily_rate = models.DecimalField(
        "Valor por día (supervisores)",
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    currency = models.CharField(
        "Moneda", max_length=3, choices=CURRENCY_CHOICES, default="USD"
    )

    active = models.BooleanField("Activo", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]

    def _normalize(self):
        if self.full_name:
            self.full_name = " ".join(self.full_name.strip().split())
        if self.document_id:
            self.document_id = self.document_id.strip().upper()
        else:
            # Evita que '' choque con la restricción de unicidad.
            self.document_id = None

    def clean(self):
        self._normalize()

    def save(self, *args, **kwargs):
        # Se normaliza antes de validar para que los validadores vean el valor final.
        self._normalize()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.document_id:
            return f"{self.full_name} ({self.document_id})"
        return self.full_name


class RateHistory(models.Model):
    """Tarifa por hora con su fecha de vigencia. La nómina aplica cada tarifa
    a los días que le corresponden (cambios a mitad de quincena)."""

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="rate_history"
    )
    rate = models.DecimalField(
        "Tarifa por hora",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    effective_from = models.DateField("Vigente desde")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_from", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "effective_from"], name="uniq_rate_employee_date"
            )
        ]

    def clean(self):
        if self.rate is not None and self.rate < Decimal("0.00"):
            raise ValidationError({"rate": "La tarifa no puede ser negativa."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee} • {self.rate} desde {self.effective_from}"
