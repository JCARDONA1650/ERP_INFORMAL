import { HttpErrorResponse } from '@angular/common/http';

/** Convierte un error de la API en un mensaje legible (detalle, primer error de campo o genérico). */
export function apiErrorMessage(err: unknown, fallback = 'No se pudo completar la operación.'): string {
  if (!(err instanceof HttpErrorResponse)) return fallback;
  if (err.status === 0) return 'Sin conexión con el servidor.';
  if (err.status === 403) return 'No tienes permisos para esta acción.';
  const body = err.error;
  if (body && typeof body === 'object') {
    if (typeof body.detail === 'string') return body.detail;
    const first = Object.values(body).flat()[0];
    if (typeof first === 'string') return first;
  }
  return fallback;
}
