"""Marcación asistida: el Supervisor (sus proyectos) o el Administrador registran ingreso/salida
de un trabajador que no tiene celular. Exige foto tomada en el momento y valida la ubicación
del dispositivo de quien marca con la misma política de zona del proyecto."""
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.roles import ADMINISTRADOR, SUPERVISOR, user_has_role
from accounts.services import audit
from attendance.services import ScanError, register_scan
from projects.models import Project

from .permissions import HasAnyRole
from .scan import ScanSerializer, require_photo_if_needed


class CanMarkForOthers(HasAnyRole):
    """Supervisor o Administrador (el superusuario siempre). RRHH no marca."""

    allowed_roles = (SUPERVISOR, ADMINISTRADOR)


def _projects_for(user):
    qs = Project.objects.filter(active=True).select_related("site").prefetch_related("employees")
    if not user_has_role(user, ADMINISTRADOR):  # el Supervisor solo ve sus proyectos
        qs = qs.filter(supervisors=user)
    return qs.order_by("name")


class ManualScanSerializer(ScanSerializer):
    project = serializers.IntegerField()


class ManualScanContextView(APIView):
    """Proyectos activos que el usuario puede atender, con su zona y trabajadores activos."""

    permission_classes = [IsAuthenticated, CanMarkForOthers]

    def get(self, request):
        data = []
        for project in _projects_for(request.user):
            site = getattr(project, "site", None)
            data.append(
                {
                    "id": project.pk,
                    "name": project.name,
                    "photo_required": project.photo_required,
                    "site": None if site is None else {
                        "latitude": float(site.latitude),
                        "longitude": float(site.longitude),
                        "radius_m": site.radius_m,
                        "out_of_zone_policy": site.out_of_zone_policy,
                        "address": site.address,
                    },
                    "employees": [
                        {"id": e.pk, "full_name": e.full_name}
                        for e in sorted(project.employees.all(), key=lambda e: e.full_name)
                        if e.active
                    ],
                }
            )
        return Response(data)


class ManualScanView(APIView):
    permission_classes = [IsAuthenticated, CanMarkForOthers]

    def post(self, request):
        serializer = ManualScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        project = _projects_for(request.user).filter(pk=data["project"]).first()
        if project is None:
            raise serializers.ValidationError(
                {"project": "No tienes asignado este proyecto o no está activo."}
            )
        require_photo_if_needed(project, data)
        employee = next(
            (e for e in project.employees.all() if e.pk == data["employee"] and e.active), None
        )
        if employee is None:
            raise serializers.ValidationError(
                {"employee": "El trabajador no está asignado a este proyecto."}
            )

        try:
            result = register_scan(
                project,
                employee,
                data["action"],
                source="manual",  # lo fija el servidor
                device_ts=data.get("device_ts"),
                client_uuid=data.get("client_uuid"),
                latitude=data.get("latitude"),
                longitude=data.get("longitude"),
                device_name=data.get("device_name", ""),
                verification_reference=f"manual:{request.user.username}",
                photo=data.get("photo"),
            )
        except ScanError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        if not result.duplicate:
            audit(
                request.user,
                "marcar_manual",
                "Attendance",
                result.attendance.pk,
                f"{data['action']} · {employee.full_name} · {project.name}",
            )
        return Response(
            {"message": result.message, "duplicate": result.duplicate, "in_zone": result.in_zone},
            status=status.HTTP_200_OK if result.duplicate else status.HTTP_201_CREATED,
        )
