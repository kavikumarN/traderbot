from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.marketdata.entities import MarketTick
from app.domain.marketdata.repositories import MarketTickRepository
from app.infrastructure.db.models import MarketTickModel


def _to_domain(model: MarketTickModel) -> MarketTick:
    return MarketTick(
        symbol=model.symbol,
        trade_id=model.trade_id,
        price=model.price,
        quantity=model.quantity,
        quote_quantity=model.quote_quantity,
        traded_at=model.traded_at,
        is_buyer_maker=model.is_buyer_maker,
    )


def _to_model(tick: MarketTick) -> MarketTickModel:
    return MarketTickModel(
        symbol=tick.symbol,
        traded_at=tick.traded_at,
        trade_id=tick.trade_id,
        price=tick.price,
        quantity=tick.quantity,
        quote_quantity=tick.quote_quantity,
        is_buyer_maker=tick.is_buyer_maker,
    )


class SqlAlchemyMarketTickRepository(MarketTickRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, tick: MarketTick) -> None:
        self._session.add(_to_model(tick))
        await self._session.flush()

    async def add_many(self, ticks: list[MarketTick]) -> None:
        if not ticks:
            return
        self._session.add_all(_to_model(tick) for tick in ticks)
        await self._session.flush()

    async def list_range(
        self, symbol: str, *, start: datetime, end: datetime, limit: int = 1000
    ) -> list[MarketTick]:
        stmt = (
            select(MarketTickModel)
            .where(
                MarketTickModel.symbol == symbol,
                MarketTickModel.traded_at >= start,
                MarketTickModel.traded_at <= end,
            )
            .order_by(MarketTickModel.traded_at)
            .limit(limit)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]
