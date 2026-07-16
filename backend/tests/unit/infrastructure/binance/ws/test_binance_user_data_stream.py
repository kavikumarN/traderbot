from __future__ import annotations

import json

import pytest

from app.domain.exchange.ports.user_data_stream import BalanceUpdateEvent, OrderUpdateEvent
from app.infrastructure.binance.ws.binance_user_data_stream import BinanceUserDataStream
from tests.fakes.fake_binance_http_client import FakeBinanceHttpClient
from tests.fakes.fake_websocket import FakeConnector, FakeSleep, FakeWebSocketConnection

EXECUTION_REPORT = {
    "e": "executionReport",
    "s": "BTCUSDT",
    "c": "abc123",
    "S": "BUY",
    "o": "LIMIT",
    "f": "GTC",
    "i": 12345,
    "p": "50000",
    "q": "1",
    "z": "0.5",
    "Z": "25000",
    "X": "PARTIALLY_FILLED",
    "O": 1735689600000,
    "T": 1735689601000,
    "E": 1735689601000,
}

BALANCE_UPDATE = {
    "e": "outboundAccountPosition",
    "E": 1735689601000,
    "B": [{"a": "BTC", "f": "1", "l": "0"}, {"a": "USDT", "f": "100", "l": "0"}],
}


@pytest.mark.asyncio
async def test_start_creates_a_listen_key_and_connects() -> None:
    http = FakeBinanceHttpClient({"/api/v3/userDataStream": {"listenKey": "the-key"}})
    connection = FakeWebSocketConnection([json.dumps(EXECUTION_REPORT)])
    connector = FakeConnector([connection])
    stream = BinanceUserDataStream(http, "wss://stream.binance.com:9443", connector=connector, sleep=FakeSleep())

    await stream.start()

    async for event in stream.events():
        assert isinstance(event, OrderUpdateEvent)
        assert event.order.exchange_order_id == 12345
        break

    assert connector.urls == ["wss://stream.binance.com:9443/ws/the-key"]
    assert http.calls[0]["signed"] is False  # listenKey creation is api-key-only, not HMAC-signed
    await stream.close()


@pytest.mark.asyncio
async def test_parses_balance_update_events() -> None:
    http = FakeBinanceHttpClient({"/api/v3/userDataStream": {"listenKey": "the-key"}})
    connection = FakeWebSocketConnection([json.dumps(BALANCE_UPDATE)])
    stream = BinanceUserDataStream(
        http, "wss://stream.binance.com:9443", connector=FakeConnector([connection]), sleep=FakeSleep()
    )
    await stream.start()

    async for event in stream.events():
        assert isinstance(event, BalanceUpdateEvent)
        assert {b.asset for b in event.balances} == {"BTC", "USDT"}
        break

    await stream.close()


@pytest.mark.asyncio
async def test_unknown_event_types_are_skipped_not_raised() -> None:
    http = FakeBinanceHttpClient({"/api/v3/userDataStream": {"listenKey": "the-key"}})
    connection = FakeWebSocketConnection(
        [json.dumps({"e": "someUnhandledEvent"}), json.dumps(EXECUTION_REPORT)]
    )
    stream = BinanceUserDataStream(
        http, "wss://stream.binance.com:9443", connector=FakeConnector([connection]), sleep=FakeSleep()
    )
    await stream.start()

    events = []
    async for event in stream.events():
        events.append(event)
        break

    assert len(events) == 1
    assert isinstance(events[0], OrderUpdateEvent)
    await stream.close()


@pytest.mark.asyncio
async def test_keepalive_loop_pings_the_listen_key_periodically() -> None:
    http = FakeBinanceHttpClient(
        {"/api/v3/userDataStream": {"listenKey": "the-key"}, "PUT:/api/v3/userDataStream": {}}
    )

    # FakeBinanceHttpClient's `put` needs a response keyed the same way as
    # `get`/`post` — reuse the listenKey creation path's key for simplicity.
    http.responses["/api/v3/userDataStream"] = {"listenKey": "the-key"}

    sleep = FakeSleep()
    stream = BinanceUserDataStream(
        http,
        "wss://stream.binance.com:9443",
        connector=FakeConnector([FakeWebSocketConnection([])]),
        sleep=sleep,
        keepalive_interval_seconds=1800,
    )
    await stream.start()

    # Let the keepalive loop run one iteration.
    import asyncio

    for _ in range(50):
        if sleep.calls:
            break
        await asyncio.sleep(0)

    put_calls = [call for call in http.calls if call["method"] == "PUT"]
    assert len(put_calls) == 1
    assert put_calls[0]["params"] == {"listenKey": "the-key"}

    await stream.close()


@pytest.mark.asyncio
async def test_close_cancels_the_keepalive_task() -> None:
    http = FakeBinanceHttpClient({"/api/v3/userDataStream": {"listenKey": "the-key"}})
    stream = BinanceUserDataStream(
        http,
        "wss://stream.binance.com:9443",
        connector=FakeConnector([FakeWebSocketConnection([])]),
        sleep=FakeSleep(),
    )
    await stream.start()

    task = stream._keepalive_task
    assert task is not None

    await stream.close()

    assert task.cancelled() or task.done()
