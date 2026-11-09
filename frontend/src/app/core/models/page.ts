/** Respuesta paginada de la API (DRF PageNumberPagination). */
export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
