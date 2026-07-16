"""Order Service: this platform's own order lifecycle, independent of any
exchange.

Owns building the `Order` aggregate and the read paths behind order
tracking/history/status, plus the one domain guard (`ensure_cancelable`)
that doesn't require talking to an exchange first. No exchange I/O (see
`ExecutionService`) and no transaction management — every method takes an
already-open `UnitOfWork`, so the caller (`TradingService`) controls the
commit boundary.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.exceptions import EntityNotFoundError
from app.domain.exchange.enums import OrderSide, OrderType, TimeInForce
from app.domain.trading.entities import Order
from app.domain.trading.enums import PlatformOrderStatus
from app.domain.trading.exceptions import OrderNotCancelableError

# Binance accepts client order ids up to 36 characters; "tb-" plus a 32-hex
# uuid4 leaves comfortable room while staying obviously platform-generated.
_CLIENT_ORDER_ID_PREFIX = "tb-"


class OrderService:
    def build_order(
        self,
        *,
        exchange_account_id: uuid.UUID,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal | None = None,
        stop_price: Decimal | None = None,
        time_in_force: TimeInForce | None = None,
        strategy_id: uuid.UUID | None = None,
        signal_id: uuid.UUID | None = None,
        client_order_id: str | None = None,
    ) -> Order:
        now = datetime.now(UTC)
        return Order(
            id=uuid.uuid4(),
            exchange_account_id=exchange_account_id,
            symbol=symbol.upper(),
            side=side,
            type=order_type,
            status=PlatformOrderStatus.PENDING_RISK,
            quantity=quantity,
            executed_quantity=Decimal(0),
            cumulative_quote_quantity=Decimal(0),
            client_order_id=client_order_id or f"{_CLIENT_ORDER_ID_PREFIX}{uuid.uuid4().hex}",
            created_at=now,
            updated_at=now,
            strategy_id=strategy_id,
            signal_id=signal_id,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
        )

    async def get_order(self, uow: UnitOfWork, order_id: uuid.UUID) -> Order:
        order = await uow.orders.get_by_id(order_id)
        if order is None:
            raise EntityNotFoundError("Order", order_id)
        return order

    async def list_open_orders(self, uow: UnitOfWork, exchange_account_id: uuid.UUID) -> list[Order]:
        return await uow.orders.list_open_for_account(exchange_account_id)

    async def list_order_history(
        self, uow: UnitOfWork, exchange_account_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Order]:
        return await uow.orders.list_for_account(exchange_account_id, limit=limit, offset=offset)

    def ensure_cancelable(self, order: Order) -> None:
        if order.is_terminal:
            raise OrderNotCancelableError(order.id, order.status.value)
