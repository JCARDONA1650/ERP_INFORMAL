"""Buscador de direcciones para ubicar la zona de obra (Nominatim / OpenStreetMap).

La consulta la hace el servidor: así se envía un User-Agent identificable, se cachean los
resultados (OSM pide no repetir consultas) y el navegador no necesita conectarse a un tercero."""
import hashlib
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .permissions import IsBackoffice

logger = logging.getLogger("api")
CACHE_SECONDS = 24 * 3600
TIMEOUT = 6


class GeocoderUnavailable(Exception):
    """El servicio externo no respondió o devolvió algo inválido."""


def _fetch(path: str, params: dict):
    """GET JSON al geocodificador. Aislado para poder simularlo en pruebas."""
    url = f"{settings.GEOCODER_URL.rstrip('/')}/{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url, headers={"User-Agent": settings.GEOCODER_USER_AGENT, "Accept-Language": "es,en"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 - host fijo de configuración
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        logger.warning("Geocodificador no disponible: %s", exc)
        raise GeocoderUnavailable from exc


def search_address(query: str) -> list[dict]:
    key = "geo:s:" + hashlib.sha1(query.lower().encode()).hexdigest()
    if (hit := cache.get(key)) is not None:
        return hit
    raw = _fetch(
        "search",
        {
            "q": query, "format": "jsonv2", "limit": 5, "addressdetails": 0,
            "countrycodes": settings.GEOCODER_COUNTRIES,
        },
    )
    results = [
        {"label": r["display_name"], "latitude": round(float(r["lat"]), 6), "longitude": round(float(r["lon"]), 6)}
        for r in raw
        if "lat" in r and "lon" in r and "display_name" in r
    ]
    cache.set(key, results, CACHE_SECONDS)
    return results


def reverse_address(lat: float, lon: float) -> str:
    key = f"geo:r:{lat:.5f},{lon:.5f}"
    if (hit := cache.get(key)) is not None:
        return hit
    raw = _fetch("reverse", {"lat": f"{lat:.6f}", "lon": f"{lon:.6f}", "format": "jsonv2", "zoom": 18})
    label = raw.get("display_name", "") if isinstance(raw, dict) else ""
    cache.set(key, label, CACHE_SECONDS)
    return label


class _GeoView(APIView):
    permission_classes = [IsBackoffice]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "geocode"

    def handle_exception(self, exc):
        if isinstance(exc, GeocoderUnavailable):
            return Response(
                {"detail": "No se pudo consultar el servicio de direcciones. Inténtalo de nuevo."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return super().handle_exception(exc)


class AddressSearchView(_GeoView):
    def get(self, request):
        query = " ".join(request.query_params.get("q", "").split())
        if len(query) < 3 or len(query) > 200:
            raise serializers.ValidationError({"detail": "Escribe al menos 3 caracteres de la dirección."})
        return Response({"results": search_address(query)})


class AddressReverseView(_GeoView):
    def get(self, request):
        try:
            lat = float(request.query_params["lat"])
            lon = float(request.query_params["lon"])
        except (KeyError, ValueError):
            raise serializers.ValidationError({"detail": "lat y lon son obligatorios."}) from None
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise serializers.ValidationError({"detail": "Coordenadas fuera de rango."})
        return Response({"address": reverse_address(lat, lon)})
