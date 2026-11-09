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


def configured_lunch_minutes(project, on_date) -> int:
    """Almuerzo configurado: regla del proyecto > regla global > 0."""
    rules = ProjectLunchRule.objects.filter(weekday=on_date.weekday(), active=True)
    rule = rules.filter(project=project).first() or rules.filter(project__isnull=True).first()
    return rule.lunch_minutes if rule else 0


def net_worked_minutes(attendance) -> int:
    """Minutos netos de una jornada.
    1) ajuste manual si existe; 2) sin ingreso/salida => 0;
    3) descuenta almuerzo configurado; sin regla: L-V descuenta 60 min si bruto > 5 h
    (sábado no descuenta); 4) redondea a 30 min."""
    if attendance.manual_minutes is not None:
        return int(attendance.manual_minutes)
    if not attendance.check_in or not attendance.check_out:
        return 0

    gross = max(0, int((attendance.check_out - attendance.check_in).total_seconds() // 60))
    lunch = configured_lunch_minutes(attendance.project, attendance.date)
    if lunch > 0:
        gross -= lunch
    elif attendance.date.weekday() != 5 and gross > LEGACY_LUNCH_THRESHOLD:
        gross -= LEGACY_LUNCH_MINUTES
    return round_to_nearest(max(0, gross))
