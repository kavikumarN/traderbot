"""Incremental technical-indicator calculators.

Each indicator is a small, pure, stateful accumulator: `update(...)` feeds
one new sample (a price or a candle) and returns the indicator's current
value — no I/O, no knowledge of `Strategy`/`Signal`, no batch/array API.
That shape is deliberate: strategies receive market data one tick/candle at
a time from the engine, so an indicator that could only be recomputed over
a whole history array would force every strategy to keep its own growing
buffer just to re-derive a number it already knew a moment ago.

`Decimal` throughout, matching the rest of the domain — an indicator is
still a number a trading decision gets made on.
"""

from __future__ import annotations

from collections import deque
from datetime import date
from decimal import Decimal

from app.domain.exchange.models.market_data import Candle


class EmaIndicator:
    """Exponential moving average.

    Seeded with the first price it sees (rather than warming up on an
    initial simple-moving-average window) — simpler, and the standard
    trade-off small trading bots make: the first few values are a little
    less accurate, but the indicator is live from sample one instead of
    silently doing nothing for `period` samples.
    """

    def __init__(self, *, period: int) -> None:
        if period < 1:
            raise ValueError("period must be >= 1")
        self._multiplier = Decimal(2) / Decimal(period + 1)
        self._value: Decimal | None = None

    def update(self, price: Decimal) -> Decimal:
        if self._value is None:
            self._value = price
        else:
            self._value = (price - self._value) * self._multiplier + self._value
        return self._value

    @property
    def value(self) -> Decimal | None:
        return self._value


class RsiIndicator:
    """Relative Strength Index, Wilder's smoothing method.

    Returns `None` until `period` price deltas have been observed (RSI is
    undefined before then) — callers must handle that, not treat it as 0.
    """

    def __init__(self, *, period: int = 14) -> None:
        if period < 1:
            raise ValueError("period must be >= 1")
        self._period = period
        self._previous_price: Decimal | None = None
        self._avg_gain: Decimal | None = None
        self._avg_loss: Decimal | None = None
        self._samples = 0

    def update(self, price: Decimal) -> Decimal | None:
        if self._previous_price is None:
            self._previous_price = price
            return None

        delta = price - self._previous_price
        self._previous_price = price
        gain = max(delta, Decimal(0))
        loss = max(-delta, Decimal(0))
        self._samples += 1

        if self._avg_gain is None or self._avg_loss is None:
            self._avg_gain = gain
            self._avg_loss = loss
        else:
            period = Decimal(self._period)
            self._avg_gain = (self._avg_gain * (period - 1) + gain) / period
            self._avg_loss = (self._avg_loss * (period - 1) + loss) / period

        if self._samples < self._period:
            return None
        if self._avg_loss == 0:
            return Decimal(100)

        relative_strength = self._avg_gain / self._avg_loss
        return Decimal(100) - (Decimal(100) / (Decimal(1) + relative_strength))


class MacdIndicator:
    """Moving Average Convergence/Divergence: the spread between a fast and
    slow EMA (the "MACD line"), plus an EMA of that spread (the "signal
    line") — built directly from `EmaIndicator`, not reimplemented."""

    def __init__(self, *, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> None:
        self._fast = EmaIndicator(period=fast_period)
        self._slow = EmaIndicator(period=slow_period)
        self._signal = EmaIndicator(period=signal_period)

    def update(self, price: Decimal) -> tuple[Decimal, Decimal]:
        """Returns `(macd_line, signal_line)`. Live from the first sample —
        see `EmaIndicator`'s own seeding note; `macd_line` starts at exactly
        0 on the first call since both EMAs seed to the same price."""
        macd_line = self._fast.update(price) - self._slow.update(price)
        signal_line = self._signal.update(macd_line)
        return macd_line, signal_line


class VwapIndicator:
    """Volume-Weighted Average Price, reset at the start of each UTC
    calendar day (the standard convention — VWAP is a *session* statistic,
    not a rolling one) and fed from closed candles: `typical_price =
    (high + low + close) / 3`, weighted by candle volume.
    """

    def __init__(self) -> None:
        self._cumulative_price_volume = Decimal(0)
        self._cumulative_volume = Decimal(0)
        self._session_date: date | None = None

    def update(self, candle: Candle) -> Decimal | None:
        candle_date = candle.open_time.date()
        if self._session_date != candle_date:
            self._session_date = candle_date
            self._cumulative_price_volume = Decimal(0)
            self._cumulative_volume = Decimal(0)

        typical_price = (candle.high + candle.low + candle.close) / Decimal(3)
        self._cumulative_price_volume += typical_price * candle.volume
        self._cumulative_volume += candle.volume
        return self.value

    @property
    def value(self) -> Decimal | None:
        if self._cumulative_volume == 0:
            return None
        return self._cumulative_price_volume / self._cumulative_volume


class RollingHighLow:
    """Fixed-size rolling window of candle highs/lows — the building block
    for breakout detection: "has price cleared the highest high (or lowest
    low) of the last N *prior* candles?". `is_full` gates callers from
    acting on a window that hasn't accumulated `period` samples yet."""

    def __init__(self, *, period: int) -> None:
        if period < 1:
            raise ValueError("period must be >= 1")
        self._highs: deque[Decimal] = deque(maxlen=period)
        self._lows: deque[Decimal] = deque(maxlen=period)

    @property
    def is_full(self) -> bool:
        return len(self._highs) == self._highs.maxlen

    @property
    def highest_high(self) -> Decimal:
        return max(self._highs)

    @property
    def lowest_low(self) -> Decimal:
        return min(self._lows)

    def push(self, *, high: Decimal, low: Decimal) -> None:
        self._highs.append(high)
        self._lows.append(low)
