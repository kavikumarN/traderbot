"""Response models for the read-only market-data surface.

Prices/quantities are serialized as strings (matching Binance's own API
convention) rather than JSON numbers — floating-point round-tripping a
price like ``62483.13000000`` through a JS ``number`` is exactly the kind
of silent precision loss a trading platform can't afford.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SymbolInfoResponse(BaseModel):
    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    tick_size: str | None
    step_size: str | None
    min_notional: str | None


class ExchangeInfoResponse(BaseModel):
    server_time: datetime
    symbol_count: int
    symbols: list[SymbolInfoResponse]


class TickerResponse(BaseModel):
    symbol: str
    last_price: str
    bid_price: str
    ask_price: str
    high_price: str
    low_price: str
    volume: str
    quote_volume: str
    price_change_percent: str
    open_time: datetime
    close_time: datetime


class OrderBookLevelResponse(BaseModel):
    price: str
    quantity: str


class OrderBookResponse(BaseModel):
    symbol: str
    last_update_id: int
    bids: list[OrderBookLevelResponse]
    asks: list[OrderBookLevelResponse]


class CandleResponse(BaseModel):
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
    is_closed: bool
