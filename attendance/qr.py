"""Token firmado del QR diario de un proyecto (válido solo el día en que se emite)."""
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils import timezone

SALT = "kiosk-scan-v1"
MAX_AGE_SECONDS = 36 * 3600


class QRTokenError(Exception):
    pass


def make_qr_token(project, day=None) -> str:
    day = day or timezone.localdate()
    return TimestampSigner(salt=SALT).sign(f"{project.pk}:{project.qr_secret}:{day.isoformat()}")


def verify_qr_token(project, token: str) -> None:
    """Lanza QRTokenError si el token no corresponde al proyecto o al día de hoy."""
    if not token:
        raise QRTokenError("Token requerido.")
    try:
        data = TimestampSigner(salt=SALT).unsign(token, max_age=MAX_AGE_SECONDS)
    except SignatureExpired:
        raise QRTokenError("Token expirado.")
    except BadSignature:
        raise QRTokenError("Token inválido.")

    parts = data.split(":")
    if len(parts) != 3:
        raise QRTokenError("Token inválido.")
    proj_id, secret, token_day = parts
    if str(project.pk) != proj_id or secret != project.qr_secret:
        raise QRTokenError("Token inválido.")
    if token_day != timezone.localdate().isoformat():
        raise QRTokenError("Token expirado para el día de hoy.")
