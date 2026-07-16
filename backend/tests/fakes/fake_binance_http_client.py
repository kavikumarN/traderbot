from __future__ import annotations

from typing import Any


class FakeBinanceHttpClient:
    """Stands in for `BinanceHttpClient` in REST-client unit tests — those
    tests exist to verify parameter building and response mapping, not HTTP
    mechanics (which `test_http_client.py` already covers against a real
    `httpx.MockTransport`)."""

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[dict[str, Any]] = []

    async def get(self, path: str, params: dict | None = None, *, signed: bool = False, rate_limits=()) -> Any:
        self.calls.append({"method": "GET", "path": path, "params": params, "signed": signed})
        return self.responses[path]

    async def post(self, path: str, params: dict | None = None, *, signed: bool = True, rate_limits=()) -> Any:
        self.calls.append({"method": "POST", "path": path, "params": params, "signed": signed})
        return self.responses[path]

    async def delete(self, path: str, params: dict | None = None, *, signed: bool = True, rate_limits=()) -> Any:
        self.calls.append({"method": "DELETE", "path": path, "params": params, "signed": signed})
        return self.responses[path]

    async def put(self, path: str, params: dict | None = None, *, signed: bool = False, rate_limits=()) -> Any:
        self.calls.append({"method": "PUT", "path": path, "params": params, "signed": signed})
        return self.responses[path]
