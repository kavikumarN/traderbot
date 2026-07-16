"""Response models for the Portfolio read/aggregation surface (Phase 9).

Read-only — there is no request body anywhere in this module, only query
params on the routes themselves. Decimals are serialized as strings on the
way out, matching the convention established in `schemas/trading.py` and
`schemas/risk.py`.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class WalletResponse(BaseModel):
    id: uuid.UUID
    asset: str
    free: str
    locked: str
    total: str
    updated_at: datetime


class PositionResponse(BaseModel):
    id: uuid.UUID
    symbol: str
    quantity: str
    avg_entry_price: str
    current_price: str
    market_value: str
    unrealized_pnl: str
    unrealized_pnl_pct: str
    realized_pnl: str
    opened_at: datetime
    updated_at: datetime


class TradeResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    symbol: str
    side: str
    price: str
    quantity: str
    quote_quantity: str
    commission: str
    commission_asset: str | None
    executed_at: datetime


class TradeHistoryResponse(BaseModel):
    items: list[TradeResponse]
    offset: int
    limit: int


class PortfolioSummaryResponse(BaseModel):
    cash: str
    positions_value: str
    equity: str
    realized_pnl: str
    unrealized_pnl: str
    total_pnl: str
    roi_pct: str | None
    fees_by_asset: dict[str, str]
    open_position_count: int
    total_trade_count: int


class EquityPointResponse(BaseModel):
    date: date
    equity: str
    realized_pnl_cum: str
    fees_cum: str


class MonthlyReturnResponse(BaseModel):
    month: str
    return_pct: str
    pnl: str


class PerformanceResponse(BaseModel):
    points: list[EquityPointResponse]
    monthly_returns: list[MonthlyReturnResponse]
    sharpe_ratio: str | None
    max_drawdown_pct: str
    current_drawdown_pct: str
    starting_equity: str
    current_equity: str
