import { hhmmToMinutes, minutesToHhmm } from './time';

describe('time utils', () => {
  it('convierte minutos a HH:MM', () => {
    expect(minutesToHhmm(480)).toBe('08:00');
    expect(minutesToHhmm(510)).toBe('08:30');
    expect(minutesToHhmm(0)).toBe('00:00');
    expect(minutesToHhmm(-5)).toBe('00:00');
  });

  it('convierte HH:MM a minutos y rechaza formatos inválidos', () => {
    expect(hhmmToMinutes('08:30')).toBe(510);
    expect(hhmmToMinutes('8:00')).toBe(480);
    expect(hhmmToMinutes('08:75')).toBeNull();
    expect(hhmmToMinutes('abc')).toBeNull();
    expect(hhmmToMinutes('')).toBeNull();
  });
});
