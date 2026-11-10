"""Marcación pública del trabajador: sin usuario, validada con el QR firmado del día."""
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from attendance.qr import QRTokenError, verify_qr_token
from attendance.services import ScanError, register_scan
from projects.models import Project

MAX_PHOTO_BYTES = 5 * 1024 * 1024


class ScanSerializer(serializers.Serializer):
    employee = serializers.IntegerField()
    action = serializers.ChoiceField(choices=["in", "out"])
    photo = serializers.ImageField(required=True)  # constancia obligatoria
    latitude = serializers.FloatField(required=False, allow_null=True, min_value=-90, max_value=90)
    longitude = serializers.FloatField(required=False, allow_null=True, min_value=-180, max_value=180)
    client_uuid = serializers.UUIDField(required=False)
    device_ts = serializers.DateTimeField(required=False)
    device_name = serializers.CharField(required=False, allow_blank=True, max_length=100)

    def validate_photo(self, photo):
        if photo.size > MAX_PHOTO_BYTES:
            raise serializers.ValidationError("La foto supera el máximo de 5 MB.")
        return photo

    def validate(self, attrs):
        if (attrs.get("latitude") is None) != (attrs.get("longitude") is None):
            raise serializers.ValidationError("Envía latitud y longitud juntas o ninguna.")
        return attrs


class _PublicScanView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "scan"

    def load_project(self, request, slug) -> Project:
        project = get_object_or_404(
            Project.objects.select_related("site"), slug=slug, active=True
        )
        try:
            verify_qr_token(project, request.query_params.get("t", ""))
        except QRTokenError as exc:
            raise serializers.ValidationError({"detail": str(exc)}, code="forbidden") from exc
        return project

    def handle_exception(self, exc):
        if isinstance(exc, serializers.ValidationError) and getattr(exc, "get_codes", None):
            codes = exc.get_codes()
            if isinstance(codes, dict) and codes.get("detail") == "forbidden":
                return Response(
                    {"detail": exc.detail["detail"]}, status=status.HTTP_403_FORBIDDEN
                )
        return super().handle_exception(exc)


class ScanContextView(_PublicScanView):
    """Datos para pintar la pantalla de marcación: proyecto y trabajadores activos asignados."""

    def get(self, request, slug):
        project = self.load_project(request, slug)
        employees = project.employees.filter(active=True).order_by("full_name")
        site = getattr(project, "site", None)
        return Response(
            {
                "project": {"name": project.name, "slug": project.slug},
                # La zona se expone solo con QR válido: permite mostrar "dentro/fuera" al trabajador.
                "site": None if site is None else {
                    "latitude": float(site.latitude),
                    "longitude": float(site.longitude),
                    "radius_m": site.radius_m,
                    "out_of_zone_policy": site.out_of_zone_policy,
                    "address": site.address,
                },
                "employees": [{"id": e.pk, "full_name": e.full_name} for e in employees],
            }
        )


class ScanView(_PublicScanView):
    def post(self, request, slug):
        project = self.load_project(request, slug)
        serializer = ScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        employee = project.employees.filter(pk=data["employee"], active=True).first()
        if employee is None:
            raise serializers.ValidationError(
                {"employee": "El trabajador no está asignado a este proyecto."}
            )

        try:
            result = register_scan(
                project,
                employee,
                data["action"],
                source="qr",  # el origen lo fija el servidor: el cliente no puede declararse manual/biométrico
                device_ts=data.get("device_ts"),
                client_uuid=data.get("client_uuid"),
                latitude=data.get("latitude"),
                longitude=data.get("longitude"),
                device_name=data.get("device_name", ""),
                photo=data["photo"],
            )
        except ScanError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(
            {
                "message": result.message,
                "duplicate": result.duplicate,
                "in_zone": result.in_zone,
            },
            status=status.HTTP_200_OK if result.duplicate else status.HTTP_201_CREATED,
        )
