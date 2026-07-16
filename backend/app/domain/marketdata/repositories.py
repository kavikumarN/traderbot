from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.market_data import OrderBookSnapshot, Ticker
from app.domain.marketdata.entities import MarketTick, PersistedCandle


class CandleRepository(ABC):
    @abstractmethod
    async def upsert(self, candle: PersistedCandle) -> None:
        """A still-forming candle is re-upserted on every close; the
        natural key (symbol, interval, open_time) makes this idempotent."""
        ...

    @abstractmethod
    async def upsert_many(self, candles: list[PersistedCandle]) -> None:
        """Bulk path for backfilling history fetched from `GET /klines`."""
        ...

    @abstractmethod
    async def list_range(
        self, symbol: str, interval: KlineInterval, *, start: datetime, end: datetime
    ) -> list[PersistedCandle]: ...

    @abstractmethod
    async def get_latest(self, symbol: str, interval: KlineInterval) -> PersistedCandle | None: ...


class MarketTickRepository(ABC):
    @abstractmethod
    async def add(self, tick: MarketTick) -> None: ...

    @abstractmethod
    async def add_many(self, ticks: list[MarketTick]) -> None: ...

    @abstractmethod
    async def list_range(
        self, symbol: str, *, start: datetime, end: datetime, limit: int = 1000
    ) -> list[MarketTick]: ...


class OrderBookRepository(ABC):
    """Holds only the latest snapshot per symbol — order-book depth is
    display/decisioning state, not a historical record worth keeping every
    100ms revision of. `OrderBookSnapshot` (the same type the REST and
    WebSocket layers already use) is reused directly as the shared-kernel
    storage shape, matching how `KlineInterval` is reused above.
    """

    @abstractmethod
    async def upsert(self, snapshot: OrderBookSnapshot) -> None: ...

    @abstractmethod
    async def get_latest(self, symbol: str) -> OrderBookSnapshot | None: ...


class VolumeStatsRepository(ABC):
    """Latest 24h rolling stats per symbol, fed by the ticker stream.
    Distinct from `CandleRepository`: candles are an OHLCV time series,
    this is a single always-current snapshot per symbol for "how much is
    trading right now" style reads.
    """

    @abstractmethod
    async def upsert(self, ticker: Ticker) -> None: ...

    @abstractmethod
    async def get_latest(self, symbol: str) -> Ticker | None: ...
