"""Port for exchange rate limiting.

Exchange-agnostic on purpose: Binance's limits are weight-based per named
bucket (``REQUEST_WEIGHT``, ``ORDERS``), but the port itself doesn't assume
that — a different exchange's limiter just uses different bucket names.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class RateLimiter(ABC):
    @abstractmethod
    async def acquire(self, bucket: str, weight: int = 1) -> None:
        """Blocks until `weight` units of capacity are available in `bucket`."""
        ...
