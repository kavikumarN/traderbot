from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import EntityNotFoundError
from app.domain.strategy.entities import Strategy
from app.domain.strategy.enums import StrategyStatus
from app.domain.strategy.repositories import StrategyRepository
from app.infrastructure.db.models import StrategyModel

_ACTIVE_STATUSES = (StrategyStatus.LIVE, StrategyStatus.PAPER_TRADING)


def _to_domain(model: StrategyModel) -> Strategy:
    return Strategy(
        id=model.id,
        user_id=model.user_id,
        name=model.name,
        description=model.description,
        symbol=model.symbol,
        status=model.status,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
        config=dict(model.config),
    )


class SqlAlchemyStrategyRepository(StrategyRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, strategy: Strategy) -> None:
        self._session.add(
            StrategyModel(
                id=strategy.id,
                user_id=strategy.user_id,
                name=strategy.name,
                description=strategy.description,
                symbol=strategy.symbol,
                status=strategy.status,
                version=strategy.version,
                config=strategy.config,
                created_at=strategy.created_at,
                updated_at=strategy.updated_at,
            )
        )
        await self._session.flush()

    async def get_by_id(self, strategy_id: uuid.UUID) -> Strategy | None:
        model = await self._session.get(StrategyModel, strategy_id)
        return _to_domain(model) if model else None

    async def list_for_user(self, user_id: uuid.UUID) -> list[Strategy]:
        stmt = (
            select(StrategyModel)
            .where(StrategyModel.user_id == user_id)
            .order_by(StrategyModel.created_at.desc())
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def list_active(self) -> list[Strategy]:
        stmt = select(StrategyModel).where(StrategyModel.status.in_(_ACTIVE_STATUSES))
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def update(self, strategy: Strategy) -> None:
        model = await self._session.get(StrategyModel, strategy.id)
        if model is None:
            raise EntityNotFoundError("Strategy", strategy.id)

        model.name = strategy.name
        model.description = strategy.description
        model.status = strategy.status
        model.version = strategy.version
        model.config = strategy.config
        model.updated_at = strategy.updated_at
        await self._session.flush()
