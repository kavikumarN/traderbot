"""The concrete Exchange Adapter Pattern implementation for Binance.

Composes the three narrow REST clients behind the single `ExchangeClient`
port, so a caller that genuinely needs full exchange access can depend on
one object — while each underlying client remains independently usable
(and independently unit-testable) for callers that only need one facet.
Adding a second exchange later means writing one more class shaped like
this one; nothing that depends on `ExchangeClient` has to change.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.account import AssetBalance, ExchangeOrder
from app.domain.exchange.models.exchange_info import ExchangeInfo
from app.domain.exchange.models.market_data import Candle, OrderBookSnapshot, Ticker, Trade
from app.domain.exchange.models.requests import PlaceOrderRequest
from app.domain.exchange.ports.exchange_client import ExchangeClient
from app.infrastructure.binance.http_client import BinanceHttpClient
from app.infrastructure.binance.rest.account_client import BinanceAccountClient
from app.infrastructure.binance.rest.market_data_client import BinanceMarketDataClient
from app.infrastructure.binance.rest.order_client import BinanceOrderClient


class BinanceExchangeAdapter(ExchangeClient):
    def __init__(self, http: BinanceHttpClient) -> None:
        self.market_data = BinanceMarketDataClient(http)
        self.account = BinanceAccountClient(http)
        self.orders = BinanceOrderClient(http)

    # --- IMarketDataReader ---------------------------------------------------------------

    async def get_exchange_info(self) -> ExchangeInfo:
        return await self.market_data.get_exchange_info()

    async def get_ticker(self, symbol: str) -> Ticker:
        return await self.market_data.get_ticker(symbol)

    async def get_order_book(self, symbol: str, *, limit: int = 100) -> OrderBookSnapshot:
        return await self.market_data.get_order_book(symbol, limit=limit)

    async def get_candles(
        self,
        symbol: str,
        interval: KlineInterval,
        *,
        limit: int = 500,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[Candle]:
        return await self.market_data.get_candles(
            symbol, interval, limit=limit, start_time=start_time, end_time=end_time
        )

    async def get_recent_trades(self, symbol: str, *, limit: int = 500) -> list[Trade]:
        return await self.market_data.get_recent_trades(symbol, limit=limit)

    # --- IAccountReader --------------------------------------------------------------------

    async def get_balances(self) -> list[AssetBalance]:
        return await self.account.get_balances()

    # --- IOrderPlacer ----------------------------------------------------------------------

    async def place_order(self, request: PlaceOrderRequest) -> ExchangeOrder:
        return await self.orders.place_order(request)

    async def cancel_order(
        self,
        symbol: str,
        *,
        exchange_order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> ExchangeOrder:
        return await self.orders.cancel_order(
            symbol, exchange_order_id=exchange_order_id, client_order_id=client_order_id
        )

    async def get_order(
        self,
        symbol: str,
        *,
        exchange_order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> ExchangeOrder:
        return await self.orders.get_order(
            symbol, exchange_order_id=exchange_order_id, client_order_id=client_order_id
        )

    async def get_open_orders(self, symbol: str | None = None) -> list[ExchangeOrder]:
        return await self.orders.get_open_orders(symbol)
