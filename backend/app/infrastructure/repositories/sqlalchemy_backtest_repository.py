from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import EntityNotFoundError
from app.domain.strategy.entities import Backtest
from app.domain.strategy.repositories import BacktestRepository
from app.infrastructure.db.models import BacktestModel


def _to_domain(model: BacktestModel) -> Backtest:
    return Backtest(
        id=model.id,
        strategy_id=model.strategy_id,
        period_start=model.period_start,
        period_end=model.period_end,
        status=model.status,
        initial_balance=model.initial_balance,
        created_at=model.created_at,
        final_balance=model.final_balance,
        sharpe_ratio=model.sharpe_ratio,
        max_drawdown=model.max_drawdown,
        win_rate=model.win_rate,
        total_trades=model.total_trades,
        error_message=model.error_message,
        completed_at=model.completed_at,
        results=dict(model.results),
    )


class SqlAlchemyBacktestRepository(BacktestRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, backtest: Backtest) -> None:
        self._session.add(
            BacktestModel(
                id=backtest.id,
                strategy_id=backtest.strategy_id,
                period_start=backtest.period_start,
                period_end=backtest.period_end,
                status=backtest.status,
                initial_balance=backtest.initial_balance,
                final_balance=backtest.final_balance,
                sharpe_ratio=backtest.sharpe_ratio,
                max_drawdown=backtest.max_drawdown,
                win_rate=backtest.win_rate,
                total_trades=backtest.total_trades,
                error_message=backtest.error_message,
                results=backtest.results,
                created_at=backtest.created_at,
                completed_at=backtest.completed_at,
            )
        )
        await self._session.flush()

    async def get_by_id(self, backtest_id: uuid.UUID) -> Backtest | None:
        model = await self._session.get(BacktestModel, backtest_id)
        return _to_domain(model) if model else None

    async def list_for_strategy(self, strategy_id: uuid.UUID) -> list[Backtest]:
        stmt = (
            select(BacktestModel)
            .where(BacktestModel.strategy_id == strategy_id)
            .order_by(BacktestModel.created_at.desc())
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def update(self, backtest: Backtest) -> None:
        model = await self._session.get(BacktestModel, backtest.id)
        if model is None:
            raise EntityNotFoundError("Backtest", backtest.id)

        model.status = backtest.status
        model.final_balance = backtest.final_balance
        model.sharpe_ratio = backtest.sharpe_ratio
        model.max_drawdown = backtest.max_drawdown
        model.win_rate = backtest.win_rate
        model.total_trades = backtest.total_trades
        model.error_message = backtest.error_message
        model.results = backtest.results
        model.completed_at = backtest.completed_at
        await self._session.flush()
