"""Constantes compartidas entre las aplicaciones de INFORMAL ERP."""

CURRENCY_CHOICES = [
    ("USD", "USD - Dólar"),
    ("COP", "COP - Peso colombiano"),
]

SCAN_SOURCE_CHOICES = [
    ("qr", "QR"),
    ("biometric", "Biométrico"),
    ("manual", "Manual"),
]

SCAN_ACTION_CHOICES = [
    ("in", "Ingreso"),
    ("out", "Salida"),
]

WEEKDAY_CHOICES = [
    (0, "Lunes"),
    (1, "Martes"),
    (2, "Miércoles"),
    (3, "Jueves"),
    (4, "Viernes"),
    (5, "Sábado"),
    (6, "Domingo"),
]
