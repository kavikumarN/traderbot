from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.market_data import Candle
from app.domain.strategy.pattern_recognition import (
    IntervalAnalysis,
    PatternBucket,
    PatternMatch,
    Signal,
    analyze_candles,
    build_analysis_result,
    suggest_strategy,
)


def make_candle(**overrides: object) -> Candle:
    now = datetime(2024, 1, 1, tzinfo=UTC)
    defaults: dict[object, object] = dict(
        symbol="BTCUSDT",
        interval=KlineInterval.ONE_HOUR,
        open_time=now,
        close_time=now + timedelta(hours=1),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=Decimal("10"),
        quote_volume=Decimal("1000"),
        trade_count=5,
        is_closed=True,
    )
    defaults.update(overrides)
    return Candle(**defaults)  # type: ignore[arg-type]


def _flat_run(value: Decimal, count: int, *, start_index: int) -> list[Candle]:
    now = datetime(2024, 1, 1, tzinfo=UTC)
    return [
        make_candle(
            open_time=now + timedelta(hours=start_index + i),
            close_time=now + timedelta(hours=start_index + i + 1),
            open=value,
            close=value,
            high=value + Decimal("0.5"),
            low=value - Decimal("0.5"),
        )
        for i in range(count)
    ]


def _zigzag_candles(pivots: list[Decimal], *, leg_steps: int = 4) -> list[Candle]:
    """Builds a zigzag candle series by linearly interpolating between
    consecutive pivots (`leg_steps` candles per leg), with a tiny strictly
    -increasing per-index epsilon to guarantee every high/low is globally
    unique — avoids accidental ties between distant legs landing inside the
    same swing-detection window without disturbing the intended shape (the
    epsilon is orders of magnitude smaller than the pivot swings)."""

    values: list[Decimal] = []
    for a, b in zip(pivots, pivots[1:], strict=False):
        step = (b - a) / leg_steps
        for s in range(leg_steps):
            values.append(a + step * s)
    values.append(pivots[-1])

    now = datetime(2024, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    for i, v in enumerate(values):
        v = v + Decimal(i) * Decimal("0.0001")
        candles.append(
            make_candle(
                open_time=now + timedelta(hours=i),
                close_time=now + timedelta(hours=i + 1),
                open=v,
                close=v,
                high=v + Decimal("0.5"),
                low=v - Decimal("0.5"),
            )
        )
    return candles


class TestCandlestickPatterns:
    def test_detects_bullish_engulfing(self) -> None:
        now = datetime(2024, 1, 1, tzinfo=UTC)
        prev = make_candle(open_time=now, open=Decimal(100), close=Decimal(95), high=Decimal(101), low=Decimal(94))
        curr = make_candle(
            open_time=now + timedelta(hours=1),
            open=Decimal(94),
            close=Decimal(102),
            high=Decimal(103),
            low=Decimal(93),
        )
        result = analyze_candles(KlineInterval.ONE_HOUR, [prev, curr])
        names = [p.name for p in result.patterns]
        assert "Bullish Engulfing" in names

    def test_detects_bearish_engulfing(self) -> None:
        now = datetime(2024, 1, 1, tzinfo=UTC)
        prev = make_candle(open_time=now, open=Decimal(95), close=Decimal(100), high=Decimal(101), low=Decimal(94))
        curr = make_candle(
            open_time=now + timedelta(hours=1),
            open=Decimal(101),
            close=Decimal(93),
            high=Decimal(102),
            low=Decimal(92),
        )
        result = analyze_candles(KlineInterval.ONE_HOUR, [prev, curr])
        names = [p.name for p in result.patterns]
        assert "Bearish Engulfing" in names

    def test_detects_hammer_after_downtrend(self) -> None:
        now = datetime(2024, 1, 1, tzinfo=UTC)
        downtrend = [
            make_candle(
                open_time=now + timedelta(hours=i),
                open=Decimal(110 - i),
                close=Decimal(109 - i),
                high=Decimal(111 - i),
                low=Decimal(108 - i),
            )
            for i in range(5)
        ]
        hammer = make_candle(
            open_time=now + timedelta(hours=5),
            open=Decimal(105),
            close=Decimal(105.4),
            high=Decimal(105.5),
            low=Decimal(100),
        )
        result = analyze_candles(KlineInterval.ONE_HOUR, [*downtrend, hammer])
        names = [p.name for p in result.patterns]
        assert "Hammer" in names

    def test_flat_doji_candle_detected(self) -> None:
        now = datetime(2024, 1, 1, tzinfo=UTC)
        doji = make_candle(open_time=now, open=Decimal(100), close=Decimal(100.02), high=Decimal(102), low=Decimal(98))
        result = analyze_candles(KlineInterval.ONE_HOUR, [doji])
        names = [p.name for p in result.patterns]
        assert "Doji" in names

    def test_no_patterns_from_empty_candles(self) -> None:
        result = analyze_candles(KlineInterval.ONE_HOUR, [])
        assert result.patterns == []
        assert result.candle_count == 0


class TestStructuralPatterns:
    def test_detects_uptrend(self) -> None:
        pivots = [Decimal(10), Decimal(3), Decimal(17), Decimal(7), Decimal(22), Decimal(12)]
        candles = _zigzag_candles(pivots)
        result = analyze_candles(KlineInterval.ONE_HOUR, candles)
        trend_matches = [p for p in result.patterns if p.name == "Uptrend"]
        assert trend_matches, [p.name for p in result.patterns]
        assert trend_matches[0].signal == Signal.BULLISH
        assert trend_matches[0].bucket == PatternBucket.TREND

    def test_detects_downtrend(self) -> None:
        pivots = [Decimal(22), Decimal(29), Decimal(15), Decimal(25), Decimal(10), Decimal(20)]
        candles = _zigzag_candles(pivots)
        result = analyze_candles(KlineInterval.ONE_HOUR, candles)
        trend_matches = [p for p in result.patterns if p.name == "Downtrend"]
        assert trend_matches, [p.name for p in result.patterns]
        assert trend_matches[0].signal == Signal.BEARISH
        assert trend_matches[0].bucket == PatternBucket.TREND

    def test_detects_range_bound(self) -> None:
        candles = _flat_run(Decimal(100), 40, start_index=0)
        result = analyze_candles(KlineInterval.ONE_HOUR, candles)
        names = [p.name for p in result.patterns]
        assert "Range-bound" in names

    def test_detects_resistance_breakout(self) -> None:
        base = _flat_run(Decimal(100), 21, start_index=0)
        now = datetime(2024, 1, 1, tzinfo=UTC)
        breakout = make_candle(
            open_time=now + timedelta(hours=21),
            open=Decimal(100.5),
            close=Decimal(110),
            high=Decimal(110.5),
            low=Decimal(100.5),
        )
        result = analyze_candles(KlineInterval.ONE_HOUR, [*base, breakout])
        breakouts = [p for p in result.patterns if p.name == "Resistance Breakout"]
        assert breakouts
        assert breakouts[0].signal == Signal.BULLISH
        assert breakouts[0].bucket == PatternBucket.BREAKOUT

    def test_detects_support_breakdown(self) -> None:
        base = _flat_run(Decimal(100), 21, start_index=0)
        now = datetime(2024, 1, 1, tzinfo=UTC)
        breakdown = make_candle(
            open_time=now + timedelta(hours=21),
            open=Decimal(99.5),
            close=Decimal(90),
            high=Decimal(99.5),
            low=Decimal(89.5),
        )
        result = analyze_candles(KlineInterval.ONE_HOUR, [*base, breakdown])
        breakdowns = [p for p in result.patterns if p.name == "Support Breakdown"]
        assert breakdowns
        assert breakdowns[0].signal == Signal.BEARISH
        assert breakdowns[0].bucket == PatternBucket.BREAKOUT

    def test_too_few_candles_yields_no_structural_patterns(self) -> None:
        candles = _flat_run(Decimal(100), 5, start_index=0)
        result = analyze_candles(KlineInterval.ONE_HOUR, candles)
        structural_names = {"Uptrend", "Downtrend", "Range-bound", "Double Top", "Double Bottom"}
        assert not any(p.name in structural_names for p in result.patterns)


class TestSuggestStrategy:
    def _analysis_with(self, bucket: PatternBucket, signal: Signal, confidence: Decimal) -> IntervalAnalysis:
        match = PatternMatch(
            name="synthetic",
            signal=signal,
            bucket=bucket,
            at=datetime(2024, 1, 1, tzinfo=UTC),
            confidence=confidence,
            description="synthetic test pattern",
        )
        return IntervalAnalysis(interval=KlineInterval.ONE_DAY, candle_count=100, patterns=[match])

    def test_returns_none_with_no_patterns(self) -> None:
        analysis = IntervalAnalysis(interval=KlineInterval.ONE_HOUR, candle_count=10, patterns=[])
        assert suggest_strategy([analysis]) is None

    def test_trend_bucket_suggests_ema_crossover(self) -> None:
        analysis = self._analysis_with(PatternBucket.TREND, Signal.BULLISH, Decimal("0.8"))
        suggestion = suggest_strategy([analysis])
        assert suggestion is not None
        assert suggestion.strategy_type == "EMA_CROSSOVER"
        assert suggestion.parameters["quantity"] == "0.01"
        assert suggestion.bucket == PatternBucket.TREND

    def test_reversal_bucket_suggests_rsi(self) -> None:
        analysis = self._analysis_with(PatternBucket.REVERSAL, Signal.BULLISH, Decimal("0.8"))
        suggestion = suggest_strategy([analysis])
        assert suggestion is not None
        assert suggestion.strategy_type == "RSI"

    def test_range_bucket_suggests_grid(self) -> None:
        analysis = self._analysis_with(PatternBucket.RANGE, Signal.NEUTRAL, Decimal("0.8"))
        suggestion = suggest_strategy([analysis])
        assert suggestion is not None
        assert suggestion.strategy_type == "GRID"

    def test_breakout_bucket_suggests_breakout_strategy(self) -> None:
        analysis = self._analysis_with(PatternBucket.BREAKOUT, Signal.BULLISH, Decimal("0.8"))
        suggestion = suggest_strategy([analysis])
        assert suggestion is not None
        assert suggestion.strategy_type == "BREAKOUT"

    def test_higher_timeframe_outweighs_lower_timeframe(self) -> None:
        daily_trend = IntervalAnalysis(
            interval=KlineInterval.ONE_DAY,
            candle_count=100,
            patterns=[
                PatternMatch(
                    name="Uptrend",
                    signal=Signal.BULLISH,
                    bucket=PatternBucket.TREND,
                    at=datetime(2024, 1, 1, tzinfo=UTC),
                    confidence=Decimal("0.65"),
                    description="daily uptrend",
                )
            ],
        )
        minute_doji = IntervalAnalysis(
            interval=KlineInterval.ONE_MINUTE,
            candle_count=100,
            patterns=[
                PatternMatch(
                    name="Doji",
                    signal=Signal.NEUTRAL,
                    bucket=PatternBucket.REVERSAL,
                    at=datetime(2024, 1, 1, tzinfo=UTC),
                    confidence=Decimal("0.4"),
                    description="1m doji",
                )
            ],
        )
        suggestion = suggest_strategy([daily_trend, minute_doji])
        assert suggestion is not None
        assert suggestion.strategy_type == "EMA_CROSSOVER"


class TestBuildAnalysisResult:
    def test_aggregates_across_intervals(self) -> None:
        # Perfectly flat (zero-body) candles legitimately also read as Doji
        # on every single candle — this only exercises the multi-interval
        # wiring, not the bucket-scoring tie-break, so it just checks that
        # both interval analyses ran and a suggestion came out the other end.
        candles = _flat_run(Decimal(100), 40, start_index=0)
        result = build_analysis_result("BTCUSDT", [(KlineInterval.ONE_HOUR, candles), (KlineInterval.ONE_DAY, candles)])
        assert result.symbol == "BTCUSDT"
        assert len(result.intervals) == 2
        assert all("Range-bound" in [p.name for p in interval.patterns] for interval in result.intervals)
        assert result.suggestion is not None

    def test_empty_candles_yields_no_suggestion(self) -> None:
        result = build_analysis_result("BTCUSDT", [(KlineInterval.ONE_HOUR, [])])
        assert result.suggestion is None
