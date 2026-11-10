from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from core.constants import CURRENCY_CHOICES

MONEY = dict(max_digits=14, decimal_places=2)
POSITIVE = [MinValueValidator(Decimal("0.00"))]


class _Movement(models.Model):
    """Base abstracta de movimientos del proyecto. Sin moneda explícita usa la del contrato."""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="%(class)ss"
    )
    date = models.DateField()
    amount = models.DecimalField(**MONEY, validators=POSITIVE)
    currency = models.CharField("Moneda", max_length=3, choices=CURRENCY_CHOICES, blank=True)
    description = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-date", "-id"]

    def save(self, *args, **kwargs):
        if not self.currency and self.project_id:
            self.currency = self.project.contract_currency
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectIncome(_Movement):
    class Meta(_Movement.Meta):
        indexes = [models.Index(fields=["project", "date"])]

    def __str__(self):
        return f"[{self.project}] {self.date} • +{self.currency} {self.amount}"


class ProjectExpense(_Movement):
    CATEGORY = [
        ("materials", "Materiales"),
        ("transport", "Transporte"),
        ("meals", "Comida"),
        ("tools", "Herramientas"),
        ("payroll", "Nómina"),
        ("other", "Otros"),
    ]
    category = models.CharField(max_length=20, choices=CATEGORY, default="other")
    # Gasto generado automáticamente al cerrar una nómina. No se edita a mano: se rehace
    # reabriendo y cerrando de nuevo el periodo.
    payroll_period = models.ForeignKey(
        "payroll.PayrollPeriod", null=True, blank=True, on_delete=models.PROTECT,
        related_name="expenses", verbose_name="Periodo de nómina",
    )

    class Meta(_Movement.Meta):
        indexes = [models.Index(fields=["project", "date"])]

    def __str__(self):
        return f"[{self.project}] {self.date} • {self.get_category_display()} • -{self.currency} {self.amount}"
