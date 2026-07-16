"""Request/response models for the backtesting HTTP surface (Phase 10),
appended to the strategy engine's routes (`/strategies/{id}/backtests`).

Decimals are serialized as strings on the way out, matching the convention
established in `schemas/trading.py`/`schemas/risk.py`/`schemas/portfolio.py`.
`trade_log`/`equity_curve` are unpacked out of `Backtest.results` (a
free-form JSONB blob on the domain entity) into typed lists here — see
`app.interface.api.backtest_mappers`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.domain.exchange.enums import KlineInterval


class RunBacktestRequest(BaseModel):
    period_start: datetime
    period_end: datetime
    interval: KlineInterval = KlineInterval.ONE_HOUR
    initial_balance: Decimal = Field(default=Decimal("10000"), gt=0)
    commission_rate: Decimal = Field(default=Decimal("0.001"), ge=0, lt=1)
    #: Basis points every market-style fill (entries, stop/take-profit/
    #: trailing exits) is worsened by — see `domain.backtesting.analytics`'s
    #: `apply_slippage`. `0` (the default) matches the old no-slippage
    #: behavior exactly.
    slippage_bps: Decimal = Field(default=Decimal("0"), ge=0, le=1000)


class BacktestFillResponse(BaseModel):
    executed_at: datetime
    side: str
    price: str
    quantity: str
    commission: str
    realized_pnl: str
    cash_after: str
    position_after: str
    reason: str


class BacktestEquityPointResponse(BaseModel):
    time: datetime
    equity: str


class BacktestMetricsResponse(BaseModel):
    """The extended metrics computed in `domain.backtesting.analytics` but
    not promoted to their own `Backtest` columns (see `backtest_mappers.py`)
    — unpacked from `Backtest.results["metrics"]`, defaulting every field so
    backtests persisted before this existed still deserialize cleanly."""

    sortino_ratio: str | None = None
    calmar_ratio: str | None = None
    cagr_pct: str | None = None
    avg_drawdown_pct: str = "0"
    profit_factor: str | None = None
    expectancy: str = "0"
    avg_win: str = "0"
    avg_loss: str = "0"
    largest_win: str = "0"
    largest_loss: str = "0"
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    exposure_pct: str = "0"


class BacktestResponse(BaseModel):
    id: uuid.UUID
    strategy_id: uuid.UUID
    status: str
    period_start: datetime
    period_end: datetime
    symbol: str
    interval: str
    initial_balance: str
    final_balance: str | None
    total_return_pct: str | None
    sharpe_ratio: str | None
    max_drawdown_pct: str | None
    win_rate: str | None
    total_trades: int | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    metrics: BacktestMetricsResponse
    trade_log: list[BacktestFillResponse]
    equity_curve: list[BacktestEquityPointResponse]
