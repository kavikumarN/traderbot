from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import EntityNotFoundError
from app.domain.strategy.entities import Signal
from app.domain.strategy.repositories import SignalRepository
from app.infrastructure.db.models import SignalModel


def _to_domain(model: SignalModel) -> Signal:
    return Signal(
        id=model.id,
        strategy_id=model.strategy_id,
        symbol=model.symbol,
        side=model.side,
        quantity=model.quantity,
        status=model.status,
        generated_at=model.generated_at,
        target_price=model.target_price,
        rejection_reason=model.rejection_reason,
        expires_at=model.expires_at,
    )


class SqlAlchemySignalRepository(SignalRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, signal: Signal) -> None:
        self._session.add(
            SignalModel(
                id=signal.id,
                strategy_id=signal.strategy_id,
                symbol=signal.symbol,
                side=signal.side,
                quantity=signal.quantity,
                target_price=signal.target_price,
                status=signal.status,
                generated_at=signal.generated_at,
                expires_at=signal.expires_at,
                rejection_reason=signal.rejection_reason,
            )
        )
        await self._session.flush()

    async def get_by_id(self, signal_id: uuid.UUID) -> Signal | None:
        model = await self._session.get(SignalModel, signal_id)
        return _to_domain(model) if model else None

    async def list_for_strategy(
        self, strategy_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Signal]:
        stmt = (
            select(SignalModel)
            .where(SignalModel.strategy_id == strategy_id)
            .order_by(SignalModel.generated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def update(self, signal: Signal) -> None:
        model = await self._session.get(SignalModel, signal.id)
        if model is None:
            raise EntityNotFoundError("Signal", signal.id)

        model.status = signal.status
        model.rejection_reason = signal.rejection_reason
        await self._session.flush()
