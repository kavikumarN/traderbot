/** Mirrors the backend's `schemas/backtest.py` response models 1:1
 * (snake_case, Decimals serialized as strings), same convention as
 * `features/portfolio/types.ts`. */

/** Strategy registration lives in `features/strategies` now — this feature
 * only needs a narrower `StrategyType` union for its own form. */
export type StrategyType = 'EMA_CROSSOVER' | 'RSI' | 'MACD'

export interface RunBacktestRequest {
  period_start: string
  period_end: string
  interval: string
  initial_balance: string
  commission_rate: string
  slippage_bps: string
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

export interface BacktestMetrics {
  sortino_ratio: string | null
  calmar_ratio: string | null
  cagr_pct: string | null
  avg_drawdown_pct: string
  profit_factor: string | null
  expectancy: string
  avg_win: string
  avg_loss: string
  largest_win: string
  largest_loss: string
  max_consecutive_wins: number
  max_consecutive_losses: number
  exposure_pct: string
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
  metrics: BacktestMetrics
  trade_log: BacktestFill[]
  equity_curve: BacktestEquityPoint[]
}
