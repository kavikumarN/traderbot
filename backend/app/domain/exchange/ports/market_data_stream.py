"""Port for push-based (WebSocket) public market data.

``subscribe_*`` methods are plain (non-``async``) methods that return an
``AsyncIterator`` — calling one just hands back an async generator, no
work happens until the caller starts iterating (`async for`). Implementors
provide this either as an ``async def ...: yield ...`` generator function
or by returning one built elsewhere; both satisfy the same call site.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.market_data import Candle, OrderBookSnapshot, Ticker, Trade


class IMarketDataStream(ABC):
    @abstractmethod
    def subscribe_ticker(self, symbol: str) -> AsyncIterator[Ticker]: ...

    @abstractmethod
    def subscribe_order_book(self, symbol: str) -> AsyncIterator[OrderBookSnapshot]: ...

    @abstractmethod
    def subscribe_candles(self, symbol: str, interval: KlineInterval) -> AsyncIterator[Candle]: ...

    @abstractmethod
    def subscribe_trades(self, symbol: str) -> AsyncIterator[Trade]: ...

    @abstractmethod
    async def close(self) -> None: ...
