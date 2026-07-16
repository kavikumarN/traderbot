from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import EntityNotFoundError
from app.domain.trading.entities import Order
from app.domain.trading.enums import PlatformOrderStatus
from app.domain.trading.repositories import OrderRepository
from app.infrastructure.db.models import OrderModel

# Mirrors `app.domain.trading.entities._TERMINAL_ORDER_STATUSES` — kept
# separate because that name is private to the domain module. An order in
# any other status still needs the risk/execution pipeline to act on it.
_TERMINAL_STATUSES = (
    PlatformOrderStatus.FILLED,
    PlatformOrderStatus.REJECTED,
    PlatformOrderStatus.CANCELLED,
    PlatformOrderStatus.EXPIRED,
    PlatformOrderStatus.SETTLED,
)


def _to_domain(model: OrderModel) -> Order:
    return Order(
        id=model.id,
        exchange_account_id=model.exchange_account_id,
        symbol=model.symbol,
        side=model.side,
        type=model.type,
        status=model.status,
        quantity=model.quantity,
        executed_quantity=model.executed_quantity,
        cumulative_quote_quantity=model.cumulative_quote_quantity,
        client_order_id=model.client_order_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        strategy_id=model.strategy_id,
        signal_id=model.signal_id,
        price=model.price,
        stop_price=model.stop_price,
        time_in_force=model.time_in_force,
        exchange_order_id=model.exchange_order_id,
        rejection_reason=model.rejection_reason,
        submitted_at=model.submitted_at,
        filled_at=model.filled_at,
    )


class SqlAlchemyOrderRepository(OrderRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, order: Order) -> None:
        self._session.add(
            OrderModel(
                id=order.id,
                exchange_account_id=order.exchange_account_id,
                strategy_id=order.strategy_id,
                signal_id=order.signal_id,
                symbol=order.symbol,
                side=order.side,
                type=order.type,
                status=order.status,
                quantity=order.quantity,
                executed_quantity=order.executed_quantity,
                cumulative_quote_quantity=order.cumulative_quote_quantity,
                price=order.price,
                stop_price=order.stop_price,
                time_in_force=order.time_in_force,
                client_order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
                rejection_reason=order.rejection_reason,
                created_at=order.created_at,
                updated_at=order.updated_at,
                submitted_at=order.submitted_at,
                filled_at=order.filled_at,
            )
        )
        await self._session.flush()

    async def get_by_id(self, order_id: uuid.UUID) -> Order | None:
        model = await self._session.get(OrderModel, order_id)
        return _to_domain(model) if model else None

    async def get_by_client_order_id(self, client_order_id: str) -> Order | None:
        stmt = select(OrderModel).where(OrderModel.client_order_id == client_order_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(model) if model else None

    async def list_open_for_account(self, exchange_account_id: uuid.UUID) -> list[Order]:
        stmt = (
            select(OrderModel)
            .where(
                OrderModel.exchange_account_id == exchange_account_id,
                OrderModel.status.not_in(_TERMINAL_STATUSES),
            )
            .order_by(OrderModel.created_at.desc())
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def list_for_strategy(self, strategy_id: uuid.UUID) -> list[Order]:
        stmt = (
            select(OrderModel)
            .where(OrderModel.strategy_id == strategy_id)
            .order_by(OrderModel.created_at.desc())
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def list_for_account(
        self, exchange_account_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Order]:
        stmt = (
            select(OrderModel)
            .where(OrderModel.exchange_account_id == exchange_account_id)
            .order_by(OrderModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def update(self, order: Order) -> None:
        model = await self._session.get(OrderModel, order.id)
        if model is None:
            raise EntityNotFoundError("Order", order.id)

        model.status = order.status
        model.executed_quantity = order.executed_quantity
        model.cumulative_quote_quantity = order.cumulative_quote_quantity
        model.exchange_order_id = order.exchange_order_id
        model.rejection_reason = order.rejection_reason
        model.updated_at = order.updated_at
        model.submitted_at = order.submitted_at
        model.filled_at = order.filled_at
        await self._session.flush()
