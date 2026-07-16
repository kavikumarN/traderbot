"""Trading domain entity -> API response mapping."""

from __future__ import annotations

from app.domain.audit.entities import AuditLog
from app.domain.trading.entities import Order
from app.interface.api.schemas.trading import AuditLogResponse, OrderResponse


def order_to_response(order: Order) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        exchange_account_id=order.exchange_account_id,
        symbol=order.symbol,
        side=order.side.value,
        type=order.type.value,
        status=order.status.value,
        quantity=str(order.quantity),
        executed_quantity=str(order.executed_quantity),
        cumulative_quote_quantity=str(order.cumulative_quote_quantity),
        price=str(order.price) if order.price is not None else None,
        stop_price=str(order.stop_price) if order.stop_price is not None else None,
        time_in_force=order.time_in_force.value if order.time_in_force else None,
        client_order_id=order.client_order_id,
        exchange_order_id=order.exchange_order_id,
        strategy_id=order.strategy_id,
        signal_id=order.signal_id,
        rejection_reason=order.rejection_reason,
        created_at=order.created_at,
        updated_at=order.updated_at,
        submitted_at=order.submitted_at,
        filled_at=order.filled_at,
    )


def audit_log_to_response(entry: AuditLog) -> AuditLogResponse:
    return AuditLogResponse(
        id=entry.id,
        event_type=entry.event_type,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        actor_user_id=entry.actor_user_id,
        occurred_at=entry.occurred_at,
        payload=entry.payload,
    )
