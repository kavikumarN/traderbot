"""Candlestick and chart-pattern recognition, plus a rule-based mapping from
whatever gets detected to one of the plugin catalog's existing strategy
types (see `app.domain.strategy.plugins`). Pure functions, no I/O — same
spirit as `app.domain.risk.position_sizing` and `app.domain.portfolio.
analytics`. This is the "AI Strategy Builder": deterministic technical
pattern-matching rather than a model call, which is what a trading platform
can actually explain and reproduce.

Two layers of detection:
  - Candlestick patterns: single/double/triple-candle shapes (Doji, Hammer,
    Engulfing, Morning/Evening Star, ...) scanned over the most recent
    candles.
  - Structural (chart) patterns: swing-high/low-derived shapes (Uptrend,
    Downtrend, Range, Double Top/Bottom, Breakout) computed over the whole
    supplied window.

`suggest_strategy` then scores each detected pattern into one of four
buckets (trend / reversal / range / breakout) and maps the winning bucket
to a strategy type + starter parameters pulled from that plugin's own
documented defaults (see each plugin module's docstring).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.market_data import Candle

_DOJI_BODY_RATIO = Decimal("0.1")  # body <= 10% of the candle's full range
_LONG_WICK_RATIO = Decimal("2")  # wick >= 2x the body
_SWING_WINDOW = 3  # candles on each side to confirm a local high/low
_RANGE_BAND_PCT = Decimal("0.03")  # band width / mid-price <= 3% => "range-bound"
_BREAKOUT_LOOKBACK = 20
_MIN_CANDLES_FOR_STRUCTURE = _SWING_WINDOW * 2 + 3

# Higher timeframes get more weight in the aggregate suggestion — a daily
# uptrend says more about "what kind of strategy fits this market" than a
# 1-minute one does.
_INTERVAL_WEIGHT: dict[KlineInterval, int] = {
    KlineInterval.ONE_MINUTE: 1,
    KlineInterval.THREE_MINUTES: 1,
    KlineInterval.FIVE_MINUTES: 2,
    KlineInterval.FIFTEEN_MINUTES: 2,
    KlineInterval.THIRTY_MINUTES: 3,
    KlineInterval.ONE_HOUR: 3,
    KlineInterval.TWO_HOURS: 4,
    KlineInterval.FOUR_HOURS: 4,
    KlineInterval.SIX_HOURS: 5,
    KlineInterval.EIGHT_HOURS: 5,
    KlineInterval.TWELVE_HOURS: 5,
    KlineInterval.ONE_DAY: 6,
    KlineInterval.THREE_DAYS: 6,
    KlineInterval.ONE_WEEK: 7,
    KlineInterval.ONE_MONTH: 7,
}


class Signal(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class PatternBucket(StrEnum):
    """Which family of plugin a detected pattern argues for."""

    TREND = "TREND"
    REVERSAL = "REVERSAL"
    RANGE = "RANGE"
    BREAKOUT = "BREAKOUT"


@dataclass(frozen=True, slots=True)
class PatternMatch:
    name: str
    signal: Signal
    bucket: PatternBucket
    at: datetime
    confidence: Decimal
    description: str


@dataclass(frozen=True, slots=True)
class IntervalAnalysis:
    interval: KlineInterval
    candle_count: int
    patterns: list[PatternMatch]


@dataclass(frozen=True, slots=True)
class StrategySuggestion:
    strategy_type: str
    parameters: dict[str, Any]
    bucket: PatternBucket
    confidence: Decimal
    rationale: str


@dataclass(frozen=True, slots=True)
class PatternAnalysisResult:
    symbol: str
    intervals: list[IntervalAnalysis]
    suggestion: StrategySuggestion | None


def analyze_candles(interval: KlineInterval, candles: list[Candle]) -> IntervalAnalysis:
    """Runs every detector against one interval's candle history."""

    patterns: list[PatternMatch] = []
    patterns.extend(_scan_candlestick_patterns(candles))
    patterns.extend(_scan_structural_patterns(candles))
    return IntervalAnalysis(interval=interval, candle_count=len(candles), patterns=patterns)


def build_analysis_result(
    symbol: str, per_interval: list[tuple[KlineInterval, list[Candle]]]
) -> PatternAnalysisResult:
    analyses = [analyze_candles(interval, candles) for interval, candles in per_interval]
    suggestion = suggest_strategy(analyses)
    return PatternAnalysisResult(symbol=symbol, intervals=analyses, suggestion=suggestion)


# --- Candlestick (single/multi-candle) patterns -------------------------------------------


def _body(c: Candle) -> Decimal:
    return abs(c.close - c.open)


def _range(c: Candle) -> Decimal:
    return c.high - c.low


def _upper_wick(c: Candle) -> Decimal:
    return c.high - max(c.open, c.close)


