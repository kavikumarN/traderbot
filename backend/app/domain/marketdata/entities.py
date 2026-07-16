"""Market-data bounded context: this platform's own durable store of
candles and raw trade prints, populated by ingesting Phase 3's Binance
streams. `KlineInterval` is reused from `app.domain.exchange` as a shared
kernel — "a candle has an interval" is the same concept whether it just
arrived over a WebSocket or is being read back out of TimescaleDB.

Both entities are stored in TimescaleDB hypertables (see
`infrastructure/db/models/marketdata.py`), so neither carries a surrogate
`id`: the natural key (symbol, interval, time) / (symbol, time, trade_id)
*is* the primary key, which is standard practice for high-volume
append-only time-series tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.exchange.enums import KlineInterval


@dataclass(frozen=True, slots=True)
class PersistedCandle:
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


@dataclass(frozen=True, slots=True)
class MarketTick:
    symbol: str
    trade_id: int
    price: Decimal
    quantity: Decimal
    quote_quantity: Decimal
    traded_at: datetime
    is_buyer_maker: bool
