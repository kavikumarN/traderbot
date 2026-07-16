"""Execution Service: the trading engine's only point of contact with an
actual exchange.

Translates between this platform's own `Order` aggregate and the exchange's
vocabulary (`app.domain.exchange`), through whichever `ExchangeClient` the
caller passes in — Binance live, or the in-memory paper-trading simulator.
Callers (`TradingService`) never branch on trading mode; they just pass
through whichever adapter dependency injection handed them.

Deliberately stateless and persistence-free: no repository access, no
`UnitOfWork`. Every method takes the `Order` (and, where relevant, the
`ExchangeClient`) it acts on and returns the updated aggregate — deciding
*when* to call this and what to persist afterwards belongs to `OrderService`
and `TradingService`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.exchange.exceptions import InsufficientBalanceError as ExchangeInsufficientBalanceError
from app.domain.exchange.exceptions import OrderNotFoundError
from app.domain.exchange.exceptions import OrderRejectedError as ExchangeOrderRejectedError
from app.domain.exchange.models.account import ExchangeOrder
from app.domain.exchange.models.requests import PlaceOrderRequest
from app.domain.exchange.ports.exchange_client import ExchangeClient
from app.domain.trading.entities import Order, Trade
from app.domain.trading.enums import PlatformOrderStatus
from app.domain.trading.exceptions import InsufficientBalanceError, OrderRejectedError
from app.domain.trading.exchange_status import to_platform_status


class ExecutionService:
    async def submit_order(self, order: Order, exchange: ExchangeClient) -> Order:
        """Places `order` on the exchange for the first time. Raises the
        trading-domain equivalents of whatever the exchange rejected it
        with — the order itself is left untouched so the caller can decide
        how to record the rejection."""

        request = PlaceOrderRequest(
            symbol=order.symbol,
            side=order.side,
            type=order.type,
            quantity=order.quantity,
            price=order.price,
            stop_price=order.stop_price,
            time_in_force=order.time_in_force,
            client_order_id=order.client_order_id,
        )
        try:
            exchange_order = await exchange.place_order(request)
        except ExchangeInsufficientBalanceError as exc:
            raise InsufficientBalanceError(order.symbol) from exc
        except ExchangeOrderRejectedError as exc:
            raise OrderRejectedError(exc.message) from exc

        return _apply_exchange_order(order, exchange_order, submitted=True)

    async def cancel_order(self, order: Order, exchange: ExchangeClient) -> Order:
        try:
            exchange_order = await exchange.cancel_order(
                order.symbol,
                exchange_order_id=order.exchange_order_id,
                client_order_id=order.client_order_id if order.exchange_order_id is None else None,
            )
        except OrderNotFoundError as exc:
            raise OrderRejectedError(f"Exchange has no record of order {order.id}") from exc
        except ExchangeOrderRejectedError as exc:
            raise OrderRejectedError(exc.message) from exc

        return _apply_exchange_order(order, exchange_order)

    async def refresh_order(self, order: Order, exchange: ExchangeClient) -> Order:
        """Re-fetches the exchange's current view of a resting order —
        `TradingService.sync_order`'s way of driving limit/stop orders
        (which don't fill the instant they're placed) toward FILLED or
        CANCELLED without a live push feed."""

        try:
            exchange_order = await exchange.get_order(
                order.symbol,
                exchange_order_id=order.exchange_order_id,
                client_order_id=order.client_order_id if order.exchange_order_id is None else None,
            )
        except OrderNotFoundError as exc:
            raise OrderRejectedError(f"Exchange has no record of order {order.id}") from exc

        return _apply_exchange_order(order, exchange_order)

    def build_fill_trade(self, order: Order, previous_executed_quantity: Decimal) -> Trade | None:
        """Builds a `Trade` for the quantity newly filled since
        `previous_executed_quantity`, or `None` if nothing new filled.

        This platform only learns about fills through `ExchangeOrder`'s
        *cumulative* fields — no per-fill trade id is available without
        ingesting Binance's own trade-level execution-report stream (a
        future enhancement). So `exchange_order_id` doubles here as an
        idempotent, per-account-unique `exchange_trade_id`: today, every
        order fills in at most one step (the paper simulator never
        partially fills; a real exchange partial-fill sequence would need
        that future trade-stream ingestion to get true per-fill records).
        """
        delta_quantity = order.executed_quantity - previous_executed_quantity
        if delta_quantity <= 0 or order.exchange_order_id is None:
            return None

        avg_price = (
            order.cumulative_quote_quantity / order.executed_quantity
            if order.executed_quantity
            else Decimal(0)
        )
        delta_quote = avg_price * delta_quantity

        return Trade(
            id=uuid.uuid4(),
            order_id=order.id,
            exchange_account_id=order.exchange_account_id,
            symbol=order.symbol,
            side=order.side,
            price=avg_price,
            quantity=delta_quantity,
            quote_quantity=delta_quote,
            commission=Decimal(0),
            exchange_trade_id=order.exchange_order_id,
            executed_at=order.filled_at or datetime.now(UTC),
        )


def _apply_exchange_order(order: Order, exchange_order: ExchangeOrder, *, submitted: bool = False) -> Order:
    now = datetime.now(UTC)
    status = to_platform_status(exchange_order.status)

    order.status = status
    order.executed_quantity = exchange_order.executed_quantity
    order.cumulative_quote_quantity = exchange_order.cumulative_quote_quantity
    order.exchange_order_id = exchange_order.exchange_order_id
    order.updated_at = now
    if submitted and order.submitted_at is None:
        order.submitted_at = now
    if status == PlatformOrderStatus.FILLED and order.filled_at is None:
        order.filled_at = now
    return order
