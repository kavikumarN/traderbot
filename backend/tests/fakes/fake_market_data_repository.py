from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from app.application.ports.market_data_repository import MarketDataRepository
from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.market_data import Candle, OrderBookSnapshot, Ticker, Trade
from app.domain.marketdata.entities import MarketTick, PersistedCandle


class FakeMarketDataRepository(MarketDataRepository):
    """In-memory `MarketDataRepository`. `*_side_effect` hooks let a test
    make a specific save raise, to verify `MarketDataService` contains the
    failure instead of losing the whole stream — see
    `tests/fakes/fake_websocket.py` for the same scripted-failure idea
    applied one layer down."""

    def __init__(self) -> None:
        self.saved_candles: list[Candle] = []
        self.saved_trades: list[Trade] = []
        self.saved_order_books: list[OrderBookSnapshot] = []
        self.saved_volume_stats: list[Ticker] = []
        self.candle_side_effect: Callable[[Candle], None] | None = None

    async def save_candle(self, candle: Candle) -> None:
        if self.candle_side_effect is not None:
            self.candle_side_effect(candle)
        self.saved_candles.append(candle)

    async def save_trade(self, trade: Trade) -> None:
        self.saved_trades.append(trade)

    async def save_order_book(self, snapshot: OrderBookSnapshot) -> None:
        self.saved_order_books.append(snapshot)

    async def save_volume_stats(self, ticker: Ticker) -> None:
        self.saved_volume_stats.append(ticker)

    async def get_candles(
        self, symbol: str, interval: KlineInterval, *, start: datetime, end: datetime
    ) -> list[PersistedCandle]:
        return []

    async def get_recent_trades(self, symbol: str, *, limit: int = 100) -> list[MarketTick]:
        return []

    async def get_order_book(self, symbol: str) -> OrderBookSnapshot | None:
        return None

    async def get_volume_stats(self, symbol: str) -> Ticker | None:
        return None


class FakeBroadcaster:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict]] = []

    async def broadcast(self, symbol: str, message: dict) -> None:
        self.messages.append((symbol, message))
