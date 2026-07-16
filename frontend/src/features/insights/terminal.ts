/** A Bloomberg-terminal-style palette/type scale used only within the
 * Insights feature — deliberately distinct from the rest of the app's MUI
 * theme (dense, dark, monospace, high-contrast) rather than a global theme
 * variant, since nowhere else in the product wants this look. */

export const terminal = {
  bg: '#05070a',
  panel: '#0a0e14',
  panelAlt: '#0e131a',
  border: '#1c2531',
  borderStrong: '#2a3644',
  text: '#d7dee6',
  textDim: '#5f6b7a',
  amber: '#f5a623',
  green: '#00e08c',
  red: '#ff4d4d',
  cyan: '#39c5ff',
  yellow: '#e8d44d',
} as const

export const terminalFont =
  "'Roboto Mono', 'SFMono-Regular', Consolas, 'Liberation Mono', 'Courier New', monospace"

export function impactColor(impact: string): string {
  if (impact === 'HIGH') return terminal.red
  if (impact === 'MEDIUM') return terminal.amber
  return terminal.textDim
}

export function signalColor(signal: string): string {
  if (signal === 'BULLISH') return terminal.green
  if (signal === 'BEARISH') return terminal.red
  return terminal.cyan
}
