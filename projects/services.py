"""Reglas de negocio de proyectos: acceso y zona de obra."""
import math
from decimal import Decimal

from .models import Project

EARTH_RADIUS_M = 6_371_000


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Distancia en metros entre dos coordenadas (fórmula de Haversine)."""
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = p2 - p1
    dlmb = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def distance_to_site_m(project: Project, latitude, longitude):
    """Metros entre un punto y el centro de la zona; None si no se puede calcular."""
    site = getattr(project, "site", None)
    if site is None or latitude is None or longitude is None:
        return None
    return haversine_m(site.latitude, site.longitude, latitude, longitude)


def is_in_zone(project: Project, latitude, longitude):
    """True/False si hay zona y coordenadas; None si no se puede determinar.
    Qué se hace al estar fuera lo decide `site.out_of_zone_policy`
    (rechazar o dejar para revisión); eso se aplica en `register_scan`."""
    distance = distance_to_site_m(project, latitude, longitude)
    if distance is None:
        return None
    return distance <= project.site.radius_m


def user_can_access_project(user, project: Project) -> bool:
    if not user.is_authenticated:
        return False
    return user.is_superuser or project.supervisors.filter(pk=user.pk).exists()


def projects_for(user):
    """Proyectos que el usuario puede ver (sin N+1: usa los M2M directos)."""
    if user.is_superuser:
        return Project.objects.all()
    return Project.objects.filter(supervisors=user)


from django.db import transaction  # noqa: E402

from .models import ProjectSite  # noqa: E402


def project_lunch(project: Project):
    """(inicio, fin, personalizado) del almuerzo del proyecto.
    Es 'personalizado' cuando las reglas difieren entre días (se cargaron en el administrador):
    en ese caso no se puede representar con un solo horario y no se edita desde la pantalla."""
    rules = [r for r in project.lunch_rules.all() if r.active]  # se precarga con prefetch_related
    if not rules:
        return None, None, False
    spans = {(r.start_time, r.end_time) for r in rules}
    if len(spans) > 1:
        return None, None, True
    start, end = next(iter(spans))
    return start, end, False


@transaction.atomic
def set_project_lunch(project: Project, start, end) -> None:
    """Reemplaza el almuerzo del proyecto: un horario para sus días laborales (o toda la semana
    si no hay días definidos). `start`/`end` en None lo elimina (sin almuerzo configurado)."""
    from attendance.models import ProjectLunchRule  # import local: evita ciclo

    ProjectLunchRule.objects.filter(project=project).delete()
    if start is None or end is None:
        return
    for weekday in project.work_days or range(7):
        ProjectLunchRule.objects.create(project=project, weekday=weekday, start_time=start, end_time=end)


@transaction.atomic
def save_project_site(project: Project, data):
    """Crea, actualiza o elimina la zona de obra. `data=None` la elimina."""
    if data is None:
        ProjectSite.objects.filter(project=project).delete()
        return None
    site, _ = ProjectSite.objects.get_or_create(
        project=project,
        defaults={"latitude": data["latitude"], "longitude": data["longitude"]},
    )
    for key in ("latitude", "longitude", "radius_m", "out_of_zone_policy", "address"):
        if key in data:
            setattr(site, key, data[key])
    site.save()
    return site
