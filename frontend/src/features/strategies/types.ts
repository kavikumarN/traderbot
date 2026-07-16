/** Mirrors the backend's `schemas/strategy.py` response models 1:1
 * (snake_case, Decimals serialized as strings), same convention as
 * `features/portfolio/types.ts`. */

export type StrategyStatus =
  | 'DRAFT'
  | 'VALIDATED'
  | 'BACKTESTING'
  | 'PAPER_TRADING'
  | 'LIVE'
  | 'PAUSED'
  | 'REJECTED'
  | 'RETIRED'

export type StrategyStatusAction = 'start_paper_trading' | 'promote_to_live' | 'pause' | 'retire'

/** Mirrors `_TRADEABLE_STATUSES` in the backend's
 * `update_strategy_status.py` — a strategy in one of these statuses has a
 * live `StrategyEngine` polling task running against real market data. */
export const TRADEABLE_STATUSES: StrategyStatus[] = ['LIVE', 'PAPER_TRADING']

export interface Strategy {
  id: string
  user_id: string
  name: string
  description: string
  symbol: string
  status: StrategyStatus
  version: number
  strategy_type: string
  parameters: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface CreateStrategyRequest {
  name: string
  description: string
  symbol: string
  strategy_type: string
  parameters: Record<string, unknown>
}

export interface UpdateStrategyStatusRequest {
  action: StrategyStatusAction
}

export interface StrategyType {
  strategy_type: string
}

export interface Signal {
  id: string
  strategy_id: string
  symbol: string
  side: 'BUY' | 'SELL'
  quantity: string
  target_price: string | null
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED' | 'CONSUMED'
  rejection_reason: string | null
  generated_at: string
  expires_at: string | null
}
