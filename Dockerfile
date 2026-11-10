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
# Se manda un Host válido (el primero de DJANGO_ALLOWED_HOSTS) para no depender
# de agregar 127.0.0.1 a ALLOWED_HOSTS, que nginx reenviaría tal cual desde fuera.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os, urllib.request; h = (os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost').split(',')[0].strip().lstrip('.') or 'localhost'); urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:9000/api/health/', headers={'Host': h}), timeout=4)" || exit 1

CMD ["python", "wsgi_serve.py"]