def _lower_wick(c: Candle) -> Decimal:
    return min(c.open, c.close) - c.low


def _is_bullish(c: Candle) -> bool:
    return c.close > c.open


def _is_bearish(c: Candle) -> bool:
    return c.close < c.open


def _scan_candlestick_patterns(candles: list[Candle]) -> list[PatternMatch]:
    if not candles:
        return []

    matches: list[PatternMatch] = []
    # Only the tail of the window matters for "what's happening right now".
    tail = candles[-30:]
    offset = len(candles) - len(tail)

    for i, c in enumerate(tail):
        idx = offset + i
        rng = _range(c)
        if rng <= 0:
            continue
        body = _body(c)

        if body <= rng * _DOJI_BODY_RATIO:
            matches.append(
                PatternMatch(
                    name="Doji",
                    signal=Signal.NEUTRAL,
                    bucket=PatternBucket.REVERSAL,
                    at=c.open_time,
                    confidence=Decimal("0.4"),
                    description="Open and close are nearly equal — indecision, a possible turning point.",
                )
            )

        upper, lower = _upper_wick(c), _lower_wick(c)
        preceding_trend = _local_trend(candles, idx)

        if lower >= body * _LONG_WICK_RATIO and upper <= body and preceding_trend == Signal.BEARISH:
            matches.append(
                PatternMatch(
                    name="Hammer",
                    signal=Signal.BULLISH,
                    bucket=PatternBucket.REVERSAL,
                    at=c.open_time,
                    confidence=Decimal("0.6"),
                    description="Long lower wick after a downtrend — buyers rejected lower prices.",
                )
            )

        if upper >= body * _LONG_WICK_RATIO and lower <= body and preceding_trend == Signal.BULLISH:
            matches.append(
                PatternMatch(
                    name="Shooting Star",
                    signal=Signal.BEARISH,
                    bucket=PatternBucket.REVERSAL,
                    at=c.open_time,
                    confidence=Decimal("0.6"),
                    description="Long upper wick after an uptrend — sellers rejected higher prices.",
                )
            )

        if idx >= 1:
            prev = candles[idx - 1]
            matches.extend(_two_candle_patterns(prev, c))
        if idx >= 2:
            matches.extend(_three_candle_patterns(candles[idx - 2], candles[idx - 1], c))

    return matches


def _two_candle_patterns(prev: Candle, curr: Candle) -> list[PatternMatch]:
    out: list[PatternMatch] = []

    if _is_bearish(prev) and _is_bullish(curr) and curr.open <= prev.close and curr.close >= prev.open:
        out.append(
            PatternMatch(
                name="Bullish Engulfing",
                signal=Signal.BULLISH,
                bucket=PatternBucket.REVERSAL,
                at=curr.open_time,
                confidence=Decimal("0.65"),
                description="A bullish candle's body fully engulfs the prior bearish candle's body.",
            )
        )

    if _is_bullish(prev) and _is_bearish(curr) and curr.open >= prev.close and curr.close <= prev.open:
        out.append(
            PatternMatch(
                name="Bearish Engulfing",
                signal=Signal.BEARISH,
                bucket=PatternBucket.REVERSAL,
                at=curr.open_time,
                confidence=Decimal("0.65"),
                description="A bearish candle's body fully engulfs the prior bullish candle's body.",
            )
        )

    prev_body, curr_body = _body(prev), _body(curr)
    if (
        curr_body > 0
        and prev_body > curr_body * 2
        and max(curr.open, curr.close) <= max(prev.open, prev.close)
        and min(curr.open, curr.close) >= min(prev.open, prev.close)
    ):
        if _is_bearish(prev) and _is_bullish(curr):
            out.append(
                PatternMatch(
                    name="Bullish Harami",
                    signal=Signal.BULLISH,
                    bucket=PatternBucket.REVERSAL,
                    at=curr.open_time,
                    confidence=Decimal("0.45"),
                    description="A small bullish candle sits inside the prior large bearish candle's body.",
                )
            )
        elif _is_bullish(prev) and _is_bearish(curr):
            out.append(
                PatternMatch(
                    name="Bearish Harami",
                    signal=Signal.BEARISH,
                    bucket=PatternBucket.REVERSAL,
                    at=curr.open_time,
                    confidence=Decimal("0.45"),
                    description="A small bearish candle sits inside the prior large bullish candle's body.",
                )
            )

    return out


