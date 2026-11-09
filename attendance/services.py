"""Reglas de negocio de asistencia: almuerzo, horas netas y redondeo."""
from .models import ProjectLunchRule

ROUND_STEP = 30
LEGACY_LUNCH_MINUTES = 60
LEGACY_LUNCH_THRESHOLD = 300  # bruto > 5 h


def round_to_nearest(minutes: int, step: int = ROUND_STEP) -> int:
    """Redondea al múltiplo de `step` más cercano (la mitad sube)."""
    minutes = max(0, int(minutes))
    remainder = minutes % step
    if remainder < step / 2:
        return minutes - remainder
    return minutes + (step - remainder)


def lunch_minutes_map() -> dict:
    """{(project_id|None, weekday): minutos} de reglas activas, en una sola consulta."""
    return {
        (r.project_id, r.weekday): r.lunch_minutes
        for r in ProjectLunchRule.objects.filter(active=True)
    }


def lunch_from_map(lunch_map: dict, project_id, on_date) -> int:
    """Almuerzo de un día usando el mapa precargado: regla del proyecto > global > 0."""
    wd = on_date.weekday()
    return lunch_map.get((project_id, wd), lunch_map.get((None, wd), 0))


def configured_lunch_minutes(project, on_date) -> int:
    """Almuerzo configurado: regla del proyecto > regla global > 0."""
    rules = ProjectLunchRule.objects.filter(weekday=on_date.weekday(), active=True)
    rule = rules.filter(project=project).first() or rules.filter(project__isnull=True).first()
    return rule.lunch_minutes if rule else 0


