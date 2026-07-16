"""Public market-data models — no authentication required to obtain these
from an exchange, and no exchange-specific fields leak through."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.exchange.enums import KlineInterval


@dataclass(frozen=True, slots=True)
class Candle:
    symbol: str
    interval: KlineInterval
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Decimal
    trade_count: int
    is_closed: bool = True


@dataclass(frozen=True, slots=True)
class Ticker:
    symbol: str
    last_price: Decimal
    bid_price: Decimal
    ask_price: Decimal
    high_price: Decimal
    low_price: Decimal
    volume: Decimal
    quote_volume: Decimal
    price_change_percent: Decimal
    open_time: datetime
    close_time: datetime


@dataclass(frozen=True, slots=True)
class OrderBookLevel:
    price: Decimal
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class OrderBookSnapshot:
    symbol: str
    last_update_id: int
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]
    retrieved_at: datetime

    @property
    def best_bid(self) -> OrderBookLevel | None:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> OrderBookLevel | None:
        return self.asks[0] if self.asks else None

    @property
    def spread(self) -> Decimal | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask.price - self.best_bid.price


@dataclass(frozen=True, slots=True)
class Trade:
    symbol: str
    trade_id: int
    price: Decimal
    quantity: Decimal
    quote_quantity: Decimal
    traded_at: datetime
    is_buyer_maker: bool
