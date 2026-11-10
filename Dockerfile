FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Archivos estáticos del admin (los sirve whitenoise). La clave es solo para este paso.
RUN DJANGO_SECRET_KEY=build-only-not-a-secret python manage.py collectstatic --noinput

# Usuario sin privilegios; /app/media es donde se guardan las fotos de constancia.
RUN useradd --create-home appuser \
    && mkdir -p /app/media \
    && chown -R appuser /app
USER appuser

EXPOSE 9000

# Estado del servicio (responde 503 si la base de datos no contesta).
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9000/api/health/', timeout=4)" || exit 1

CMD ["waitress-serve", "--listen=0.0.0.0:9000", "core.wsgi:application"]
