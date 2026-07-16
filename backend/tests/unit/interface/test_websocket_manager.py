from __future__ import annotations

import pytest

from app.interface.api.websocket_manager import WebSocketManager


class FakeClientSocket:
    """Minimal duck-typed stand-in for `fastapi.WebSocket` — the manager
    only ever calls `accept()` and `send_json()`."""

    def __init__(self, *, fail_on_send: bool = False) -> None:
        self.accepted = False
        self.sent: list[dict] = []
        self.fail_on_send = fail_on_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: dict) -> None:
        if self.fail_on_send:
            raise ConnectionError("client gone")
        self.sent.append(data)


@pytest.mark.asyncio
async def test_connect_accepts_and_subscribes_up_front() -> None:
    manager = WebSocketManager()
    socket = FakeClientSocket()

    await manager.connect(socket, symbols={"btcusdt"})

    assert socket.accepted is True
    assert manager.connection_count == 1

    await manager.broadcast("BTCUSDT", {"channel": "trade"})
    assert socket.sent == [{"channel": "trade"}]


@pytest.mark.asyncio
async def test_broadcast_only_reaches_subscribed_symbol() -> None:
    manager = WebSocketManager()
    socket = FakeClientSocket()
    await manager.connect(socket, symbols={"BTCUSDT"})

    await manager.broadcast("ETHUSDT", {"channel": "trade"})

    assert socket.sent == []


@pytest.mark.asyncio
async def test_subscribe_after_connect() -> None:
    manager = WebSocketManager()
    socket = FakeClientSocket()
    await manager.connect(socket)

    await manager.subscribe(socket, {"ethusdt"})
    await manager.broadcast("ETHUSDT", {"channel": "ticker"})

    assert socket.sent == [{"channel": "ticker"}]


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery() -> None:
    manager = WebSocketManager()
    socket = FakeClientSocket()
    await manager.connect(socket, symbols={"BTCUSDT"})

    await manager.unsubscribe(socket, {"BTCUSDT"})
    await manager.broadcast("BTCUSDT", {"channel": "trade"})

    assert socket.sent == []


@pytest.mark.asyncio
async def test_disconnect_removes_from_all_symbols() -> None:
    manager = WebSocketManager()
    socket = FakeClientSocket()
    await manager.connect(socket, symbols={"BTCUSDT", "ETHUSDT"})

    await manager.disconnect(socket)

    assert manager.connection_count == 0
    await manager.broadcast("BTCUSDT", {"channel": "trade"})
    assert socket.sent == []


@pytest.mark.asyncio
async def test_broadcast_prunes_dead_connections_without_raising() -> None:
    manager = WebSocketManager()
    dead = FakeClientSocket(fail_on_send=True)
    alive = FakeClientSocket()
    await manager.connect(dead, symbols={"BTCUSDT"})
    await manager.connect(alive, symbols={"BTCUSDT"})

    await manager.broadcast("BTCUSDT", {"channel": "trade"})

    assert alive.sent == [{"channel": "trade"}]
    assert manager.connection_count == 1  # the dead one was pruned


@pytest.mark.asyncio
async def test_broadcast_to_unknown_symbol_is_a_no_op() -> None:
    manager = WebSocketManager()

    await manager.broadcast("DOGEUSDT", {"channel": "trade"})  # no subscribers — must not raise

    assert manager.connection_count == 0


@pytest.mark.asyncio
async def test_two_clients_can_subscribe_to_different_symbols_independently() -> None:
    manager = WebSocketManager()
    btc_client = FakeClientSocket()
    eth_client = FakeClientSocket()
    await manager.connect(btc_client, symbols={"BTCUSDT"})
    await manager.connect(eth_client, symbols={"ETHUSDT"})

    await manager.broadcast("BTCUSDT", {"channel": "trade"})
    await manager.broadcast("ETHUSDT", {"channel": "ticker"})

    assert btc_client.sent == [{"channel": "trade"}]
    assert eth_client.sent == [{"channel": "ticker"}]
