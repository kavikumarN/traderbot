/** Small formatting helpers shared by any feature displaying backend
 * Decimals (which arrive as strings — see e.g. `features/portfolio/types.ts`,
 * `features/backtesting/types.ts`); these are the only place that
 * `Number()`-converts them for display — never for further math. */

const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 2,
})

const numberFormatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 8 })

const percentFormatter = new Intl.NumberFormat('en-US', {
  style: 'percent',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export function formatCurrency(value: string | number): string {
  return currencyFormatter.format(Number(value))
}

export function formatQuantity(value: string | number): string {
  return numberFormatter.format(Number(value))
}

export function formatPercent(value: string | number | null): string {
  if (value === null) return '—'
  return percentFormatter.format(Number(value))
}

export function formatSharpe(value: string | null): string {
  if (value === null) return '—'
  return Number(value).toFixed(2)
}

export function isNonNegative(value: string): boolean {
  return Number(value) >= 0
}
