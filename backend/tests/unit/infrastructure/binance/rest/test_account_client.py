from __future__ import annotations

import pytest

from app.infrastructure.binance.rest.account_client import BinanceAccountClient
from tests.fakes.fake_binance_http_client import FakeBinanceHttpClient


@pytest.mark.asyncio
async def test_get_balances_signs_the_request_and_maps_entries() -> None:
    http = FakeBinanceHttpClient(
        {
            "/api/v3/account": {
                "balances": [
                    {"asset": "BTC", "free": "1", "locked": "0"},
                    {"asset": "USDT", "free": "100", "locked": "50"},
                ]
            }
        }
    )
    client = BinanceAccountClient(http)

    balances = await client.get_balances()

    assert len(balances) == 2
    assert balances[1].total == 150
    assert http.calls[0]["signed"] is True


@pytest.mark.asyncio
async def test_get_balances_handles_an_empty_account() -> None:
    http = FakeBinanceHttpClient({"/api/v3/account": {"balances": []}})
    client = BinanceAccountClient(http)

    balances = await client.get_balances()

    assert balances == []
