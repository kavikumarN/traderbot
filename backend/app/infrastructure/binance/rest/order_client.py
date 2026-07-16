"""Implements `IOrderPlacer` against Binance's signed Spot REST API."""

from __future__ import annotations

from app.domain.exchange.models.account import ExchangeOrder
from app.domain.exchange.models.requests import PlaceOrderRequest
from app.domain.exchange.ports.order_placer import IOrderPlacer
from app.infrastructure.binance import mappers
from app.infrastructure.binance.http_client import BinanceHttpClient


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

        data = await self._http.post(
            "/api/v3/order",
            params,
            signed=True,
            rate_limits=(("REQUEST_WEIGHT", 1), ("ORDERS", 1)),
        )
        return mappers.to_exchange_order(data)

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
