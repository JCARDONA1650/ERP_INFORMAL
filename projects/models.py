import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify

from core.constants import CURRENCY_CHOICES


class Project(models.Model):
    name = models.CharField("Proyecto", max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)

    supervisors = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="supervised_projects", blank=True
    )
    employees = models.ManyToManyField(
        "workers.Employee", related_name="projects", blank=True
    )

    contract_value = models.DecimalField(
        "Valor del contrato",
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    contract_currency = models.CharField(
        "Moneda del contrato", max_length=3, choices=CURRENCY_CHOICES, default="USD"
    )

    # Secreto propio del proyecto: firma el QR del día.
    qr_secret = models.CharField(
        max_length=64, default=secrets.token_urlsafe, editable=False
    )

    active = models.BooleanField("Activo", default=True)

    class Meta:
        ordering = ["name"]

    def _unique_slug(self):
        base = slugify(self.name) or "proyecto"
        slug, counter = base, 1
        while Project.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            counter += 1
            slug = f"{base}-{counter}"
        return slug

    def save(self, *args, **kwargs):
        if self.name:
            self.name = " ".join(self.name.strip().split())
        if not self.slug:
            self.slug = self._unique_slug()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


POLICY_BLOCK = "block"    # rechaza la marcación fuera de la zona
POLICY_REVIEW = "review"  # la acepta y la deja pendiente de revisión
OUT_OF_ZONE_CHOICES = [
    (POLICY_BLOCK, "Rechazar marcación fuera de la zona"),
    (POLICY_REVIEW, "Permitir y marcar para revisión"),
]


class ProjectSite(models.Model):
    """Zona de obra: punto central y radio. Define qué es 'dentro de la zona'."""

    project = models.OneToOneField(
        Project, on_delete=models.CASCADE, related_name="site"
    )
    latitude = models.DecimalField(
        "Latitud",
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))],
    )
    longitude = models.DecimalField(
        "Longitud",
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))],
    )
    radius_m = models.PositiveIntegerField(
        "Radio permitido (m)",
        default=150,
        validators=[MinValueValidator(10), MaxValueValidator(5000)],
    )
    # Qué pasa si el trabajador marca fuera del radio (o sin ubicación).
    out_of_zone_policy = models.CharField(
        "Política fuera de zona",
        max_length=10,
        choices=OUT_OF_ZONE_CHOICES,
        default=POLICY_BLOCK,
    )

    def clean(self):
        if self.radius_m is not None and self.radius_m < 10:
            raise ValidationError({"radius_m": "El radio mínimo es 10 metros."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Zona de {self.project} ({self.radius_m} m)"
