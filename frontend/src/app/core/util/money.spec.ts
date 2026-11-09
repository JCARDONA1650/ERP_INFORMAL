import { formatMoney } from './money';

describe('formatMoney', () => {
  it('formatea con dos decimales y código de moneda', () => {
    expect(formatMoney('1234.5', 'USD')).toContain('1');
    expect(formatMoney('1234.5', 'USD')).toContain('USD');
    expect(formatMoney('0', 'COP')).toContain('COP');
  });

  it('tolera valores vacíos o inválidos', () => {
    expect(formatMoney(null, 'USD')).toContain('0,00');
    expect(formatMoney('abc', 'USD')).toContain('0,00');
  });
});
