FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Usuario sin privilegios
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 9000

CMD ["waitress-serve", "--listen=0.0.0.0:9000", "core.wsgi:application"]
