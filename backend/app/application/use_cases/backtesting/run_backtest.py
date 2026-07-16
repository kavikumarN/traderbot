"""Runs a backtest: resolves the strategy's own persisted config
(`{"strategy_type", "parameters"}`) into an initialized `StrategyPlugin`
via `StrategyLoader`, sources the requested candle range (the persisted
`candles` store first, falling back to a paginated live-REST fetch through
`IMarketDataReader` on a miss — see the module-level note below), replays
it through `BacktestEngine`, and persists the result as a `COMPLETED`
`Backtest` row.

Runs entirely inline inside the request — there's no scheduler/job-queue
infrastructure in this codebase to run it any other way, and the
simulation is deterministic pure math, so nothing about it should fail
mid-run once the inputs (a valid strategy, a non-empty candle range) are
validated up front. `BacktestStatus.PENDING/RUNNING/FAILED` stay valid
enum values but aren't reachable from this synchronous flow.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.application.services.backtest_engine import BacktestEngine
from app.application.services.strategy_loader import StrategyLoader
from app.domain.backtesting.analytics import MAX_BACKTEST_CANDLES, PERIODS_PER_YEAR, BacktestResult
from app.domain.exceptions import EntityNotFoundError, ValidationError
from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.market_data import Candle
from app.domain.exchange.ports.market_data_reader import IMarketDataReader
from app.domain.marketdata.entities import PersistedCandle
from app.domain.strategy.entities import Backtest, Strategy
from app.domain.strategy.enums import BacktestStatus

_BACKFILL_PAGE_SIZE = 1000


@dataclass(frozen=True, slots=True)
class RunBacktestCommand:
    user_id: uuid.UUID
    strategy_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    interval: KlineInterval
    initial_balance: Decimal
    commission_rate: Decimal
    slippage_bps: Decimal = Decimal(0)


class RunBacktestUseCase:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        market_data: IMarketDataReader,
        *,
        engine: BacktestEngine | None = None,
        strategy_loader: StrategyLoader | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._market_data = market_data
        self._engine = engine or BacktestEngine()
        self._strategy_loader = strategy_loader or StrategyLoader()

    async def execute(self, command: RunBacktestCommand) -> Backtest:
        if command.period_end <= command.period_start:
            raise ValidationError("period_end must be after period_start")

        async with self._uow_factory() as uow:
            strategy = await self._owned_strategy(uow, command.user_id, command.strategy_id)
            candles = await self._resolve_candles(
                uow, strategy.symbol, command.interval, command.period_start, command.period_end
            )
            if not candles:
                raise ValidationError(
                    f"No candles available for {strategy.symbol} {command.interval.value} "
                    f"between {command.period_start.isoformat()} and {command.period_end.isoformat()}"
                )

            plugin = await self._strategy_loader.load(strategy)
            result = await self._engine.run(
                plugin,
                [_to_domain_candle(candle) for candle in candles],
                initial_balance=command.initial_balance,
                commission_rate=command.commission_rate,
                periods_per_year=PERIODS_PER_YEAR[command.interval],
                slippage_bps=command.slippage_bps,
            )

            now = datetime.now(UTC)
            backtest = Backtest(
                id=uuid.uuid4(),
                strategy_id=strategy.id,
                period_start=command.period_start,
                period_end=command.period_end,
                status=BacktestStatus.COMPLETED,
                initial_balance=command.initial_balance,
                final_balance=result.final_balance,
                sharpe_ratio=result.sharpe_ratio,
                max_drawdown=result.max_drawdown_pct,
                win_rate=result.win_rate,
                total_trades=result.total_trades,
                created_at=now,
                completed_at=now,
                results=_result_to_dict(strategy.symbol, command.interval, result),
            )
            await uow.backtests.add(backtest)
            await uow.commit()
            return backtest

    async def _owned_strategy(self, uow: UnitOfWork, user_id: uuid.UUID, strategy_id: uuid.UUID) -> Strategy:
        strategy = await uow.strategies.get_by_id(strategy_id)
        if strategy is None or strategy.user_id != user_id:
            raise EntityNotFoundError("Strategy", strategy_id)
        return strategy

    async def _resolve_candles(
        self, uow: UnitOfWork, symbol: str, interval: KlineInterval, start: datetime, end: datetime
    ) -> list[PersistedCandle]:
        persisted = await uow.candles.list_range(symbol, interval, start=start, end=end)
        if persisted:
            return persisted[:MAX_BACKTEST_CANDLES]

        fetched = await self._backfill_candles(symbol, interval, start, end)
        if fetched:
            await uow.candles.upsert_many(fetched)
        return fetched

    async def _backfill_candles(
        self, symbol: str, interval: KlineInterval, start: datetime, end: datetime
    ) -> list[PersistedCandle]:
        """The persisted store only ever holds what the live WebSocket
        ingestion happened to capture — on a fresh install (or any range
        predating that) it's empty. `IMarketDataReader.get_candles` reaches
        the exchange's real REST history directly, but caps each call at
        `_BACKFILL_PAGE_SIZE`, so a longer range needs paging through by
        advancing the window to the last candle fetched."""

        collected: list[PersistedCandle] = []
        cursor = start
        while cursor < end and len(collected) < MAX_BACKTEST_CANDLES:
            batch = await self._market_data.get_candles(
                symbol, interval, limit=_BACKFILL_PAGE_SIZE, start_time=cursor, end_time=end
            )
            if not batch:
                break
            collected.extend(_to_persisted_candle(candle) for candle in batch)
            next_cursor = batch[-1].close_time
            if next_cursor <= cursor:
                break
            cursor = next_cursor
            if len(batch) < _BACKFILL_PAGE_SIZE:
                break
        return collected[:MAX_BACKTEST_CANDLES]


def _to_domain_candle(candle: PersistedCandle) -> Candle:
    return Candle(
        symbol=candle.symbol,
        interval=candle.interval,
        open_time=candle.open_time,
        close_time=candle.close_time,
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        volume=candle.volume,
        quote_volume=candle.quote_volume,
        trade_count=candle.trade_count,
        is_closed=True,
    )


def _to_persisted_candle(candle: Candle) -> PersistedCandle:
    return PersistedCandle(
        symbol=candle.symbol,
        interval=candle.interval,
        open_time=candle.open_time,
        close_time=candle.close_time,
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        volume=candle.volume,
        quote_volume=candle.quote_volume,
        trade_count=candle.trade_count,
    )


def _result_to_dict(symbol: str, interval: KlineInterval, result: BacktestResult) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "interval": interval.value,
        "metrics": {
            "sortino_ratio": str(result.sortino_ratio) if result.sortino_ratio is not None else None,
            "calmar_ratio": str(result.calmar_ratio) if result.calmar_ratio is not None else None,
            "cagr_pct": str(result.cagr_pct) if result.cagr_pct is not None else None,
            "avg_drawdown_pct": str(result.avg_drawdown_pct),
            "profit_factor": str(result.profit_factor) if result.profit_factor is not None else None,
            "expectancy": str(result.trade_stats.expectancy),
            "avg_win": str(result.trade_stats.avg_win),
            "avg_loss": str(result.trade_stats.avg_loss),
            "largest_win": str(result.trade_stats.largest_win),
            "largest_loss": str(result.trade_stats.largest_loss),
            "max_consecutive_wins": result.trade_stats.max_consecutive_wins,
            "max_consecutive_losses": result.trade_stats.max_consecutive_losses,
            "exposure_pct": str(result.exposure_pct),
        },
        "trade_log": [
            {
                "executed_at": fill.executed_at.isoformat(),
                "side": fill.side.value,
                "price": str(fill.price),
                "quantity": str(fill.quantity),
                "commission": str(fill.commission),
                "realized_pnl": str(fill.realized_pnl),
                "cash_after": str(fill.cash_after),
                "position_after": str(fill.position_after),
                "reason": fill.reason,
            }
            for fill in result.fills
        ],
        "equity_curve": [
            {"time": point.time.isoformat(), "equity": str(point.equity)} for point in result.equity_curve
        ],
    }
