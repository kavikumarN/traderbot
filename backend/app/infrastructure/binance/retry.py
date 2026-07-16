"""Generic retry-with-backoff.

Not Binance-specific — it retries any awaitable-returning callable whose
raised exception is judged retryable, defaulting to
``ExchangeError.retryable`` (see `app.domain.exchange.exceptions`). A rate
limit error that carries a server-told ``retry_after_seconds`` is honored
exactly rather than backed off exponentially.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.domain.exchange.exceptions import ExchangeError


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    jitter_seconds: float = 0.25


def is_retryable_exchange_error(exc: BaseException) -> bool:
    return isinstance(exc, ExchangeError) and exc.retryable


async def retry_async[T](
    operation: Callable[[], Awaitable[T]],
    *,
    policy: RetryPolicy = RetryPolicy(),
    is_retryable: Callable[[BaseException], bool] = is_retryable_exchange_error,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    rng: random.Random | None = None,
) -> T:
    rng = rng or random.Random()
    attempt = 0

    while True:
        attempt += 1
        try:
            return await operation()
        except Exception as exc:
            if attempt >= policy.max_attempts or not is_retryable(exc):
                raise

            retry_after = getattr(exc, "retry_after_seconds", None)
            if retry_after:
                delay = float(retry_after)
            else:
                delay = min(policy.base_delay_seconds * (2 ** (attempt - 1)), policy.max_delay_seconds)
                delay += rng.uniform(0, policy.jitter_seconds)

            await sleep(delay)
