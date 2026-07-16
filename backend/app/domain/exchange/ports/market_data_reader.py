"""Port for pull-based (REST) public market data.

Narrow by design (Interface Segregation): a component that only ever reads
candles has no business depending on order-placement or account methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.exchange_info import ExchangeInfo
from app.domain.exchange.models.market_data import Candle, OrderBookSnapshot, Ticker, Trade


class IMarketDataReader(ABC):
    @abstractmethod
    async def get_exchange_info(self) -> ExchangeInfo: ...

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker: ...

    @abstractmethod
    async def get_order_book(self, symbol: str, *, limit: int = 100) -> OrderBookSnapshot: ...

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        interval: KlineInterval,
        *,
        limit: int = 500,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[Candle]: ...

    @abstractmethod
    async def get_recent_trades(self, symbol: str, *, limit: int = 500) -> list[Trade]: ...
