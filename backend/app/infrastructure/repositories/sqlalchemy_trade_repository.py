from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.trading.entities import Trade
from app.domain.trading.repositories import TradeRepository
from app.infrastructure.db.models import TradeModel


def _to_domain(model: TradeModel) -> Trade:
    return Trade(
        id=model.id,
        order_id=model.order_id,
        exchange_account_id=model.exchange_account_id,
        symbol=model.symbol,
        side=model.side,
        price=model.price,
        quantity=model.quantity,
        quote_quantity=model.quote_quantity,
        commission=model.commission,
        exchange_trade_id=model.exchange_trade_id,
        executed_at=model.executed_at,
        commission_asset=model.commission_asset,
    )


class SqlAlchemyTradeRepository(TradeRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, trade: Trade) -> None:
        self._session.add(
            TradeModel(
                id=trade.id,
                order_id=trade.order_id,
                exchange_account_id=trade.exchange_account_id,
                symbol=trade.symbol,
                side=trade.side,
                price=trade.price,
                quantity=trade.quantity,
                quote_quantity=trade.quote_quantity,
                commission=trade.commission,
                commission_asset=trade.commission_asset,
                exchange_trade_id=trade.exchange_trade_id,
                executed_at=trade.executed_at,
            )
        )
        await self._session.flush()

    async def list_for_order(self, order_id: uuid.UUID) -> list[Trade]:
        stmt = select(TradeModel).where(TradeModel.order_id == order_id).order_by(TradeModel.executed_at)
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def list_for_account(
        self, exchange_account_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Trade]:
        stmt = (
            select(TradeModel)
            .where(TradeModel.exchange_account_id == exchange_account_id)
            .order_by(TradeModel.executed_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def list_all_for_account(self, exchange_account_id: uuid.UUID) -> list[Trade]:
        stmt = (
            select(TradeModel)
            .where(TradeModel.exchange_account_id == exchange_account_id)
            .order_by(TradeModel.executed_at.asc())
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]
