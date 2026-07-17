/** Mirrors the backend's `schemas/risk.py` response models 1:1
 * (snake_case, Decimals serialized as strings), same convention as
 * `features/portfolio/types.ts`. */

export type RiskRuleType =
  | 'MAX_POSITION_NOTIONAL'
  | 'MAX_DAILY_LOSS'
  | 'MAX_ORDER_RATE'
  | 'SYMBOL_WHITELIST'
  | 'MAX_DRAWDOWN'
  | 'MAX_LEVERAGE'
  | 'MAX_OPEN_TRADES'
  | 'MAX_PORTFOLIO_EXPOSURE'
  | 'RISK_PER_TRADE'
  | 'DRAWDOWN_DERISK'

export type CircuitBreakerState = 'CLOSED' | 'OPEN'

export interface RiskRule {
  id: string
  user_id: string
  strategy_id: string | null
  rule_type: RiskRuleType
  threshold: string | null
  is_active: boolean
  config: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface CreateRiskRuleRequest {
  rule_type: RiskRuleType
  threshold?: string | null
  strategy_id?: string | null
  is_active: boolean
  config: Record<string, unknown>
}

export interface UpdateRiskRuleRequest {
  is_active?: boolean
  threshold?: string | null
  config?: Record<string, unknown>
}

export interface RiskState {
  user_id: string
  circuit_breaker: CircuitBreakerState
  circuit_breaker_reason: string | null
  circuit_breaker_tripped_at: string | null
  circuit_breaker_resume_at: string | null
  emergency_stop: boolean
  emergency_stop_reason: string | null
  emergency_stop_at: string | null
  consecutive_losses: number
  daily_loss: string
  daily_loss_date: string | null
  equity_peak: string
  de_risked: boolean
  de_risk_multiplier: string
  de_risk_reason: string | null
  de_risked_at: string | null
  is_trading_allowed: boolean
  updated_at: string
}

export interface SetEmergencyStopRequest {
  active: boolean
  reason?: string | null
}

export interface PositionSizeRequest {
  side: 'BUY' | 'SELL'
  entry_price: string
  stop_loss_price?: string | null
  stop_loss_pct?: string | null
  risk_per_trade_pct?: string | null
  reward_risk_ratio?: string | null
}

export interface PositionSizeResponse {
  quantity: string
  stop_loss_price: string
  take_profit_price: string
  equity: string
}
