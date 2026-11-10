import { monthRange } from './month';

describe('monthRange', () => {
  it('devuelve el primer y último día del mes', () => {
    expect(monthRange('2026-11')).toEqual({ from: '2026-11-01', to: '2026-11-30' });
    expect(monthRange('2026-12')).toEqual({ from: '2026-12-01', to: '2026-12-31' });
  });

  it('respeta los años bisiestos', () => {
    expect(monthRange('2028-02')?.to).toBe('2028-02-29');
    expect(monthRange('2026-02')?.to).toBe('2026-02-28');
  });

  it('devuelve null si el valor está vacío o es inválido', () => {
    expect(monthRange('')).toBeNull();
    expect(monthRange('2026-13')).toBeNull();
  });
});
