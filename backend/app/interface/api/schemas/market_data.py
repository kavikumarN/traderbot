"""Response models for the *persisted* market-data surface (Phase 5).

Distinct from `schemas/market.py`, which proxies Binance live (no
storage involved). These serve what `MarketDataService` has actually
written to Postgres/TimescaleDB. Same string-serialization convention for
prices/quantities as `schemas/market.py` — see that module's docstring.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PersistedCandleResponse(BaseModel):
    symbol: str
    interval: str
    open_time: datetime
    close_time: datetime
    open: str
    high: str
    low: str
    close: str
    volume: str
    quote_volume: str
    trade_count: int


class MarketTickResponse(BaseModel):
    symbol: str
    trade_id: int
    price: str
    quantity: str
    quote_quantity: str
    traded_at: datetime
    is_buyer_maker: bool


class PersistedOrderBookLevelResponse(BaseModel):
    price: str
    quantity: str


class PersistedOrderBookResponse(BaseModel):
    symbol: str
    last_update_id: int
    bids: list[PersistedOrderBookLevelResponse]
    asks: list[PersistedOrderBookLevelResponse]
    retrieved_at: datetime
