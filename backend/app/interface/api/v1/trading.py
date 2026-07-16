"""Order placement, cancellation, and tracking — the trading engine's HTTP
surface. `TradingService` lazily provisions each user's default exchange
account on their first order (see that module's docstring), so no separate
account-linking step is required before placing an order in paper-trading
mode.

Route order matters here: `/orders/open` is registered before
`/orders/{order_id}` so "open" is never parsed as an order id.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.application.services.trading_service import TradingService
from app.domain.entities.user import User
from app.domain.exchange.ports.exchange_client import ExchangeClient
from app.interface.api.deps import get_current_user, get_exchange_client, get_trading_service, require_permission
from app.interface.api.schemas.trading import (
    AuditLogResponse,
    OrderListResponse,
    OrderResponse,
    PlaceLimitOrderRequest,
    PlaceMarketOrderRequest,
    PlaceStopOrderRequest,
)
from app.interface.api.trading_mappers import audit_log_to_response, order_to_response

router = APIRouter(prefix="/trading", tags=["trading"])


@router.post(
    "/orders/market",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("trading:write"))],
    summary="Place a market order",
)
async def place_market_order(
    body: PlaceMarketOrderRequest,
    user: User = Depends(get_current_user),
    exchange: ExchangeClient = Depends(get_exchange_client),
    trading_service: TradingService = Depends(get_trading_service),
) -> OrderResponse:
    order = await trading_service.place_market_order(
        user_id=user.id,
        exchange=exchange,
        symbol=body.symbol,
        side=body.side,
        quantity=body.quantity,
        strategy_id=body.strategy_id,
        signal_id=body.signal_id,
        client_order_id=body.client_order_id,
    )
    return order_to_response(order)


@router.post(
    "/orders/limit",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("trading:write"))],
    summary="Place a limit order",
)
async def place_limit_order(
    body: PlaceLimitOrderRequest,
    user: User = Depends(get_current_user),
    exchange: ExchangeClient = Depends(get_exchange_client),
    trading_service: TradingService = Depends(get_trading_service),
) -> OrderResponse:
    order = await trading_service.place_limit_order(
        user_id=user.id,
        exchange=exchange,
        symbol=body.symbol,
        side=body.side,
        quantity=body.quantity,
        price=body.price,
        time_in_force=body.time_in_force,
        strategy_id=body.strategy_id,
        signal_id=body.signal_id,
        client_order_id=body.client_order_id,
    )
    return order_to_response(order)


@router.post(
    "/orders/stop",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("trading:write"))],
    summary="Place a stop order (stop-loss, optionally stop-limit)",
)
async def place_stop_order(
    body: PlaceStopOrderRequest,
    user: User = Depends(get_current_user),
    exchange: ExchangeClient = Depends(get_exchange_client),
    trading_service: TradingService = Depends(get_trading_service),
) -> OrderResponse:
    order = await trading_service.place_stop_order(
        user_id=user.id,
        exchange=exchange,
        symbol=body.symbol,
        side=body.side,
        quantity=body.quantity,
        stop_price=body.stop_price,
        limit_price=body.limit_price,
        strategy_id=body.strategy_id,
        signal_id=body.signal_id,
        client_order_id=body.client_order_id,
    )
    return order_to_response(order)


@router.get(
    "/orders/open",
    response_model=list[OrderResponse],
    dependencies=[Depends(require_permission("trading:read"))],
    summary="List open (resting/working) orders",
)
async def list_open_orders(
    user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
) -> list[OrderResponse]:
    orders = await trading_service.list_open_orders(user_id=user.id)
    return [order_to_response(order) for order in orders]


@router.get(
    "/orders",
    response_model=OrderListResponse,
    dependencies=[Depends(require_permission("trading:read"))],
    summary="Order history",
)
async def list_order_history(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
) -> OrderListResponse:
    orders = await trading_service.list_order_history(user_id=user.id, limit=limit, offset=offset)
    return OrderListResponse(items=[order_to_response(order) for order in orders], offset=offset, limit=limit)


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    dependencies=[Depends(require_permission("trading:read"))],
    summary="Get order status",
)
async def get_order(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
) -> OrderResponse:
    order = await trading_service.get_order(user_id=user.id, order_id=order_id)
    return order_to_response(order)


@router.post(
    "/orders/{order_id}/cancel",
    response_model=OrderResponse,
    dependencies=[Depends(require_permission("trading:write"))],
    summary="Cancel an order",
)
async def cancel_order(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    exchange: ExchangeClient = Depends(get_exchange_client),
    trading_service: TradingService = Depends(get_trading_service),
) -> OrderResponse:
    order = await trading_service.cancel_order(user_id=user.id, exchange=exchange, order_id=order_id)
    return order_to_response(order)


@router.post(
    "/orders/{order_id}/sync",
    response_model=OrderResponse,
    dependencies=[Depends(require_permission("trading:write"))],
    summary="Refresh a resting order's status from the exchange",
)
async def sync_order(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    exchange: ExchangeClient = Depends(get_exchange_client),
    trading_service: TradingService = Depends(get_trading_service),
) -> OrderResponse:
    order = await trading_service.sync_order(user_id=user.id, exchange=exchange, order_id=order_id)
    return order_to_response(order)


@router.get(
    "/orders/{order_id}/audit-log",
    response_model=list[AuditLogResponse],
    dependencies=[Depends(require_permission("trading:read"))],
    summary="Audit trail for an order",
)
async def get_order_audit_log(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    trading_service: TradingService = Depends(get_trading_service),
) -> list[AuditLogResponse]:
    entries = await trading_service.get_order_audit_log(user_id=user.id, order_id=order_id)
    return [audit_log_to_response(entry) for entry in entries]
