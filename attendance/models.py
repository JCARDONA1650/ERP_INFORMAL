import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from core.constants import SCAN_ACTION_CHOICES, SCAN_SOURCE_CHOICES, WEEKDAY_CHOICES


class ProjectLunchRule(models.Model):
    """Regla de almuerzo por día de la semana. project=None => regla global."""

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="lunch_rules",
        null=True,
        blank=True,
        verbose_name="Proyecto",
    )
    weekday = models.PositiveSmallIntegerField("Día", choices=WEEKDAY_CHOICES)
    start_time = models.TimeField("Inicio almuerzo")
    end_time = models.TimeField("Fin almuerzo")
    active = models.BooleanField("Activo", default=True)

    class Meta:
        ordering = ["project__name", "weekday", "start_time"]

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError(
                {"end_time": "La hora final del almuerzo debe ser mayor que la hora inicial."}
            )

    @property
    def lunch_minutes(self) -> int:
        start = self.start_time.hour * 60 + self.start_time.minute
        end = self.end_time.hour * 60 + self.end_time.minute
        return max(0, end - start)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        scope = self.project.name if self.project else "GLOBAL"
        return f"{scope} • {self.get_weekday_display()} • {self.start_time} - {self.end_time}"


def evidence_upload_path(instance, filename):
    emp_slug = slugify(instance.employee.full_name) or "empleado"
    return f"attendance/{instance.project.slug}/{emp_slug}/{instance.date:%Y/%m/%d}/{filename}"


class Attendance(models.Model):
    """Jornada diaria de un trabajador en un proyecto (una por proyecto/trabajador/día)."""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, verbose_name="Proyecto"
    )
    employee = models.ForeignKey(
        "workers.Employee", on_delete=models.PROTECT, verbose_name="Trabajador"
    )
    date = models.DateField("Fecha", default=timezone.localdate)

    check_in = models.DateTimeField("Hora ingreso", blank=True, null=True)
    check_out = models.DateTimeField("Hora salida", blank=True, null=True)
    check_in_source = models.CharField(
        "Método ingreso", max_length=20, choices=SCAN_SOURCE_CHOICES, default="qr"
    )
    check_out_source = models.CharField(
        "Método salida", max_length=20, choices=SCAN_SOURCE_CHOICES, default="qr"
    )

    evidence_photo = models.ImageField(
        "Foto constancia", upload_to=evidence_upload_path, blank=True, null=True
    )
    notes = models.CharField("Observaciones", max_length=200, blank=True)

    manual_minutes = models.PositiveIntegerField(
        null=True, blank=True, help_text="Minutos netos ajustados tras revisión."
    )
    manual_note = models.CharField("Motivo del ajuste", max_length=200, blank=True)

    # Geocerca: fuera de zona NO bloquea; solo marca para revisión.
    in_zone = models.BooleanField(
        "Dentro de zona", null=True, blank=True,
        help_text="None = no se pudo determinar (sin zona o sin ubicación).",
    )
    needs_review = models.BooleanField("Requiere revisión", default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "employee", "date"], name="uniq_attendance_day"
            )
        ]
        indexes = [
            models.Index(fields=["date", "project"]),
            models.Index(fields=["employee", "date"]),
        ]
        ordering = ["-date", "project__name", "employee__full_name"]

    def clean(self):
        if self.check_in and self.check_out and self.check_out < self.check_in:
            raise ValidationError(
                {"check_out": "La hora de salida no puede ser menor que la de ingreso."}
            )
        if self.manual_minutes is not None and not self.manual_note.strip():
            raise ValidationError(
                {"manual_note": "Todo ajuste manual requiere un motivo."}
            )

    def worked_minutes(self) -> int:
        from .services import net_worked_minutes

        return net_worked_minutes(self)

    def worked_hhmm(self) -> str:
        m = self.worked_minutes()
        return f"{m // 60:02d}:{m % 60:02d}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.project} • {self.employee} • {self.date} ({self.worked_hhmm()})"


class AttendanceScan(models.Model):
    """Evento de marcación (QR / biométrico / manual). `client_uuid` evita duplicados
    en reintentos offline. No guarda datos biométricos crudos."""

    client_uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    employee = models.ForeignKey("workers.Employee", on_delete=models.PROTECT)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, null=True, blank=True
    )
    action = models.CharField(max_length=10, choices=SCAN_ACTION_CHOICES)
    device_ts = models.DateTimeField()
    server_ts = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=20, choices=SCAN_SOURCE_CHOICES, default="qr")
    device_name = models.CharField("Dispositivo", max_length=100, blank=True)
    verification_reference = models.CharField(
        "Referencia verificación", max_length=120, blank=True,
        help_text="Referencia del proveedor biométrico/dispositivo. Nunca datos biométricos crudos.",
    )

    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))],
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))],
    )
    in_zone = models.BooleanField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["employee", "server_ts"]),
            models.Index(fields=["project", "server_ts"]),
        ]
        ordering = ["-server_ts"]

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.employee} • {self.get_action_display()} • "
            f"{self.get_source_display()} • {self.device_ts:%Y-%m-%d %H:%M}"
        )
