"""Request/response models for the Risk Engine's HTTP surface (Phase 8).

Quantities/prices/thresholds are serialized as strings on the way out,
matching the convention established in `schemas/trading.py` and
`schemas/strategy.py`; requests accept `Decimal` directly.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.domain.exchange.enums import OrderSide
from app.domain.risk.enums import CircuitBreakerState, RiskRuleType


class CreateRiskRuleRequest(BaseModel):
    rule_type: RiskRuleType
    threshold: Decimal | None = Field(default=None, gt=0)
    strategy_id: uuid.UUID | None = None
    is_active: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class UpdateRiskRuleRequest(BaseModel):
    is_active: bool | None = None
    threshold: Decimal | None = Field(default=None, gt=0)
    config: dict[str, Any] | None = None


class RiskRuleResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    strategy_id: uuid.UUID | None
    rule_type: RiskRuleType
    threshold: str | None
    is_active: bool
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class RiskStateResponse(BaseModel):
    user_id: uuid.UUID
    circuit_breaker: CircuitBreakerState
    circuit_breaker_reason: str | None
    circuit_breaker_tripped_at: datetime | None
    circuit_breaker_resume_at: datetime | None
    emergency_stop: bool
    emergency_stop_reason: str | None
    emergency_stop_at: datetime | None
    consecutive_losses: int
    daily_loss: str
    daily_loss_date: date | None
    equity_peak: str
    de_risked: bool
    de_risk_multiplier: str
    de_risk_reason: str | None
    de_risked_at: datetime | None
    is_trading_allowed: bool
    updated_at: datetime


class SetEmergencyStopRequest(BaseModel):
    active: bool
    reason: str | None = Field(default=None, max_length=500)


class PositionSizeRequest(BaseModel):
    side: OrderSide
    entry_price: Decimal = Field(gt=0)
    stop_loss_price: Decimal | None = Field(default=None, gt=0)
    stop_loss_pct: Decimal | None = Field(default=None, gt=0, lt=1)
    risk_per_trade_pct: Decimal | None = Field(default=None, gt=0, lt=1)
    reward_risk_ratio: Decimal | None = Field(default=None, gt=0)


class PositionSizeResponse(BaseModel):
    quantity: str
    stop_loss_price: str
    take_profit_price: str
    equity: str
