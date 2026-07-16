"""Registry of live market-data WebSocket clients.

Subscriptions are per-symbol, not per-channel: a client subscribed to
`BTCUSDT` receives every channel (candle/trade/orderbook/ticker) for that
symbol and filters client-side on the `channel` field in each message —
simple, and entirely sufficient for the two symbols this engine supports.

Structurally satisfies `app.application.ports.broadcaster.MarketDataBroadcaster`
(a `Protocol`) so `MarketDataService` can depend on "a broadcaster" without
importing FastAPI/Starlette.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger(__name__)


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._subscriptions: dict[WebSocket, set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, *, symbols: set[str] = frozenset()) -> None:
        await websocket.accept()
        async with self._lock:
            self._subscriptions[websocket] = set()
        if symbols:
            await self.subscribe(websocket, symbols)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            symbols = self._subscriptions.pop(websocket, set())
            for symbol in symbols:
                self._connections[symbol].discard(websocket)
                if not self._connections[symbol]:
                    del self._connections[symbol]

    async def subscribe(self, websocket: WebSocket, symbols: set[str]) -> None:
        normalized = {symbol.upper() for symbol in symbols}
        async with self._lock:
            if websocket not in self._subscriptions:
                return  # disconnected between the check and here — nothing to do
            self._subscriptions[websocket].update(normalized)
            for symbol in normalized:
                self._connections[symbol].add(websocket)

    async def unsubscribe(self, websocket: WebSocket, symbols: set[str]) -> None:
        normalized = {symbol.upper() for symbol in symbols}
        async with self._lock:
            self._subscriptions[websocket].difference_update(normalized)
            for symbol in normalized:
                self._connections[symbol].discard(websocket)
                if not self._connections[symbol]:
                    del self._connections[symbol]

    async def broadcast(self, symbol: str, message: dict[str, Any]) -> None:
        symbol = symbol.upper()
        async with self._lock:
            targets = list(self._connections.get(symbol, ()))
        if not targets:
            return

        dead: list[WebSocket] = []
        for websocket in targets:
            try:
                await websocket.send_json(message)
            except Exception:
                dead.append(websocket)

        for websocket in dead:
            await self.disconnect(websocket)

    @property
    def connection_count(self) -> int:
        return len(self._subscriptions)
