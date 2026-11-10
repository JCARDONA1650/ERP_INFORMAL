"""Arranca waitress para producción.

`waitress-serve` (el comando de línea de órdenes) no expone forma de marcar
un proxy de confianza, así que usa la API de Python directamente. Se confía
en cualquier peer (`trusted_proxy="*"`) porque el puerto 9000 nunca se
publica al host: dentro de docker-compose.prod.yml solo nginx puede
alcanzarlo. Sin esto, Waitress descarta X-Forwarded-Proto/-For y
DJANGO_BEHIND_PROXY no tiene efecto.
"""
from waitress import serve

from core.wsgi import application

serve(
    application,
    listen="0.0.0.0:9000",
    trusted_proxy="*",
    trusted_proxy_headers={"x-forwarded-proto", "x-forwarded-for"},
)
