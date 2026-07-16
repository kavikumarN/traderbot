"""Request/response models for the strategy engine's HTTP surface.

Quantities/prices are serialized as strings on the way out, matching the
convention established in `schemas/trading.py` and `schemas/market.py`.
`parameters` stays a free-form object both ways — each plugin defines its
own shape and validates it in `initialize()`, so this layer deliberately
doesn't try to model it more strictly than "a JSON object".
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.application.use_cases.strategies.update_strategy_status import StrategyStatusAction
from app.domain.exchange.enums import OrderSide


class CreateStrategyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    symbol: str = Field(min_length=1, max_length=20)
    strategy_type: str = Field(min_length=1, max_length=50)
    parameters: dict[str, Any] = Field(default_factory=dict)


class UpdateStrategyStatusRequest(BaseModel):
    action: StrategyStatusAction


class StrategyResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str
    symbol: str
    status: str
    version: int
    strategy_type: str
    parameters: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SignalResponse(BaseModel):
    id: uuid.UUID
    strategy_id: uuid.UUID
    symbol: str
    side: OrderSide
    quantity: str
    target_price: str | None
    status: str
    rejection_reason: str | None
    generated_at: datetime
    expires_at: datetime | None


class StrategyTypeResponse(BaseModel):
    strategy_type: str