def _three_candle_patterns(c1: Candle, c2: Candle, c3: Candle) -> list[PatternMatch]:
    out: list[PatternMatch] = []
    small_middle = _body(c2) <= _range(c2) * Decimal("0.3") if _range(c2) > 0 else False

    if (
        _is_bearish(c1)
        and small_middle
        and max(c2.open, c2.close) < c1.close
        and _is_bullish(c3)
        and c3.close >= (c1.open + c1.close) / 2
    ):
        out.append(
            PatternMatch(
                name="Morning Star",
                signal=Signal.BULLISH,
                bucket=PatternBucket.REVERSAL,
                at=c3.open_time,
                confidence=Decimal("0.7"),
                description="Bearish candle, a small-bodied gap down, then a strong bullish reversal.",
            )
        )

    if (
        _is_bullish(c1)
        and small_middle
        and min(c2.open, c2.close) > c1.close
        and _is_bearish(c3)
        and c3.close <= (c1.open + c1.close) / 2
    ):
        out.append(
            PatternMatch(
                name="Evening Star",
                signal=Signal.BEARISH,
                bucket=PatternBucket.REVERSAL,
                at=c3.open_time,
                confidence=Decimal("0.7"),
                description="Bullish candle, a small-bodied gap up, then a strong bearish reversal.",
            )
        )

    return out


def _local_trend(candles: list[Candle], idx: int, *, lookback: int = 5) -> Signal:
    """A cheap "what was happening just before this candle" read, used only
    to give reversal candlesticks directional context (a hammer only means
    something after a decline)."""

    start = max(0, idx - lookback)
    window = candles[start:idx]
    if len(window) < 2:
        return Signal.NEUTRAL
    if window[-1].close > window[0].close:
        return Signal.BULLISH
    if window[-1].close < window[0].close:
        return Signal.BEARISH
    return Signal.NEUTRAL


# --- Structural (chart) patterns -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Swing:
    index: int
    candle: Candle
    is_high: bool


def _find_swings(candles: list[Candle], *, window: int = _SWING_WINDOW) -> list[_Swing]:
    swings: list[_Swing] = []
    for i in range(window, len(candles) - window):
        segment = candles[i - window : i + window + 1]
        c = candles[i]
        if c.high == max(s.high for s in segment):
            swings.append(_Swing(index=i, candle=c, is_high=True))
        elif c.low == min(s.low for s in segment):
            swings.append(_Swing(index=i, candle=c, is_high=False))
    return swings


def _scan_structural_patterns(candles: list[Candle]) -> list[PatternMatch]:
    if len(candles) < _MIN_CANDLES_FOR_STRUCTURE:
        return []

    matches: list[PatternMatch] = []
    swings = _find_swings(candles)
    highs = [s for s in swings if s.is_high]
    lows = [s for s in swings if not s.is_high]

    trend = _detect_trend(candles, highs, lows)
    if trend is not None:
        matches.append(trend)

    range_pattern = _detect_range(candles)
    if range_pattern is not None:
        matches.append(range_pattern)

    matches.extend(_detect_double_top_bottom(highs, lows))

    breakout = _detect_breakout(candles)
    if breakout is not None:
        matches.append(breakout)

    return matches


def _detect_trend(candles: list[Candle], highs: list[_Swing], lows: list[_Swing]) -> PatternMatch | None:
    if len(highs) < 2 or len(lows) < 2:
        return None

    higher_highs = highs[-1].candle.high > highs[-2].candle.high
    higher_lows = lows[-1].candle.low > lows[-2].candle.low
    lower_highs = highs[-1].candle.high < highs[-2].candle.high
    lower_lows = lows[-1].candle.low < lows[-2].candle.low

    last = candles[-1]
    if higher_highs and higher_lows:
        return PatternMatch(
            name="Uptrend",
            signal=Signal.BULLISH,
            bucket=PatternBucket.TREND,
            at=last.open_time,
            confidence=Decimal("0.65"),
            description="Higher swing highs and higher swing lows — a sustained uptrend.",
        )
    if lower_highs and lower_lows:
        return PatternMatch(
            name="Downtrend",
            signal=Signal.BEARISH,
            bucket=PatternBucket.TREND,
            at=last.open_time,
            confidence=Decimal("0.65"),
            description="Lower swing highs and lower swing lows — a sustained downtrend.",
        )
    return None


def _detect_range(candles: list[Candle]) -> PatternMatch | None:
    window = candles[-min(len(candles), 50) :]
    highest = max(c.high for c in window)
    lowest = min(c.low for c in window)
    mid = (highest + lowest) / 2
    if mid <= 0:
        return None

    band_pct = (highest - lowest) / mid
    if band_pct <= _RANGE_BAND_PCT:
        return PatternMatch(
            name="Range-bound",
            signal=Signal.NEUTRAL,
            bucket=PatternBucket.RANGE,
            at=window[-1].open_time,
            confidence=Decimal("0.55"),
            description=f"Price has stayed within a tight {band_pct * 100:.1f}% band — no clear trend.",
        )
    return None


