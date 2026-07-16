"""Scriptable fake `ExchangeClient` for exercising `ExecutionService` /
`TradingService` without a real Binance connection or the in-memory paper
simulator's own matching logic.

`get_ticker`/`get_candles` *are* implemented (unlike the other market-data
methods below) so this same fake also serves `StrategyEngine` tests, which
poll exactly those two methods — see `ticker_result`/`candles_result`.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.account import AssetBalance, ExchangeOrder
from app.domain.exchange.models.exchange_info import ExchangeInfo
from app.domain.exchange.models.market_data import Candle, OrderBookSnapshot, Ticker, Trade
from app.domain.exchange.models.requests import PlaceOrderRequest
from app.domain.exchange.ports.exchange_client import ExchangeClient


class FakeExchangeClient(ExchangeClient):
    def __init__(self) -> None:
        self.place_order_result: ExchangeOrder | Exception | None = None
        self.cancel_order_result: ExchangeOrder | Exception | None = None
        self.get_order_result: ExchangeOrder | Exception | None = None
        self.balances: list[AssetBalance] = []
        self.placed_requests: list[PlaceOrderRequest] = []
        self.ticker_result: Ticker | Exception | None = None
        self.candles_result: list[Candle] = []

    # --- IMarketDataReader ---

    async def get_exchange_info(self) -> ExchangeInfo:
        raise NotImplementedError

    async def get_ticker(self, symbol: str) -> Ticker:
        if isinstance(self.ticker_result, Exception):
            raise self.ticker_result
        assert self.ticker_result is not None, "test must set ticker_result"
        return self.ticker_result

    async def get_order_book(self, symbol: str, *, limit: int = 100) -> OrderBookSnapshot:
        raise NotImplementedError

    async def get_candles(
        self,
        symbol: str,
        interval: KlineInterval,
        *,
        limit: int = 500,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[Candle]:
        return self.candles_result[-limit:]

    async def get_recent_trades(self, symbol: str, *, limit: int = 500) -> list[Trade]:
        raise NotImplementedError

    # --- IAccountReader ---

    async def get_balances(self) -> list[AssetBalance]:
        return self.balances

    # --- IOrderPlacer ---

    async def place_order(self, request: PlaceOrderRequest) -> ExchangeOrder:
        self.placed_requests.append(request)
        if isinstance(self.place_order_result, Exception):
            raise self.place_order_result
        assert self.place_order_result is not None, "test must set place_order_result"
        return self.place_order_result

    async def cancel_order(
        self,
        symbol: str,
        *,
        exchange_order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> ExchangeOrder:
        if isinstance(self.cancel_order_result, Exception):
            raise self.cancel_order_result
        assert self.cancel_order_result is not None, "test must set cancel_order_result"
        return self.cancel_order_result

    async def get_order(
        self,
        symbol: str,
        *,
        exchange_order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> ExchangeOrder:
        if isinstance(self.get_order_result, Exception):
            raise self.get_order_result
        assert self.get_order_result is not None, "test must set get_order_result"
        return self.get_order_result

    async def get_open_orders(self, symbol: str | None = None) -> list[ExchangeOrder]:
        return []
