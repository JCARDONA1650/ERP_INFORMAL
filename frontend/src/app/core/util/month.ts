/** Convierte un valor de <input type="month"> ("2026-11") en el primer y último día del mes. */
export function monthRange(value: string): { from: string; to: string } | null {
  const m = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(value ?? '');
  if (!m) return null;
  const year = Number(m[1]);
  const month = Number(m[2]);
  const last = new Date(year, month, 0).getDate();
  return { from: `${m[1]}-${m[2]}-01`, to: `${m[1]}-${m[2]}-${String(last).padStart(2, '0')}` };
}
