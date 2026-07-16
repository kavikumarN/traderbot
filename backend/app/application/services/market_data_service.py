"""Market data engine orchestrator.

For each configured symbol this opens independent, concurrently-running
subscriptions against `IMarketDataStream` — ticker, order book, one per
configured candle interval, and trades — persists every event through
`MarketDataRepository`, and broadcasts it to WebSocket clients through a
`MarketDataBroadcaster`. Each subscription runs as its own `asyncio.Task`
so one symbol's stream erroring out can't take any other stream down.

Two layers of resilience, matching where each kind of failure actually
happens:

* Per-message: `_run` catches and logs exceptions from the handler (a bad
  DB write, a parsing bug) around a *single* message and keeps consuming —
  one bad tick shouldn't kill an otherwise-healthy stream.
* Transport: already handled below us. `IMarketDataStream`
  (`BinanceMarketDataStream` in production) reconnects with backoff
  forever on connection drops, so `_run`'s outer loop only ever exits via
  `stop()` or a genuine bug in the stream implementation itself.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from functools import partial
from typing import Any, TypeVar

from app.application.ports.broadcaster import MarketDataBroadcaster
from app.application.ports.market_data_repository import MarketDataRepository
from app.core.logging import get_logger
from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.market_data import Candle, OrderBookSnapshot, Ticker, Trade
from app.domain.exchange.ports.market_data_stream import IMarketDataStream

logger = get_logger(__name__)

T = TypeVar("T")


class MarketDataService:
    def __init__(
        self,
        stream: IMarketDataStream,
        repository: MarketDataRepository,
        broadcaster: MarketDataBroadcaster,
        *,
        symbols: list[str],
        candle_intervals: list[KlineInterval],
        order_book_persist_interval_seconds: float = 1.0,
    ) -> None:
        self._stream = stream
        self._repository = repository
        self._broadcaster = broadcaster
        self._symbols = [symbol.upper() for symbol in symbols]
        self._candle_intervals = list(candle_intervals)
        self._order_book_persist_interval = order_book_persist_interval_seconds
        self._tasks: list[asyncio.Task[None]] = []

    @property
    def running(self) -> bool:
        return len(self._tasks) > 0

    async def start(self) -> None:
        if self._tasks:
            raise RuntimeError("MarketDataService is already running")

        for symbol in self._symbols:
            self._spawn(f"trades:{symbol}", self._stream.subscribe_trades(symbol), partial(self._handle_trade, symbol))
            self._spawn(f"ticker:{symbol}", self._stream.subscribe_ticker(symbol), partial(self._handle_ticker, symbol))
            self._spawn(
                f"orderbook:{symbol}",
                self._stream.subscribe_order_book(symbol),
                self._make_order_book_handler(symbol),
            )
            for interval in self._candle_intervals:
                self._spawn(
                    f"candles:{symbol}:{interval.value}",
                    self._stream.subscribe_candles(symbol, interval),
                    partial(self._handle_candle, symbol),
                )

        logger.info(
            "MarketDataService started: %d streams across %d symbols", len(self._tasks), len(self._symbols)
        )

    async def stop(self) -> None:
        if not self._tasks:
            return

        await self._stream.close()
        for task in self._tasks:
            task.cancel()

        results = await asyncio.gather(*self._tasks, return_exceptions=True)
        for task, result in zip(self._tasks, results, strict=True):
            if isinstance(result, Exception):
                logger.error("MarketDataService task %s failed during shutdown", task.get_name(), exc_info=result)

        self._tasks.clear()
        logger.info("MarketDataService stopped")

    def _spawn(self, name: str, aiter: AsyncIterator[T], handle: Callable[[T], Awaitable[None]]) -> None:
        self._tasks.append(asyncio.create_task(self._run(name, aiter, handle), name=f"marketdata:{name}"))

    async def _run(self, name: str, aiter: AsyncIterator[T], handle: Callable[[T], Awaitable[None]]) -> None:
        try:
            async for item in aiter:
                try:
                    await handle(item)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("MarketDataService[%s]: error handling message", name)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("MarketDataService[%s]: stream terminated unexpectedly", name)

    # --- per-channel handlers -----------------------------------------------------------------

    async def _handle_trade(self, symbol: str, trade: Trade) -> None:
        await self._repository.save_trade(trade)
        await self._broadcaster.broadcast(symbol, _envelope(symbol, "trade", _trade_payload(trade)))

    async def _handle_ticker(self, symbol: str, ticker: Ticker) -> None:
        await self._repository.save_volume_stats(ticker)
        await self._broadcaster.broadcast(symbol, _envelope(symbol, "ticker", _ticker_payload(ticker)))

    async def _handle_candle(self, symbol: str, candle: Candle) -> None:
        await self._repository.save_candle(candle)
        await self._broadcaster.broadcast(symbol, _envelope(symbol, "candle", _candle_payload(candle)))

    def _make_order_book_handler(self, symbol: str) -> Callable[[OrderBookSnapshot], Awaitable[None]]:
        # Order-book snapshots arrive ~10/sec; every one is broadcast (a
        # live-updating depth chart needs that), but persistence is
        # throttled — see `Settings.market_data_order_book_persist_interval_seconds`.
        last_persisted_at = 0.0

        async def handle(snapshot: OrderBookSnapshot) -> None:
            nonlocal last_persisted_at
            await self._broadcaster.broadcast(symbol, _envelope(symbol, "orderbook", _order_book_payload(snapshot)))
            now = time.monotonic()
            if now - last_persisted_at >= self._order_book_persist_interval:
                last_persisted_at = now
                await self._repository.save_order_book(snapshot)

        return handle


def _envelope(symbol: str, channel: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"channel": channel, "symbol": symbol, "data": data}


def _candle_payload(candle: Candle) -> dict[str, Any]:
    return {
        "interval": candle.interval.value,
        "open_time": candle.open_time.isoformat(),
        "close_time": candle.close_time.isoformat(),
        "open": str(candle.open),
        "high": str(candle.high),
        "low": str(candle.low),
        "close": str(candle.close),
        "volume": str(candle.volume),
        "quote_volume": str(candle.quote_volume),
        "trade_count": candle.trade_count,
        "is_closed": candle.is_closed,
    }


def _trade_payload(trade: Trade) -> dict[str, Any]:
    return {
        "trade_id": trade.trade_id,
        "price": str(trade.price),
        "quantity": str(trade.quantity),
        "quote_quantity": str(trade.quote_quantity),
        "traded_at": trade.traded_at.isoformat(),
        "is_buyer_maker": trade.is_buyer_maker,
    }


def _order_book_payload(snapshot: OrderBookSnapshot) -> dict[str, Any]:
    return {
        "last_update_id": snapshot.last_update_id,
        "bids": [{"price": str(level.price), "quantity": str(level.quantity)} for level in snapshot.bids],
        "asks": [{"price": str(level.price), "quantity": str(level.quantity)} for level in snapshot.asks],
        "retrieved_at": snapshot.retrieved_at.isoformat(),
    }


def _ticker_payload(ticker: Ticker) -> dict[str, Any]:
    return {
        "last_price": str(ticker.last_price),
        "bid_price": str(ticker.bid_price),
        "ask_price": str(ticker.ask_price),
        "high_price": str(ticker.high_price),
        "low_price": str(ticker.low_price),
        "volume": str(ticker.volume),
        "quote_volume": str(ticker.quote_volume),
        "price_change_percent": str(ticker.price_change_percent),
        "open_time": ticker.open_time.isoformat(),
        "close_time": ticker.close_time.isoformat(),
    }
