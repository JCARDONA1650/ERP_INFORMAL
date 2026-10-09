# INFORMAL ERP

Aplicación web para automatizar la asistencia (QR, ubicación, foto) y la nómina en empresas de construcción. Proyecto aplicado de Ingeniería de Sistemas (UNAD).

## Estado actual

- Configuración base: Django 5.2, PostgreSQL, Docker Compose.
- Autenticación: inicio y cierre de sesión, con página de inicio protegida.

## Requisitos

- Docker y Docker Compose, o bien Python 3.11 y una instancia de PostgreSQL.

## Puesta en marcha con Docker

```bash
cp .env.example .env        # edita las claves antes de continuar
docker compose up --build
docker compose exec web python manage.py createsuperuser
```

La aplicación queda en http://localhost:9000/.

## Pruebas

```bash
docker compose exec web python manage.py test
```

## Estructura

```
core/       configuración del proyecto (settings, urls, wsgi/asgi)
accounts/   inicio/cierre de sesión y página de inicio
```

## Flujo de ramas

- `main`: versiones estables entregadas.
- `develop`: trabajo en curso; cada funcionalidad se desarrolla en una rama `feature/*` y se integra mediante pull request.
