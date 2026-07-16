"""Implements `IUserDataStream` — the authenticated, per-account event feed.

Binance's user-data stream is layered oddly: you obtain a `listenKey` via a
REST call (signed with the API key header but *not* HMAC-signed), then
connect a plain WebSocket to `ws/<listenKey>`. The key expires after 60
minutes of silence, so it must be "kept alive" with a REST PUT roughly
every 30 minutes — handled here as a background task, invisible to callers.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from app.domain.exchange.exceptions import ExchangeError
from app.domain.exchange.models.account import AssetBalance
from app.domain.exchange.ports.user_data_stream import (
    BalanceUpdateEvent,
    IUserDataStream,
    OrderUpdateEvent,
    UserDataEvent,
)
from app.infrastructure.binance import mappers
from app.infrastructure.binance.http_client import BinanceHttpClient
from app.infrastructure.binance.ws.reconnecting_websocket import (
    ReconnectingWebSocket,
    ReconnectPolicy,
    WebSocketConnection,
    WebSocketConnector,
    websockets_connector,
)

logger = logging.getLogger(__name__)

_KEEPALIVE_INTERVAL_SECONDS = 30 * 60  # Binance recommends every 30 minutes; keys expire at 60.


class BinanceUserDataStream(IUserDataStream):
    def __init__(
        self,
        http: BinanceHttpClient,
        ws_base_url: str,
        *,
        connector: WebSocketConnector = websockets_connector,
        reconnect_policy: ReconnectPolicy = ReconnectPolicy(),
        keepalive_interval_seconds: float = _KEEPALIVE_INTERVAL_SECONDS,
        sleep=asyncio.sleep,
    ) -> None:
        self._http = http
        self._ws_base_url = ws_base_url.rstrip("/")
        self._connector = connector
        self._reconnect_policy = reconnect_policy
        self._keepalive_interval = keepalive_interval_seconds
        self._sleep = sleep

        self._listen_key: str | None = None
        self._socket: ReconnectingWebSocket | None = None
        self._keepalive_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._listen_key = await self._create_listen_key()
        self._socket = ReconnectingWebSocket(
            self._url,
            connector=self._connector,
            reconnect_policy=self._reconnect_policy,
            on_reconnect=self._on_reconnect,
        )
        self._keepalive_task = asyncio.ensure_future(self._keepalive_loop())

    def _url(self) -> str:
        assert self._listen_key is not None, "start() must be called before the socket connects"
        return f"{self._ws_base_url}/ws/{self._listen_key}"

    async def _create_listen_key(self) -> str:
        data = await self._http.post(
            "/api/v3/userDataStream", signed=False, rate_limits=(("REQUEST_WEIGHT", 2),)
        )
        return data["listenKey"]

    async def _on_reconnect(self, _connection: WebSocketConnection) -> None:
        # A connection that had to reconnect may have done so *because* the
        # listenKey expired — mint a fresh one so the new connection is
        # good for another 60 minutes regardless of why the old one dropped.
        self._listen_key = await self._create_listen_key()

    async def _keepalive_loop(self) -> None:
        while True:
            await self._sleep(self._keepalive_interval)
            if self._listen_key is None:
                return
            try:
                await self._http.put(
                    "/api/v3/userDataStream",
                    {"listenKey": self._listen_key},
                    rate_limits=(("REQUEST_WEIGHT", 2),),
                )
            except ExchangeError:
                logger.warning("Failed to refresh Binance listenKey; next reconnect will mint a new one")

    def events(self) -> AsyncIterator[UserDataEvent]:
        return self._events()

    async def _events(self) -> AsyncIterator[UserDataEvent]:
        assert self._socket is not None, "call start() before events()"
        async for raw_message in self._socket.messages():
            event = _parse_event(json.loads(raw_message))
            if event is not None:
                yield event

    async def close(self) -> None:
        if self._keepalive_task is not None:
            self._keepalive_task.cancel()
            self._keepalive_task = None
        if self._socket is not None:
            await self._socket.close()
            self._socket = None


def _parse_event(data: dict) -> UserDataEvent | None:
    event_type = data.get("e")
    if event_type == "executionReport":
        return OrderUpdateEvent(order=mappers.to_exchange_order_from_execution_report(data))
    if event_type == "outboundAccountPosition":
        balances = tuple(
            AssetBalance(
                asset=entry["a"],
                free=mappers.parse_decimal(entry["f"]),
                locked=mappers.parse_decimal(entry["l"]),
            )
            for entry in data.get("B", [])
        )
        return BalanceUpdateEvent(balances=balances)
    return None
