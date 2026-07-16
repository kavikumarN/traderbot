"""Strategy Engine: the runtime that actually executes plugins.

For every active (`LIVE`/`PAPER_TRADING`) `Strategy`, loads its plugin via
`StrategyLoader`, then drives `on_tick`/`on_candle`/`generate_signal()` from
polled market data, forwarding any resulting proposal to `SignalManager`.

Polling rather than a live push feed is a deliberate simplification, in the
same spirit as `PaperTradingExchangeAdapter`'s own documented trade-offs:
every strategy already talks to the market exclusively through
`ExchangeClient` (the same port `TradingService` places orders through), so
polling that one port on an interval works identically in paper and live
trading mode and needs no new integration with the Phase 5 WebSocket
ingestion pipeline. A push-based version could replace `_poll_once` later
without changing `StrategyPlugin`, `StrategyLoader`, or `SignalManager` at
all.

One `asyncio.Task` per running strategy, matching `MarketDataService`'s own
resilience pattern: a bug or a bad tick in one strategy can't take any
other strategy down, and a crash during one poll just gets logged — the
strategy keeps running on the next interval instead of silently dying.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.services.signal_manager import SignalManager
from app.application.services.strategy_loader import StrategyLoader
from app.core.logging import get_logger
from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.ports.exchange_client import ExchangeClient
from app.domain.strategy.entities import Strategy
from app.domain.strategy.plugin import StrategyPlugin

logger = get_logger(__name__)

DEFAULT_POLL_INTERVAL_SECONDS = 5.0


class StrategyEngine:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        exchange: ExchangeClient,
        strategy_loader: StrategyLoader,
        signal_manager: SignalManager,
        *,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        candle_interval: KlineInterval = KlineInterval.ONE_MINUTE,
    ) -> None:
        self._uow_factory = uow_factory
        self._exchange = exchange
        self._loader = strategy_loader
        self._signals = signal_manager
        self._poll_interval = poll_interval_seconds
        self._candle_interval = candle_interval
        self._tasks: dict[uuid.UUID, asyncio.Task[None]] = {}

    @property
    def running_strategy_ids(self) -> list[uuid.UUID]:
        return list(self._tasks)

    async def start(self) -> None:
        if self._tasks:
            raise RuntimeError("StrategyEngine is already running")
        async with self._uow_factory() as uow:
            strategies = await uow.strategies.list_active()
        for strategy in strategies:
            await self.start_strategy(strategy)
        logger.info("StrategyEngine started: %d active strategies", len(self._tasks))

    async def stop(self) -> None:
        for strategy_id in list(self._tasks):
            await self.stop_strategy(strategy_id)
        logger.info("StrategyEngine stopped")

    async def start_strategy(self, strategy: Strategy) -> None:
        if strategy.id in self._tasks:
            return
        self._tasks[strategy.id] = asyncio.create_task(
            self._run_strategy(strategy), name=f"strategy:{strategy.id}"
        )

    async def stop_strategy(self, strategy_id: uuid.UUID) -> None:
        task = self._tasks.pop(strategy_id, None)
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("StrategyEngine[%s]: task raised during shutdown", strategy_id)

    async def _run_strategy(self, strategy: Strategy) -> None:
        try:
            plugin = await self._loader.load(strategy)
        except Exception:
            logger.exception("StrategyEngine[%s]: failed to load plugin, not running", strategy.id)
            return

        last_candle_close_time: datetime | None = None
        try:
            while True:
                try:
                    last_candle_close_time = await self._poll_once(strategy, plugin, last_candle_close_time)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("StrategyEngine[%s]: error during poll, continuing", strategy.id)
                await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            pass
        finally:
            try:
                await plugin.shutdown()
            except Exception:
                logger.exception("StrategyEngine[%s]: error during plugin shutdown", strategy.id)

    async def _poll_once(
        self, strategy: Strategy, plugin: StrategyPlugin, last_candle_close_time: datetime | None
    ) -> datetime | None:
        ticker = await self._exchange.get_ticker(strategy.symbol)
        await plugin.on_tick(ticker)
        await self._maybe_emit(strategy, plugin)

        # `limit=2` is enough to always see the most recently *closed*
        # candle even if the REST endpoint's very last entry is still
        # forming — `close_time` in the future is the reliable signal that
        # a candle isn't done yet, independent of whatever a given
        # exchange adapter's mapper does with `Candle.is_closed`.
        now = datetime.now(UTC)
        candles = await self._exchange.get_candles(strategy.symbol, self._candle_interval, limit=2)
        for candle in candles:
            if candle.close_time > now:
                continue
            if last_candle_close_time is not None and candle.close_time <= last_candle_close_time:
                continue
            await plugin.on_candle(candle)
            last_candle_close_time = candle.close_time
            await self._maybe_emit(strategy, plugin)

        return last_candle_close_time

    async def _maybe_emit(self, strategy: Strategy, plugin: StrategyPlugin) -> None:
        proposal = plugin.generate_signal()
        if proposal is None:
            return
        await self._signals.submit(strategy, proposal, exchange=self._exchange)
