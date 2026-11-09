# INFORMAL ERP

Aplicación web para automatizar la asistencia (QR, ubicación, foto) y la nómina en empresas de construcción. Proyecto aplicado de Ingeniería de Sistemas (UNAD).

## Estado actual

- Configuración base: Django 5.2, PostgreSQL, Docker Compose.
- Autenticación: inicio y cierre de sesión, con página de inicio protegida.
- Dominio y lógica de negocio (Fase 1, sin vistas ni API todavía): trabajadores con historial de tarifas, proyectos con zona de obra, asistencia con QR firmado y geocerca, nómina con ajustes y cierre auditado, finanzas por proyecto y datos de reportes. Cubierto por 83 pruebas.
- Pendiente: API REST (DRF + JWT) y frontend Angular.

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
core/        configuración del proyecto (settings, urls, constantes compartidas)
accounts/    inicio/cierre de sesión, roles (Supervisor, Administrador, RRHH) y bitácora de auditoría
workers/     trabajadores, tipo de pago e historial de tarifas
projects/    proyectos, supervisores, zona de obra (geocerca) y acceso por proyecto
attendance/  jornadas, marcaciones idempotentes, token QR diario y horas netas
payroll/     periodos y líneas de nómina, ajustes con motivo y cierre
finance/     ingresos y gastos por proyecto, resumen por moneda
reports/     datos de reportes de asistencia y nómina
```

Cada app separa modelos (datos) de `services.py` (reglas de negocio). Los roles son: Empleado (sin usuario, marca con QR), Supervisor, Administrador, RRHH y Super Admin (superusuario de Django).

## Flujo de ramas

- `main`: versiones estables entregadas.
- `develop`: trabajo en curso; cada funcionalidad se desarrolla en una rama `feature/*` y se integra mediante pull request.
