from __future__ import annotations

import asyncio


class FakeWebSocketConnection:
    """A scripted connection: `messages` is consumed in order by `recv()`;
    an `Exception` instance in the list is raised instead of returned,
    letting a test simulate a mid-stream drop."""

    def __init__(self, messages: list[object]) -> None:
        self._messages = list(messages)
        self.sent: list[str] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def recv(self) -> str:
        if not self._messages:
            raise ConnectionError("FakeWebSocketConnection has no more scripted messages")
        item = self._messages.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def close(self) -> None:
        self.closed = True


class HangingConnection:
    """`recv()` blocks forever until `close()` is called (mirrors real
    `websockets` behavior: closing a connection unblocks any pending
    `recv()` with an exception) — used to test that `ReconnectingWebSocket.close()`
    stops the message loop instead of leaving it to reconnect."""

    def __init__(self) -> None:
        self._closed_event = asyncio.Event()
        self.closed = False

    async def send(self, message: str) -> None:
        pass

    async def recv(self) -> str:
        await self._closed_event.wait()
        raise ConnectionError("closed")

    async def close(self) -> None:
        self.closed = True
        self._closed_event.set()


class FakeConnector:
    """Each call returns (or raises) the next item in `connections`,
    in order — lets a test script exactly how many connect attempts
    succeed vs. fail before yielding a working connection."""

    def __init__(self, connections: list[object]) -> None:
        self._connections = list(connections)
        self.urls: list[str] = []

    async def __call__(self, url: str):
        self.urls.append(url)
        if not self._connections:
            raise ConnectionError("FakeConnector has no more scripted connections")
        item = self._connections.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
