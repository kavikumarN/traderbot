from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.market_data import Candle
from app.domain.strategy.indicators import EmaIndicator, MacdIndicator, RollingHighLow, RsiIndicator, VwapIndicator


def make_candle(**overrides: object) -> Candle:
    now = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    defaults: dict[object, object] = dict(
        symbol="BTCUSDT",
        interval=KlineInterval.ONE_MINUTE,
        open_time=now,
        close_time=now + timedelta(minutes=1),
        open=Decimal("100"),
        high=Decimal("100"),
        low=Decimal("100"),
        close=Decimal("100"),
        volume=Decimal("1"),
        quote_volume=Decimal("100"),
        trade_count=1,
        is_closed=True,
    )
    defaults.update(overrides)
    return Candle(**defaults)  # type: ignore[arg-type]


class TestEmaIndicator:
    def test_seeds_on_first_value(self) -> None:
        ema = EmaIndicator(period=3)
        assert ema.value is None
        assert ema.update(Decimal(10)) == Decimal(10)
        assert ema.value == Decimal(10)

    def test_converges_over_known_sequence(self) -> None:
        ema = EmaIndicator(period=3)
        assert ema.update(Decimal(10)) == Decimal(10)
        assert ema.update(Decimal(20)) == Decimal("15")
        assert ema.update(Decimal(30)) == Decimal("22.5")


class TestRsiIndicator:
    def test_returns_none_before_period_samples(self) -> None:
        rsi = RsiIndicator(period=14)
        assert rsi.update(Decimal(100)) is None
        assert rsi.update(Decimal(101)) is None

    def test_computes_known_value_for_simple_up_down_sequence(self) -> None:
        rsi = RsiIndicator(period=2)
        assert rsi.update(Decimal(100)) is None
        assert rsi.update(Decimal(102)) is None
        value = rsi.update(Decimal(101))
        assert value is not None
        assert float(value) == 66.66666666666667

    def test_returns_100_when_avg_loss_is_zero(self) -> None:
        rsi = RsiIndicator(period=3)
        assert rsi.update(Decimal(10)) is None
        assert rsi.update(Decimal(11)) is None
        assert rsi.update(Decimal(12)) is None
        value = rsi.update(Decimal(13))
        assert value == Decimal(100)


class TestMacdIndicator:
    def test_macd_line_starts_at_zero_on_first_sample(self) -> None:
        macd = MacdIndicator(fast_period=2, slow_period=5, signal_period=2)
        macd_line, signal_line = macd.update(Decimal(100))
        assert macd_line == Decimal(0)
        assert signal_line == Decimal(0)

    def test_update_returns_a_tuple_of_macd_and_signal_line(self) -> None:
        macd = MacdIndicator(fast_period=2, slow_period=5, signal_period=2)
        macd.update(Decimal(100))
        result = macd.update(Decimal(110))
        assert isinstance(result, tuple)
        assert len(result) == 2
        macd_line, signal_line = result
        assert macd_line != Decimal(0)
        assert isinstance(signal_line, Decimal)


class TestVwapIndicator:
    def test_returns_none_with_no_volume(self) -> None:
        vwap = VwapIndicator()
        value = vwap.update(make_candle(high=Decimal(10), low=Decimal(8), close=Decimal(9), volume=Decimal(0)))
        assert value is None
        assert vwap.value is None

    def test_computes_typical_price_weighted_average(self) -> None:
        vwap = VwapIndicator()
        day = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        vwap.update(
            make_candle(
                open_time=day,
                high=Decimal(9),
                low=Decimal(9),
                close=Decimal(9),
                volume=Decimal(100),
            )
        )
        value = vwap.update(
            make_candle(
                open_time=day + timedelta(hours=1),
                high=Decimal(10),
                low=Decimal(10),
                close=Decimal(10),
                volume=Decimal(100),
            )
        )
        assert value == Decimal("9.5")

    def test_resets_on_utc_calendar_day_rollover(self) -> None:
        vwap = VwapIndicator()
        day_one = datetime(2024, 1, 1, 23, 0, tzinfo=UTC)
        day_two = datetime(2024, 1, 2, 0, 0, tzinfo=UTC)
        vwap.update(
            make_candle(open_time=day_one, high=Decimal(9), low=Decimal(9), close=Decimal(9), volume=Decimal(100))
        )
        value = vwap.update(
            make_candle(open_time=day_two, high=Decimal(20), low=Decimal(20), close=Decimal(20), volume=Decimal(50))
        )
        assert value == Decimal(20)


class TestRollingHighLow:
    def test_is_full_false_until_period_pushes(self) -> None:
        window = RollingHighLow(period=3)
        assert window.is_full is False
        window.push(high=Decimal(10), low=Decimal(5))
        assert window.is_full is False
        window.push(high=Decimal(12), low=Decimal(4))
        assert window.is_full is False
        window.push(high=Decimal(8), low=Decimal(6))
        assert window.is_full is True

    def test_highest_high_and_lowest_low(self) -> None:
        window = RollingHighLow(period=3)
        window.push(high=Decimal(10), low=Decimal(5))
        window.push(high=Decimal(12), low=Decimal(4))
        window.push(high=Decimal(8), low=Decimal(6))
        assert window.highest_high == Decimal(12)
        assert window.lowest_low == Decimal(4)

    def test_maxlen_eviction_drops_the_oldest(self) -> None:
        window = RollingHighLow(period=3)
        window.push(high=Decimal(20), low=Decimal(1))
        window.push(high=Decimal(5), low=Decimal(10))
        window.push(high=Decimal(6), low=Decimal(11))
        assert window.highest_high == Decimal(20)
        assert window.lowest_low == Decimal(1)

        window.push(high=Decimal(7), low=Decimal(12))
        assert window.highest_high == Decimal(7)
        assert window.lowest_low == Decimal(10)
