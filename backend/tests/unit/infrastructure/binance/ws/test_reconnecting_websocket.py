from __future__ import annotations

import asyncio
import random

import pytest

from app.domain.exchange.enums import ConnectionState
from app.infrastructure.binance.ws.reconnecting_websocket import ReconnectingWebSocket, ReconnectPolicy
from tests.fakes.fake_websocket import FakeConnector, FakeSleep, FakeWebSocketConnection, HangingConnection


@pytest.mark.asyncio
async def test_yields_messages_from_a_stable_connection() -> None:
    connection = FakeWebSocketConnection(["msg1", "msg2"])
    connector = FakeConnector([connection])
    ws = ReconnectingWebSocket(lambda: "wss://example/stream", connector=connector)

    received = []
    async for message in ws.messages():
        received.append(message)
        if len(received) == 2:
            break
    await ws.close()

    assert received == ["msg1", "msg2"]
    assert connector.urls == ["wss://example/stream"]


@pytest.mark.asyncio
async def test_reconnects_after_a_recv_failure() -> None:
    connection1 = FakeWebSocketConnection(["msg1", ConnectionError("dropped")])
    connection2 = FakeWebSocketConnection(["msg2"])
    connector = FakeConnector([connection1, connection2])
    sleep = FakeSleep()
    ws = ReconnectingWebSocket(
        lambda: "wss://example",
        connector=connector,
        sleep=sleep,
        reconnect_policy=ReconnectPolicy(initial_delay_seconds=0.01, jitter_seconds=0),
    )

    received = []
    async for message in ws.messages():
        received.append(message)
        if len(received) == 2:
            break
    await ws.close()

    assert received == ["msg1", "msg2"]
    assert len(connector.urls) == 2
    assert len(sleep.calls) == 1


@pytest.mark.asyncio
async def test_reconnects_with_growing_backoff_when_connect_itself_fails() -> None:
    connector = FakeConnector(
        [ConnectionError("refused"), ConnectionError("refused"), FakeWebSocketConnection(["ok"])]
    )
    sleep = FakeSleep()
    ws = ReconnectingWebSocket(
        lambda: "wss://example",
        connector=connector,
        sleep=sleep,
        reconnect_policy=ReconnectPolicy(initial_delay_seconds=1.0, multiplier=2.0, jitter_seconds=0),
        rng=random.Random(0),
    )

    received = []
    async for message in ws.messages():
        received.append(message)
        break
    await ws.close()

    assert received == ["ok"]
    assert len(connector.urls) == 3
    assert sleep.calls == [1.0, 2.0]


@pytest.mark.asyncio
async def test_reports_connection_state_transitions() -> None:
    states: list[ConnectionState] = []
    connector = FakeConnector([FakeWebSocketConnection(["msg"])])
    ws = ReconnectingWebSocket(lambda: "wss://example", connector=connector, on_state_change=states.append)

    async for _message in ws.messages():
        break
    await ws.close()

    assert states[0] == ConnectionState.CONNECTING
    assert states[1] == ConnectionState.CONNECTED
    assert states[-1] == ConnectionState.CLOSED


@pytest.mark.asyncio
async def test_close_stops_the_loop_without_reconnecting() -> None:
    connection = HangingConnection()
    connector = FakeConnector([connection])
    ws = ReconnectingWebSocket(lambda: "wss://example", connector=connector)

    received: list[str] = []

    async def consume() -> None:
        async for message in ws.messages():
            received.append(message)

    task = asyncio.ensure_future(consume())
    await asyncio.sleep(0.05)  # let it connect and start blocking on recv()

    await ws.close()
    await asyncio.wait_for(task, timeout=1)

    assert received == []
    assert connection.closed is True
    assert len(connector.urls) == 1  # never reconnected after an intentional close


@pytest.mark.asyncio
async def test_on_reconnect_hook_runs_after_every_successful_connect() -> None:
    hook_calls = []

    async def on_reconnect(connection) -> None:
        hook_calls.append(connection)

    connector = FakeConnector([FakeWebSocketConnection(["msg"])])
    ws = ReconnectingWebSocket(lambda: "wss://example", connector=connector, on_reconnect=on_reconnect)

    async for _message in ws.messages():
        break
    await ws.close()

    assert len(hook_calls) == 1


@pytest.mark.asyncio
async def test_send_requires_an_active_connection() -> None:
    ws = ReconnectingWebSocket(lambda: "wss://example", connector=FakeConnector([]))
    with pytest.raises(RuntimeError, match="not connected"):
        await ws.send("hello")
