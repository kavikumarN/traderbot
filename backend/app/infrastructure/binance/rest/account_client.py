"""Implements `IAccountReader` against Binance's signed Spot REST API."""

from __future__ import annotations

from app.domain.exchange.models.account import AssetBalance
from app.domain.exchange.ports.account_reader import IAccountReader
from app.infrastructure.binance import mappers
from app.infrastructure.binance.http_client import BinanceHttpClient


class BinanceAccountClient(IAccountReader):
    def __init__(self, http: BinanceHttpClient) -> None:
        self._http = http

    async def get_balances(self) -> list[AssetBalance]:
        data = await self._http.get(
            "/api/v3/account", signed=True, rate_limits=(("REQUEST_WEIGHT", 20),)
        )
        return [mappers.to_asset_balance(entry) for entry in data.get("balances", [])]
