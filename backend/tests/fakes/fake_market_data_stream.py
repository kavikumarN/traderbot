from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TypeVar

from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.market_data import Candle, OrderBookSnapshot, Ticker, Trade
from app.domain.exchange.ports.market_data_stream import IMarketDataStream

T = TypeVar("T")

# Sentinel: when present in a scripted list, the generator blocks forever
# (until the consuming task is cancelled) instead of completing — lets a
# test simulate "the stream is still live" so it can exercise `stop()`.
BLOCK = object()


class FakeMarketDataStream(IMarketDataStream):
    """Scripted `IMarketDataStream`: each `subscribe_*` call is fed from a
    dict keyed by symbol (or (symbol, interval) for candles), consumed in
    order. Mirrors `tests/fakes/fake_websocket.py`'s scripted-connection
    style but at the domain-event level, since `MarketDataService` depends
    on the port, not on `BinanceMarketDataStream`/`websockets` directly."""

    def __init__(self) -> None:
        self.tickers: dict[str, list[object]] = {}
        self.order_books: dict[str, list[object]] = {}
        self.candles: dict[tuple[str, KlineInterval], list[object]] = {}
        self.trades: dict[str, list[object]] = {}
        self.closed = False

    def subscribe_ticker(self, symbol: str) -> AsyncIterator[Ticker]:
        return self._iter(self.tickers.get(symbol, []))

    def subscribe_order_book(self, symbol: str) -> AsyncIterator[OrderBookSnapshot]:
        return self._iter(self.order_books.get(symbol, []))

    def subscribe_candles(self, symbol: str, interval: KlineInterval) -> AsyncIterator[Candle]:
        return self._iter(self.candles.get((symbol, interval), []))

    def subscribe_trades(self, symbol: str) -> AsyncIterator[Trade]:
        return self._iter(self.trades.get(symbol, []))

    async def _iter(self, items: list[object]) -> AsyncIterator[T]:
        for item in items:
            if item is BLOCK:
                await asyncio.Event().wait()
            else:
                yield item  # type: ignore[misc]

    async def close(self) -> None:
        self.closed = True
