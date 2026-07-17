from __future__ import annotations

from typing import Any


class FakeBinanceHttpClient:
    """Stands in for `BinanceHttpClient` in REST-client unit tests — those
    tests exist to verify parameter building and response mapping, not HTTP
    mechanics (which `test_http_client.py` already covers against a real
    `httpx.MockTransport`)."""

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        # A response value is normally returned as-is on every call (a dict,
        # or a list for endpoints like get_open_orders whose real payload is
        # a JSON array). A *tuple* is treated differently: it's consumed one
        # item per call, letting tests script a failure followed by a
        # recovery response — a real Binance response never decodes to a
        # tuple, so this can't collide with a literal response value. A
        # consumed item that's a BaseException instance is raised.
        self.responses = responses or {}
        self.calls: list[dict[str, Any]] = []

    def _resolve(self, path: str) -> Any:
        value = self.responses[path]
        if isinstance(value, tuple):
            item, *rest = value
            self.responses[path] = tuple(rest)
        else:
            item = value
        if isinstance(item, BaseException):
            raise item
        return item

    async def get(
        self, path: str, params: dict | None = None, *, signed: bool = False, rate_limits=(), retry_policy=None
    ) -> Any:
        self.calls.append({"method": "GET", "path": path, "params": params, "signed": signed})
        return self._resolve(path)

    async def post(
        self, path: str, params: dict | None = None, *, signed: bool = True, rate_limits=(), retry_policy=None
    ) -> Any:
        self.calls.append({"method": "POST", "path": path, "params": params, "signed": signed})
        return self._resolve(path)

    async def delete(
        self, path: str, params: dict | None = None, *, signed: bool = True, rate_limits=(), retry_policy=None
    ) -> Any:
        self.calls.append({"method": "DELETE", "path": path, "params": params, "signed": signed})
        return self._resolve(path)

    async def put(
        self, path: str, params: dict | None = None, *, signed: bool = False, rate_limits=(), retry_policy=None
    ) -> Any:
        self.calls.append({"method": "PUT", "path": path, "params": params, "signed": signed})
        return self._resolve(path)
