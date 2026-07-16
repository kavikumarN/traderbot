from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.trading.entities import Position
from app.domain.trading.repositories import PositionRepository
from app.infrastructure.db.models import PositionModel


def _to_domain(model: PositionModel) -> Position:
    return Position(
        id=model.id,
        exchange_account_id=model.exchange_account_id,
        symbol=model.symbol,
        quantity=model.quantity,
        avg_entry_price=model.avg_entry_price,
        realized_pnl=model.realized_pnl,
        opened_at=model.opened_at,
        updated_at=model.updated_at,
        closed_at=model.closed_at,
    )


class SqlAlchemyPositionRepository(PositionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, position: Position) -> None:
        stmt = insert(PositionModel).values(
            id=position.id,
            exchange_account_id=position.exchange_account_id,
            symbol=position.symbol,
            quantity=position.quantity,
            avg_entry_price=position.avg_entry_price,
            realized_pnl=position.realized_pnl,
            opened_at=position.opened_at,
            updated_at=position.updated_at,
            closed_at=position.closed_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[PositionModel.exchange_account_id, PositionModel.symbol],
            set_={
                "quantity": position.quantity,
                "avg_entry_price": position.avg_entry_price,
                "realized_pnl": position.realized_pnl,
                "updated_at": position.updated_at,
                "closed_at": position.closed_at,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get(self, exchange_account_id: uuid.UUID, symbol: str) -> Position | None:
        stmt = select(PositionModel).where(
            PositionModel.exchange_account_id == exchange_account_id, PositionModel.symbol == symbol
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(model) if model else None

    async def list_open_for_account(self, exchange_account_id: uuid.UUID) -> list[Position]:
        stmt = select(PositionModel).where(
            PositionModel.exchange_account_id == exchange_account_id, PositionModel.closed_at.is_(None)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def list_for_account(self, exchange_account_id: uuid.UUID) -> list[Position]:
        stmt = select(PositionModel).where(PositionModel.exchange_account_id == exchange_account_id)
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]
