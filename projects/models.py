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

    # Si es True, toda marcación (QR o asistida) debe traer una foto tomada en el momento.
    photo_required = models.BooleanField("Foto obligatoria al marcar", default=True)

    # Jornada del proyecto (informativa: una marcación fuera de ella queda para revisión).
    # work_days: días 0=lunes … 6=domingo; vacío = sin restricción de días.
    work_days = models.JSONField("Días laborales", default=list, blank=True)
    work_start = models.TimeField("Inicio de jornada", null=True, blank=True)
    work_end = models.TimeField("Fin de jornada", null=True, blank=True)

    active = models.BooleanField("Activo", default=True)

    class Meta:
        ordering = ["name"]

    def clean(self):
        days = self.work_days or []
        if not isinstance(days, list) or any(
            not isinstance(d, int) or isinstance(d, bool) or d < 0 or d > 6 for d in days
        ):
            raise ValidationError({"work_days": "Los días laborales deben ser números de 0 (lunes) a 6 (domingo)."})
        self.work_days = sorted(set(days))
        if (self.work_start is None) != (self.work_end is None):
            raise ValidationError({"work_end": "Indica la hora de inicio y la de fin de la jornada."})
        if self.work_start and self.work_end and self.work_end <= self.work_start:
            raise ValidationError({"work_end": "La hora de fin de la jornada debe ser mayor que la de inicio."})

    def outside_schedule(self, local_dt) -> bool:
        """True si `local_dt` (hora local) cae en un día no laboral o fuera del horario de la jornada."""
        if self.work_days and local_dt.weekday() not in self.work_days:
            return True
        if self.work_start and self.work_end:
            return not (self.work_start <= local_dt.time().replace(second=0, microsecond=0) <= self.work_end)
        return False

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
    # Dirección legible del punto (la devuelve el buscador de direcciones; es informativa).
    address = models.CharField("Dirección", max_length=255, blank=True)
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
