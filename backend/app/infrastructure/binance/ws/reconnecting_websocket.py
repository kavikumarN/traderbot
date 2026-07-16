"""A generic, reusable auto-reconnecting WebSocket client.

Nothing here is Binance-specific — it takes a URL factory and reconnects
with exponential backoff (plus jitter) whenever the connection drops for
*any* reason, be it a network blip, a server-side close, or the exchange
recycling the connection. Binance's own streams
(`ws/binance_market_data_stream.py`, `ws/binance_user_data_stream.py`) are
built on top of this rather than reimplementing reconnect logic.

The connector is injectable (`WebSocketConnector`) specifically so tests
can drive reconnection scenarios without a real network — see
`tests/unit/infrastructure/binance/ws/test_reconnecting_websocket.py`.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

import websockets

from app.domain.exchange.enums import ConnectionState


class WebSocketConnection(Protocol):
    async def send(self, message: str) -> None: ...
    async def recv(self) -> str: ...
    async def close(self) -> None: ...


class WebSocketConnector(Protocol):
    async def __call__(self, url: str) -> WebSocketConnection: ...


async def websockets_connector(url: str) -> WebSocketConnection:
    """Default connector: the real `websockets` client, with its own
    ping/pong keepalive enabled so silently-dead connections are detected
    even when no application messages are flowing."""
    return await websockets.connect(url, ping_interval=20, ping_timeout=20)


@dataclass(frozen=True, slots=True)
class ReconnectPolicy:
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    multiplier: float = 2.0
    jitter_seconds: float = 0.5


class ReconnectingWebSocket:
    def __init__(
        self,
        url_factory: Callable[[], str],
        *,
        connector: WebSocketConnector = websockets_connector,
        reconnect_policy: ReconnectPolicy = ReconnectPolicy(),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rng: random.Random | None = None,
        on_state_change: Callable[[ConnectionState], None] | None = None,
        on_reconnect: Callable[[WebSocketConnection], Awaitable[None]] | None = None,
    ) -> None:
        """`on_reconnect` runs after every successful (re)connect — market
        data streams have nothing to resubscribe to (the stream name is in
        the URL itself), but the user-data stream uses this to mint a fresh
        listenKey when the connection was lost."""
        self._url_factory = url_factory
        self._connector = connector
        self._policy = reconnect_policy
        self._sleep = sleep
        self._rng = rng or random.Random()
        self._on_state_change = on_state_change
        self._on_reconnect = on_reconnect

        self._state = ConnectionState.CLOSED
        self._connection: WebSocketConnection | None = None
        self._attempt = 0
        self._closing = False

    @property
    def state(self) -> ConnectionState:
        return self._state

    async def send(self, message: str) -> None:
        if self._connection is None:
            raise RuntimeError("WebSocket is not connected")
        await self._connection.send(message)

    async def messages(self) -> AsyncIterator[str]:
        """Runs until `close()` is called, yielding each text message and
        transparently reconnecting (with backoff) on any failure."""
        self._closing = False
        while not self._closing:
            try:
                await self._connect()
            except Exception:
                if self._closing:
                    return
                self._set_state(ConnectionState.RECONNECTING)
                await self._backoff_sleep()
                continue

            try:
                assert self._connection is not None
                while True:
                    yield await self._connection.recv()
            except Exception:
                if self._closing:
                    return
                self._set_state(ConnectionState.RECONNECTING)
                await self._backoff_sleep()
                continue

    async def close(self) -> None:
        self._closing = True
        self._set_state(ConnectionState.CLOSED)
        if self._connection is not None:
            connection, self._connection = self._connection, None
            await connection.close()

    async def _connect(self) -> None:
        self._set_state(ConnectionState.CONNECTING if self._attempt == 0 else ConnectionState.RECONNECTING)
        self._connection = await self._connector(self._url_factory())
        self._attempt = 0
        self._set_state(ConnectionState.CONNECTED)
        if self._on_reconnect is not None:
            await self._on_reconnect(self._connection)

    async def _backoff_sleep(self) -> None:
        self._attempt += 1
        delay = min(
            self._policy.initial_delay_seconds * (self._policy.multiplier ** (self._attempt - 1)),
            self._policy.max_delay_seconds,
        )
        delay += self._rng.uniform(0, self._policy.jitter_seconds)
        await self._sleep(delay)

    def _set_state(self, state: ConnectionState) -> None:
        self._state = state
        if self._on_state_change is not None:
            self._on_state_change(state)
