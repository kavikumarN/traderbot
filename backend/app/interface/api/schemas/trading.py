"""Request/response models for the trading engine's order surface.

Prices/quantities are serialized as strings on the way out, matching the
convention already established in `schemas/market.py` — round-tripping a
price through a JS `number` risks silent precision loss a trading platform
can't afford. Requests accept `Decimal` directly (Pydantic parses numeric
JSON or numeric strings into it without that risk on the way in).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.domain.exchange.enums import OrderSide, TimeInForce


class PlaceMarketOrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    side: OrderSide
    quantity: Decimal = Field(gt=0)
    strategy_id: uuid.UUID | None = None
    signal_id: uuid.UUID | None = None
    client_order_id: str | None = Field(default=None, min_length=1, max_length=36)


class PlaceLimitOrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    side: OrderSide
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)
    time_in_force: TimeInForce = TimeInForce.GTC
    strategy_id: uuid.UUID | None = None
    signal_id: uuid.UUID | None = None
    client_order_id: str | None = Field(default=None, min_length=1, max_length=36)


class PlaceStopOrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    side: OrderSide
    quantity: Decimal = Field(gt=0)
    stop_price: Decimal = Field(gt=0)
    # Omit for a stop-loss that triggers into a market order; provide for one
    # that triggers into a resting limit order (STOP_LOSS_LIMIT).
    limit_price: Decimal | None = Field(default=None, gt=0)
    strategy_id: uuid.UUID | None = None
    signal_id: uuid.UUID | None = None
    client_order_id: str | None = Field(default=None, min_length=1, max_length=36)


class OrderResponse(BaseModel):
    id: uuid.UUID
    exchange_account_id: uuid.UUID
    symbol: str
    side: str
    type: str
    status: str
    quantity: str
    executed_quantity: str
    cumulative_quote_quantity: str
    price: str | None
    stop_price: str | None
    time_in_force: str | None
    client_order_id: str
    exchange_order_id: int | None
    strategy_id: uuid.UUID | None
    signal_id: uuid.UUID | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    filled_at: datetime | None


class OrderListResponse(BaseModel):
    items: list[OrderResponse]
    offset: int
    limit: int


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    entity_type: str
    entity_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    occurred_at: datetime
    payload: dict[str, Any]
