from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.domain.exchange.enums import OrderSide
from app.domain.strategy.enums import BacktestStatus, SignalStatus, StrategyStatus


@dataclass(slots=True)
class Strategy:
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str
    symbol: str
    status: StrategyStatus
    version: int
    created_at: datetime
    updated_at: datetime
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def is_live(self) -> bool:
        return self.status == StrategyStatus.LIVE

    def promote_to_live(self) -> None:
        if self.status != StrategyStatus.PAPER_TRADING:
            raise ValueError(f"Cannot promote a strategy from {self.status} directly to LIVE")
        self.status = StrategyStatus.LIVE

    def pause(self) -> None:
        if self.status != StrategyStatus.LIVE:
            raise ValueError("Only a LIVE strategy can be paused")
        self.status = StrategyStatus.PAUSED


@dataclass(slots=True)
class Signal:
    id: uuid.UUID
    strategy_id: uuid.UUID
    symbol: str
    side: OrderSide
    quantity: Decimal
    status: SignalStatus
    generated_at: datetime
    target_price: Decimal | None = None
    rejection_reason: str | None = None
    expires_at: datetime | None = None

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and now >= self.expires_at

    def is_actionable(self, now: datetime) -> bool:
        return self.status == SignalStatus.PENDING and not self.is_expired(now)


@dataclass(slots=True)
class Backtest:
    id: uuid.UUID
    strategy_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    status: BacktestStatus
    initial_balance: Decimal
    created_at: datetime
    final_balance: Decimal | None = None
    sharpe_ratio: Decimal | None = None
    max_drawdown: Decimal | None = None
    win_rate: Decimal | None = None
    total_trades: int | None = None
    error_message: str | None = None
    completed_at: datetime | None = None
    results: dict[str, Any] = field(default_factory=dict)

    @property
    def total_return(self) -> Decimal | None:
        if self.final_balance is None or self.initial_balance == 0:
            return None
        return (self.final_balance - self.initial_balance) / self.initial_balance
