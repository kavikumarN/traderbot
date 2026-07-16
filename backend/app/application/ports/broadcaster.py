"""Port `MarketDataService` pushes live updates through.

A single-method structural port (`Protocol`, like `UnitOfWorkFactory`)
rather than an `ABC` — it exists purely so the application layer can
depend on "a thing that broadcasts market data per symbol" without knowing
`WebSocketManager` (an interface-layer, FastAPI/Starlette-coupled class)
exists.
"""

from __future__ import annotations

from typing import Any, Protocol


class MarketDataBroadcaster(Protocol):
    async def broadcast(self, symbol: str, message: dict[str, Any]) -> None: ...