def net_worked_minutes(attendance, lunch_minutes=None) -> int:
    """Minutos netos de una jornada.
    1) ajuste manual si existe; 2) sin ingreso/salida => 0;
    3) descuenta almuerzo configurado; sin regla: L-V descuenta 60 min si bruto > 5 h
    (sábado no descuenta); 4) redondea a 30 min.
    `lunch_minutes` permite pasar el almuerzo ya resuelto (reportes masivos sin
    consultar la base por jornada)."""
    if attendance.manual_minutes is not None:
        return int(attendance.manual_minutes)
    if not attendance.check_in or not attendance.check_out:
        return 0

    gross = max(0, int((attendance.check_out - attendance.check_in).total_seconds() // 60))
    lunch = (
        lunch_minutes if lunch_minutes is not None
        else configured_lunch_minutes(attendance.project, attendance.date)
    )
    if lunch > 0:
        gross -= lunch
    elif attendance.date.weekday() != 5 and gross > LEGACY_LUNCH_THRESHOLD:
        gross -= LEGACY_LUNCH_MINUTES
    return round_to_nearest(max(0, gross))


# ───────────────── Registro de marcaciones ─────────────────
import logging
import uuid as uuid_lib
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.db import models, transaction
from django.utils import timezone

from projects.services import is_in_zone

from .models import Attendance, AttendanceScan

logger = logging.getLogger(__name__)


def _coord(value):
    """Normaliza una coordenada GPS a 6 decimales (el GPS entrega más precisión)."""
    if value in (None, ""):
        return None
    return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


class ScanError(Exception):
    """Marcación no permitida (p. ej. salida sin ingreso, trabajador inactivo)."""


@dataclass
class ScanResult:
    attendance: Attendance
    duplicate: bool
    message: str
    in_zone: bool | None


@transaction.atomic
def register_scan(
    project,
    employee,
    action: str,
    *,
    source: str = "qr",
    device_ts=None,
    client_uuid=None,
    latitude=None,
    longitude=None,
    device_name: str = "",
    verification_reference: str = "",
    photo=None,
) -> ScanResult:
    """Registra un ingreso ('in') o salida ('out').

    - Idempotente por `client_uuid` (reintentos offline no duplican).
    - Fuera de zona NO bloquea: marca la jornada `needs_review`.
    - Salida sin ingreso previo => ScanError.
    """
    if action not in ("in", "out"):
        raise ScanError("Acción inválida.")
    if not employee.active:
        raise ScanError("El trabajador está inactivo.")

    client_uuid = client_uuid or uuid_lib.uuid4()
    now = timezone.now()
    today = timezone.localdate(now)

    existing = AttendanceScan.objects.filter(client_uuid=client_uuid).first()
    if existing:
        att = Attendance.objects.filter(
            project=project, employee=employee, date=today
        ).first()
        return ScanResult(att, True, "Marcación ya registrada.", existing.in_zone)

    latitude, longitude = _coord(latitude), _coord(longitude)
    in_zone = is_in_zone(project, latitude, longitude)
    project.employees.add(employee)

    AttendanceScan.objects.create(
        client_uuid=client_uuid,
        employee=employee,
        project=project,
        action=action,
        device_ts=device_ts or now,
        source=source,
        device_name=device_name[:100],
        verification_reference=verification_reference[:120],
        latitude=latitude,
        longitude=longitude,
        in_zone=in_zone,
    )

    att, _ = Attendance.objects.select_for_update().get_or_create(
        project=project, employee=employee, date=today
    )
    if photo:
        att.evidence_photo = photo
    if in_zone is not None:
        att.in_zone = in_zone if att.in_zone is not False else False
    if in_zone is False:
        att.needs_review = True

    local = timezone.localtime(now).strftime("%H:%M")
    if action == "in":
        if att.check_in is None:
            att.check_in, att.check_in_source = now, source
            msg = f"Ingreso registrado: {employee.full_name} a las {local}."
        else:
            msg = f"{employee.full_name} ya tenía ingreso registrado."
    else:
        if att.check_in is None:
            raise ScanError("No hay ingreso previo. Primero registra la entrada.")
        if att.check_out is None:
            att.check_out, att.check_out_source = now, source
        att.save()
        m = att.worked_minutes()
        msg = (
            f"Salida registrada: {employee.full_name} a las {local}. "
            f"Tiempo neto trabajado: {m // 60:02d}:{m % 60:02d}."
        )
    att.save()
    logger.info(
        "Marcación: proyecto=%s trabajador=%s acción=%s fuente=%s en_zona=%s",
        project.pk, employee.pk, action, source, in_zone,
    )
    return ScanResult(att, False, msg, in_zone)


# ───────────────── Revisión y ajuste manual ─────────────────
from accounts.services import audit  # noqa: E402


class AttendanceLocked(Exception):
    """La jornada pertenece a una nómina cerrada y no admite ajustes."""


@transaction.atomic
def review_attendance(attendance: Attendance, user) -> Attendance:
    """Marca la jornada como revisada, registrando quién y cuándo."""
    attendance.needs_review = False
    attendance.reviewed_by = user
    attendance.reviewed_at = timezone.now()
    attendance.save()
    audit(user, "revisar", "Attendance", attendance.pk, str(attendance))
    return attendance


@transaction.atomic
def adjust_minutes(attendance: Attendance, minutes: int, reason: str, user) -> Attendance:
    """Ajuste manual de minutos netos. Exige motivo y que la nómina no esté cerrada."""
    from payroll.models import STATUS_CLOSED, PayrollPeriod  # import local: evita ciclo

    if not reason or not reason.strip():
        raise ValueError("Todo ajuste manual requiere un motivo.")
    if PayrollPeriod.objects.filter(
        status=STATUS_CLOSED,
        start_date__lte=attendance.date,
        end_date__gte=attendance.date,
    ).filter(models.Q(project__isnull=True) | models.Q(project=attendance.project)).exists():
        raise AttendanceLocked("La jornada pertenece a una nómina cerrada.")

    before = attendance.worked_minutes()
    attendance.manual_minutes = int(minutes)
    attendance.manual_note = reason.strip()
    attendance.save()
    audit(user, "ajustar", "Attendance", attendance.pk, f"{before} -> {minutes} min: {reason.strip()}")
    return attendance
