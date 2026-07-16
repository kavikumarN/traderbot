from __future__ import annotations

from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exchange.models.market_data import OrderBookLevel, OrderBookSnapshot
from app.domain.marketdata.repositories import OrderBookRepository
from app.infrastructure.db.models import OrderBookSnapshotModel


def _levels_to_json(levels: tuple[OrderBookLevel, ...]) -> list[dict[str, str]]:
    return [{"price": str(level.price), "quantity": str(level.quantity)} for level in levels]


def _json_to_levels(raw: list[dict[str, str]]) -> tuple[OrderBookLevel, ...]:
    return tuple(OrderBookLevel(price=Decimal(item["price"]), quantity=Decimal(item["quantity"])) for item in raw)


def _to_domain(model: OrderBookSnapshotModel) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        symbol=model.symbol,
        last_update_id=model.last_update_id,
        bids=_json_to_levels(model.bids),
        asks=_json_to_levels(model.asks),
        retrieved_at=model.retrieved_at,
    )


class SqlAlchemyOrderBookRepository(OrderBookRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, snapshot: OrderBookSnapshot) -> None:
        stmt = insert(OrderBookSnapshotModel).values(
            symbol=snapshot.symbol,
            last_update_id=snapshot.last_update_id,
            bids=_levels_to_json(snapshot.bids),
            asks=_levels_to_json(snapshot.asks),
            retrieved_at=snapshot.retrieved_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[OrderBookSnapshotModel.symbol],
            set_={
                "last_update_id": stmt.excluded.last_update_id,
                "bids": stmt.excluded.bids,
                "asks": stmt.excluded.asks,
                "retrieved_at": stmt.excluded.retrieved_at,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_latest(self, symbol: str) -> OrderBookSnapshot | None:
        model = await self._session.get(OrderBookSnapshotModel, symbol)
        return _to_domain(model) if model else None
