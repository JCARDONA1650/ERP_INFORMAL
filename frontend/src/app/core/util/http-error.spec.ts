import { HttpErrorResponse } from '@angular/common/http';

import { apiErrorMessage } from './http-error';

const err = (status: number, error?: unknown) => new HttpErrorResponse({ status, error });

describe('apiErrorMessage', () => {
  it('usa el detalle del servidor', () => {
    expect(apiErrorMessage(err(409, { detail: 'Periodo cerrado.' }))).toBe('Periodo cerrado.');
  });

  it('usa el primer error de campo', () => {
    expect(apiErrorMessage(err(400, { end_date: ['Fecha inválida.'] }))).toBe('Fecha inválida.');
  });

  it('mensajes para 0 y 403 y fallback', () => {
    expect(apiErrorMessage(err(0))).toContain('Sin conexión');
    expect(apiErrorMessage(err(403))).toContain('permisos');
    expect(apiErrorMessage(err(500))).toBe('No se pudo completar la operación.');
    expect(apiErrorMessage('x', 'otro')).toBe('otro');
  });
});
