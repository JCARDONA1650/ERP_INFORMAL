/** "1234.5" + "USD" -> "$1,234.50" según moneda; tolera valores vacíos. */
export function formatMoney(value: string | number | null | undefined, currency: string): string {
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat('es', {
    style: 'currency',
    currency,
    currencyDisplay: 'code',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(amount) ? amount : 0);
}
