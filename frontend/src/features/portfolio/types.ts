/** Mirrors the backend's `schemas/portfolio.py` response models 1:1
 * (snake_case, Decimals serialized as strings — see that module's own
 * docstring for why) rather than translating field names, matching the
 * convention `AuthUser` already established for direct API responses. */

export interface Wallet {
  id: string
  asset: string
  free: string
  locked: string
  total: string
  updated_at: string
}

export interface Position {
  id: string
  symbol: string
  quantity: string
  avg_entry_price: string
  current_price: string
  market_value: string
  unrealized_pnl: string
  unrealized_pnl_pct: string
  realized_pnl: string
  opened_at: string
  updated_at: string
}

export interface Trade {
  id: string
  order_id: string
  symbol: string
  side: string
  price: string
  quantity: string
  quote_quantity: string
  commission: string
  commission_asset: string | null
  executed_at: string
}

export interface TradeHistory {
  items: Trade[]
  offset: number
  limit: number
}

export interface PortfolioSummary {
  cash: string
  positions_value: string
  equity: string
  realized_pnl: string
  unrealized_pnl: string
  total_pnl: string
  roi_pct: string | null
  fees_by_asset: Record<string, string>
  open_position_count: number
  total_trade_count: number
}

export interface EquityPoint {
  date: string
  equity: string
  realized_pnl_cum: string
  fees_cum: string
}

export interface MonthlyReturn {
  month: string
  return_pct: string
  pnl: string
}

export interface Performance {
  points: EquityPoint[]
  monthly_returns: MonthlyReturn[]
  sharpe_ratio: string | null
  max_drawdown_pct: string
  current_drawdown_pct: string
  starting_equity: string
  current_equity: string
}
