/** Mirrors the backend's `schemas/trading.py` response models 1:1
 * (snake_case, Decimals serialized as strings), same convention as
 * `features/portfolio/types.ts`. */

export type OrderSide = 'BUY' | 'SELL'
export type TimeInForce = 'GTC' | 'IOC' | 'FOK'

export interface Order {
  id: string
  exchange_account_id: string
  symbol: string
  side: string
  type: string
  status: string
  quantity: string
  executed_quantity: string
  cumulative_quote_quantity: string
  price: string | null
  stop_price: string | null
  time_in_force: string | null
  client_order_id: string
  exchange_order_id: number | null
  strategy_id: string | null
  signal_id: string | null
  rejection_reason: string | null
  created_at: string
  updated_at: string
  submitted_at: string | null
  filled_at: string | null
}

export interface OrderListResponse {
  items: Order[]
  offset: number
  limit: number
}

interface BaseOrderRequest {
  symbol: string
  side: OrderSide
  quantity: string
  strategy_id?: string | null
  signal_id?: string | null
  client_order_id?: string | null
}

export interface PlaceMarketOrderRequest extends BaseOrderRequest {}

export interface PlaceLimitOrderRequest extends BaseOrderRequest {
  price: string
  time_in_force?: TimeInForce
}

export interface PlaceStopOrderRequest extends BaseOrderRequest {
  stop_price: string
  limit_price?: string | null
}

export interface AuditLogEntry {
  id: string
  event_type: string
  entity_type: string
  entity_id: string | null
  actor_user_id: string | null
  occurred_at: string
  payload: Record<string, unknown>
}
