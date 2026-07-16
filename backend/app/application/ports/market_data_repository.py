"""Port for the market-data engine's persistence needs.

Distinct from the granular `CandleRepository` / `MarketTickRepository` /
`OrderBookRepository` / `VolumeStatsRepository` ports (`app.domain.marketdata`)
that back it: those are the general-purpose, per-bounded-context repository
pattern used throughout the app (and reachable via `UnitOfWork` inside a
request). This port is a thin aggregate purpose-built for `MarketDataService`
— a *long-lived background singleton*, not a per-request use case — so its
implementation manages its own database sessions (opened and closed per
call) rather than participating in a request-scoped `UnitOfWork` transaction.

Write methods accept the same live-stream types `IMarketDataStream` yields
(`Candle`, `Trade`, `OrderBookSnapshot`, `Ticker`) so the service can pass
stream events straight through without knowing anything about storage
shape; the adapter is responsible for translating into whatever the
underlying repositories persist.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.market_data import Candle, OrderBookSnapshot, Ticker, Trade
from app.domain.marketdata.entities import MarketTick, PersistedCandle


class MarketDataRepository(ABC):
    @abstractmethod
    async def save_candle(self, candle: Candle) -> None: ...

    @abstractmethod
    async def save_trade(self, trade: Trade) -> None: ...

    @abstractmethod
    async def save_order_book(self, snapshot: OrderBookSnapshot) -> None: ...

    @abstractmethod
    async def save_volume_stats(self, ticker: Ticker) -> None: ...

    @abstractmethod
    async def get_candles(
        self, symbol: str, interval: KlineInterval, *, start: datetime, end: datetime
    ) -> list[PersistedCandle]: ...

    @abstractmethod
    async def get_recent_trades(self, symbol: str, *, limit: int = 100) -> list[MarketTick]: ...

    @abstractmethod
    async def get_order_book(self, symbol: str) -> OrderBookSnapshot | None: ...

    @abstractmethod
    async def get_volume_stats(self, symbol: str) -> Ticker | None: ...
