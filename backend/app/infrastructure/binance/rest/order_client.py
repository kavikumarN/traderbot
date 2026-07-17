"""Implements `IOrderPlacer` against Binance's signed Spot REST API."""

from __future__ import annotations

from app.domain.exchange.exceptions import ExchangeConnectionError, OrderNotFoundError
from app.domain.exchange.models.account import ExchangeOrder
from app.domain.exchange.models.requests import PlaceOrderRequest
from app.domain.exchange.ports.order_placer import IOrderPlacer
from app.infrastructure.binance import mappers
from app.infrastructure.binance.http_client import BinanceHttpClient
from app.infrastructure.binance.retry import RetryPolicy

# A connection error on POST /order is ambiguous — the order may have been
# placed and only the response was lost. Blindly re-sending it risks a real
# duplicate order (Binance only rejects a re-used newClientOrderId while the
# original is still open; once it reaches a terminal state the id can be
# reused and a "retry" becomes a second real order). So this call disables
# `BinanceHttpClient`'s own automatic retry and instead verifies by
# client_order_id before ever resubmitting.
_NO_AUTO_RETRY = RetryPolicy(max_attempts=1)
_MAX_PLACEMENT_ATTEMPTS = 3


class BinanceOrderClient(IOrderPlacer):
    def __init__(self, http: BinanceHttpClient) -> None:
        self._http = http

    async def place_order(self, request: PlaceOrderRequest) -> ExchangeOrder:
        params: dict[str, object] = {
            "symbol": request.symbol.upper(),
            "side": request.side.value,
            "type": request.type.value,
            "quantity": str(request.quantity),
            "newOrderRespType": "FULL",
        }
        if request.price is not None:
            params["price"] = str(request.price)
        if request.stop_price is not None:
            params["stopPrice"] = str(request.stop_price)
        if request.time_in_force is not None:
            params["timeInForce"] = request.time_in_force.value
        if request.client_order_id is not None:
            params["newClientOrderId"] = request.client_order_id

        for attempt in range(1, _MAX_PLACEMENT_ATTEMPTS + 1):
            try:
                data = await self._http.post(
                    "/api/v3/order",
                    params,
                    signed=True,
                    rate_limits=(("REQUEST_WEIGHT", 1), ("ORDERS", 1)),
                    retry_policy=_NO_AUTO_RETRY,
                )
                return mappers.to_exchange_order(data)
            except ExchangeConnectionError:
                if request.client_order_id is None or attempt == _MAX_PLACEMENT_ATTEMPTS:
                    raise
                existing = await self._find_placed_order(request.symbol, request.client_order_id)
                if existing is not None:
                    return existing
                # Genuinely never reached Binance — safe to resubmit with
                # the same client_order_id.

        raise AssertionError("unreachable: loop above always returns or raises")

    async def _find_placed_order(self, symbol: str, client_order_id: str) -> ExchangeOrder | None:
        try:
            return await self.get_order(symbol, client_order_id=client_order_id)
        except OrderNotFoundError:
            return None

    async def cancel_order(
        self,
        symbol: str,
        *,
        exchange_order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> ExchangeOrder:
        params = _order_reference_params(symbol, exchange_order_id, client_order_id)
        data = await self._http.delete(
            "/api/v3/order", params, signed=True, rate_limits=(("REQUEST_WEIGHT", 1),)
        )
        return mappers.to_exchange_order(data)

    async def get_order(
        self,
        symbol: str,
        *,
        exchange_order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> ExchangeOrder:
        params = _order_reference_params(symbol, exchange_order_id, client_order_id)
        data = await self._http.get(
            "/api/v3/order", params, signed=True, rate_limits=(("REQUEST_WEIGHT", 4),)
        )
        return mappers.to_exchange_order(data)

    async def get_open_orders(self, symbol: str | None = None) -> list[ExchangeOrder]:
        params = {"symbol": symbol.upper()} if symbol else {}
        # Querying across every symbol at once costs far more weight than
        # a single-symbol query — Binance charges for the fan-out.
        weight = 6 if symbol else 80
        data = await self._http.get(
            "/api/v3/openOrders", params, signed=True, rate_limits=(("REQUEST_WEIGHT", weight),)
        )
        return [mappers.to_exchange_order(entry) for entry in data]


def _order_reference_params(
    symbol: str, exchange_order_id: int | None, client_order_id: str | None
) -> dict[str, object]:
    if exchange_order_id is None and client_order_id is None:
        raise ValueError("Provide either exchange_order_id or client_order_id")

    params: dict[str, object] = {"symbol": symbol.upper()}
    if exchange_order_id is not None:
        params["orderId"] = exchange_order_id
    if client_order_id is not None:
        params["origClientOrderId"] = client_order_id
    return params
