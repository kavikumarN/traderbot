/** Mirrors the backend's `schemas/backtest.py` response models 1:1
 * (snake_case, Decimals serialized as strings), same convention as
 * `features/portfolio/types.ts`. */

export type StrategyType = 'EMA_CROSSOVER' | 'RSI' | 'MACD'

export interface CreateStrategyRequest {
  name: string
  description: string
  symbol: string
  strategy_type: StrategyType
  parameters: Record<string, unknown>
}

export interface StrategyResponse {
  id: string
  user_id: string
  name: string
  description: string
  symbol: string
  status: string
  version: number
  strategy_type: string
  parameters: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface RunBacktestRequest {
  period_start: string
  period_end: string
  interval: string
  initial_balance: string
  commission_rate: string
}

export interface BacktestFill {
  executed_at: string
  side: string
  price: string
  quantity: string
  commission: string
  realized_pnl: string
  cash_after: string
  position_after: string
  reason: string
}

export interface BacktestEquityPoint {
  time: string
  equity: string
}

export interface Backtest {
  id: string
  strategy_id: string
  status: string
  period_start: string
  period_end: string
  symbol: string
  interval: string
  initial_balance: string
  final_balance: string | null
  total_return_pct: string | null
  sharpe_ratio: string | null
  max_drawdown_pct: string | null
  win_rate: string | null
  total_trades: number | null
  error_message: string | null
  created_at: string
  completed_at: string | null
  trade_log: BacktestFill[]
  equity_curve: BacktestEquityPoint[]
}
