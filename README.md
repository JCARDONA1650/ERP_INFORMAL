# INFORMAL ERP

Aplicación web para automatizar la asistencia (QR, ubicación, foto) y la nómina en empresas de construcción. Proyecto aplicado de Ingeniería de Sistemas (UNAD).

## Estado actual

- Backend: Django 5.2 + PostgreSQL, API REST con DRF y autenticación JWT.
- Frontend: Angular (login, proyectos, trabajadores, asistencia, nómina, finanzas, reportes).
- Dominio y lógica de negocio: trabajadores con historial de tarifas, proyectos con zona de obra, asistencia con QR firmado y geocerca, nómina con ajustes y cierre auditado, finanzas por proyecto y reportes de asistencia/nómina/finanzas (Excel y PDF).
- Pruebas: 207 backend (~96 % de cobertura) y 96 frontend.
- Despliegue de producción (Docker + nginx) validado en un entorno de prueba aislado.

## Requisitos

- Docker y Docker Compose, o bien Python 3.11 y una instancia de PostgreSQL.

## Puesta en marcha con Docker

```bash
cp .env.example .env        # edita las claves antes de continuar
docker compose up --build
docker compose exec web python manage.py createsuperuser
```

La aplicación queda en http://localhost:9000/.

## Despliegue en producción (servidor propio / VPS)

Arquitectura: `nginx` (sirve Angular y hace proxy de `/api/`, `/admin/`, `/static/`) → `web` (Django + waitress) → `db` (PostgreSQL). nginx solo escucha en `127.0.0.1`; el HTTPS lo termina un proxy delante (Caddy, Traefik, etc.).

1. Copiar la plantilla y completar los valores (clave secreta, dominio, contraseña de BD):

   ```bash
   cp .env.production.example .env
   ```

2. Construir y levantar (las migraciones se aplican al arrancar `web`; los grupos de roles se crean por migración):

   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

3. Crear el primer superusuario:

   ```bash
   docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
   ```

4. Proxy HTTPS delante apuntando a `127.0.0.1:8080` (ejemplo con Caddy):

   ```
   erp.tu-dominio.com {
       reverse_proxy 127.0.0.1:8080
   }
   ```

   Tras comprobar que el HTTPS funciona, puede activarse `DJANGO_HSTS_SECONDS` (p. ej. `31536000`).

**Respaldos:** base de datos con `docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > backup.sql`, y copiar el volumen `media_data` (fotos de asistencia).

**Notas:** las fotos solo se sirven por la API autenticada (`/media/` responde 404 en nginx). Estos archivos de despliegue se validaron en un entorno de prueba aislado (proyecto Compose separado, sin tocar los datos de desarrollo): migraciones, nginx, login JWT, redirección a HTTPS detrás de proxy y pruebas automatizadas. Aun así, conviene validar también con el primer despliegue real.

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
