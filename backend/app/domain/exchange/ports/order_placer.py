from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.exchange.models.account import ExchangeOrder
from app.domain.exchange.models.requests import PlaceOrderRequest


class IOrderPlacer(ABC):
    @abstractmethod
    async def place_order(self, request: PlaceOrderRequest) -> ExchangeOrder: ...

    @abstractmethod
    async def cancel_order(
        self,
        symbol: str,
        *,
        exchange_order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> ExchangeOrder: ...

    @abstractmethod
    async def get_order(
        self,
        symbol: str,
        *,
        exchange_order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> ExchangeOrder: ...

    @abstractmethod
    async def get_open_orders(self, symbol: str | None = None) -> list[ExchangeOrder]: ...