def _detect_double_top_bottom(highs: list[_Swing], lows: list[_Swing]) -> list[PatternMatch]:
    matches: list[PatternMatch] = []
    tolerance = Decimal("0.015")  # swings within 1.5% of each other count as "the same level"

    if len(highs) >= 2:
        a, b = highs[-2], highs[-1]
        if a.candle.high > 0 and abs(a.candle.high - b.candle.high) / a.candle.high <= tolerance:
            matches.append(
                PatternMatch(
                    name="Double Top",
                    signal=Signal.BEARISH,
                    bucket=PatternBucket.REVERSAL,
                    at=b.candle.open_time,
                    confidence=Decimal("0.5"),
                    description="Two swing highs at roughly the same level — resistance rejecting price twice.",
                )
            )

    if len(lows) >= 2:
        a, b = lows[-2], lows[-1]
        if a.candle.low > 0 and abs(a.candle.low - b.candle.low) / a.candle.low <= tolerance:
            matches.append(
                PatternMatch(
                    name="Double Bottom",
                    signal=Signal.BULLISH,
                    bucket=PatternBucket.REVERSAL,
                    at=b.candle.open_time,
                    confidence=Decimal("0.5"),
                    description="Two swing lows at roughly the same level — support holding price twice.",
                )
            )

    return matches


def _detect_breakout(candles: list[Candle]) -> PatternMatch | None:
    if len(candles) < _BREAKOUT_LOOKBACK + 1:
        return None

    window = candles[-(_BREAKOUT_LOOKBACK + 1) : -1]
    last = candles[-1]
    prior_high = max(c.high for c in window)
    prior_low = min(c.low for c in window)

    if last.close > prior_high:
        return PatternMatch(
            name="Resistance Breakout",
            signal=Signal.BULLISH,
            bucket=PatternBucket.BREAKOUT,
            at=last.open_time,
            confidence=Decimal("0.6"),
            description=f"Close broke above the prior {_BREAKOUT_LOOKBACK}-candle high.",
        )
    if last.close < prior_low:
        return PatternMatch(
            name="Support Breakdown",
            signal=Signal.BEARISH,
            bucket=PatternBucket.BREAKOUT,
            at=last.open_time,
            confidence=Decimal("0.6"),
            description=f"Close broke below the prior {_BREAKOUT_LOOKBACK}-candle low.",
        )
    return None


# --- Aggregation: patterns -> a suggested strategy -----------------------------------------


def suggest_strategy(analyses: list[IntervalAnalysis]) -> StrategySuggestion | None:
    """Scores every detected pattern into its `PatternBucket`, weighted by
    how significant that interval's timeframe is (see `_INTERVAL_WEIGHT`)
    and the pattern's own confidence, then maps the winning bucket to a
    concrete strategy type + starter parameters."""

    scores: dict[PatternBucket, Decimal] = {bucket: Decimal(0) for bucket in PatternBucket}
    total_patterns = 0

    for analysis in analyses:
        weight = Decimal(_INTERVAL_WEIGHT.get(analysis.interval, 1))
        for pattern in analysis.patterns:
            scores[pattern.bucket] += pattern.confidence * weight
            total_patterns += 1

    if total_patterns == 0:
        return None

    winning_bucket = max(scores, key=lambda b: scores[b])
    if scores[winning_bucket] <= 0:
        return None

    total_score = sum(scores.values())
    confidence = (scores[winning_bucket] / total_score) if total_score > 0 else Decimal(0)

    return _bucket_to_suggestion(winning_bucket, confidence)


def _bucket_to_suggestion(bucket: PatternBucket, confidence: Decimal) -> StrategySuggestion:
    if bucket == PatternBucket.TREND:
        return StrategySuggestion(
            strategy_type="EMA_CROSSOVER",
            parameters={"fast_period": 12, "slow_period": 26, "quantity": "0.01"},
            bucket=bucket,
            confidence=confidence,
            rationale="A sustained directional trend was detected — an EMA crossover follows it.",
        )
    if bucket == PatternBucket.REVERSAL:
        return StrategySuggestion(
            strategy_type="RSI",
            parameters={"period": 14, "oversold": "30", "overbought": "70", "quantity": "0.01"},
            bucket=bucket,
            confidence=confidence,
            rationale="Reversal candlestick patterns dominated — RSI trades overbought/oversold turns.",
        )
    if bucket == PatternBucket.RANGE:
        return StrategySuggestion(
            strategy_type="GRID",
            parameters={"grid_levels": 5, "grid_spacing_pct": "1", "quantity": "0.01"},
            bucket=bucket,
            confidence=confidence,
            rationale="Price is range-bound with no clear trend — a grid captures the oscillation.",
        )
    return StrategySuggestion(
        strategy_type="BREAKOUT",
        parameters={"lookback_period": _BREAKOUT_LOOKBACK, "quantity": "0.01"},
        bucket=bucket,
        confidence=confidence,
        rationale="Price broke out of its recent range — a breakout strategy rides the move.",
    )
