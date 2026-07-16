from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.domain.backtesting.analytics import (
    Fill,
    PendingEntryOrder,
    PositionBracket,
    PositionState,
    apply_slippage,
    capped_fill_quantity,
    check_bracket_trigger,
    compute_avg_drawdown,
    compute_cagr,
    compute_calmar_ratio,
    compute_max_drawdown,
    compute_profit_factor,
    compute_sharpe_ratio,
    compute_sortino_ratio,
    compute_trade_stats,
    compute_win_rate,
    limit_order_touched,
    simulate_fill,
    update_trailing_stop,
)
from app.domain.exchange.enums import KlineInterval, OrderSide
from app.domain.exchange.models.market_data import Candle

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_SYMBOL = "BTCUSDT"


def _candle(*, open_: str, high: str, low: str, close: str, volume: str = "100") -> Candle:
    return Candle(
        symbol=_SYMBOL,
        interval=KlineInterval.ONE_HOUR,
        open_time=_NOW,
        close_time=_NOW,
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(volume),
        quote_volume=Decimal(volume) * Decimal(close),
        trade_count=1,
        is_closed=True,
    )


def _fill(realized_pnl: str) -> Fill:
    return Fill(
        executed_at=_NOW,
        side=OrderSide.SELL,
        price=Decimal("100"),
        quantity=Decimal("1"),
        commission=Decimal("0"),
        realized_pnl=Decimal(realized_pnl),
        cash_after=Decimal("0"),
        position_after=Decimal("0"),
    )


class TestSimulateFill:
    def test_opening_a_long_charges_cash_and_commission(self) -> None:
        result = simulate_fill(
            PositionState(),
            Decimal("10000"),
            side=OrderSide.BUY,
            price=Decimal("100"),
            quantity=Decimal("1"),
            commission_rate=Decimal("0.01"),
        )

        assert result.position.quantity == Decimal("1")
        assert result.position.avg_entry_price == Decimal("100")
        assert result.commission == Decimal("1")
        assert result.cash == Decimal("9899")
        assert result.realized_pnl == Decimal("0")

    def test_extending_a_long_blends_the_entry_price(self) -> None:
        position = PositionState(quantity=Decimal("1"), avg_entry_price=Decimal("100"))

        result = simulate_fill(
            position,
            Decimal("9899"),
            side=OrderSide.BUY,
            price=Decimal("120"),
            quantity=Decimal("1"),
            commission_rate=Decimal("0.01"),
        )

        assert result.position.quantity == Decimal("2")
        assert result.position.avg_entry_price == Decimal("110")
        assert result.realized_pnl == Decimal("0")

    def test_partial_close_realizes_pnl_on_the_closed_portion_only(self) -> None:
        position = PositionState(quantity=Decimal("2"), avg_entry_price=Decimal("110"))

        result = simulate_fill(
            position,
            Decimal("9777.8"),
            side=OrderSide.SELL,
            price=Decimal("130"),
            quantity=Decimal("1"),
            commission_rate=Decimal("0.01"),
        )

        assert result.position.quantity == Decimal("1")
        assert result.position.avg_entry_price == Decimal("110")  # unchanged — still long, just smaller
        assert result.realized_pnl == Decimal("20")  # (130 - 110) * 1

    def test_overshooting_a_close_flips_the_position_at_the_fill_price(self) -> None:
        position = PositionState(quantity=Decimal("1"), avg_entry_price=Decimal("110"))

        result = simulate_fill(
            position,
            Decimal("0"),
            side=OrderSide.SELL,
            price=Decimal("100"),
            quantity=Decimal("2"),
            commission_rate=Decimal("0"),
        )

        assert result.position.quantity == Decimal("-1")
        assert result.position.avg_entry_price == Decimal("100")  # flipped short at the fill price
        assert result.realized_pnl == Decimal("-10")  # (100 - 110) * 1 closed


class TestMaxDrawdown:
    def test_peak_to_trough(self) -> None:
        equities = [Decimal("1000"), Decimal("1200"), Decimal("900"), Decimal("1100")]
        assert compute_max_drawdown(equities) == (Decimal("1200") - Decimal("900")) / Decimal("1200")

    def test_empty_curve_is_zero(self) -> None:
        assert compute_max_drawdown([]) == Decimal("0")

    def test_ever_rising_curve_is_zero(self) -> None:
        assert compute_max_drawdown([Decimal("1000"), Decimal("1100"), Decimal("1200")]) == Decimal("0")


class TestSharpeRatio:
    def test_none_with_too_little_history(self) -> None:
        assert compute_sharpe_ratio([Decimal("1000"), Decimal("1010")], periods_per_year=Decimal(365)) is None

    def test_positive_for_a_steadily_rising_curve(self) -> None:
        equities = [Decimal(1000 + i * 10) for i in range(6)]
        ratio = compute_sharpe_ratio(equities, periods_per_year=Decimal(365))
        assert ratio is not None
        assert ratio > 0

    def test_none_when_returns_have_no_variance(self) -> None:
        equities = [Decimal("1000")] * 6
        assert compute_sharpe_ratio(equities, periods_per_year=Decimal(365)) is None

    def test_higher_periods_per_year_annualizes_to_a_larger_magnitude(self) -> None:
        equities = [Decimal(1000 + i * 10) for i in range(6)]
        daily = compute_sharpe_ratio(equities, periods_per_year=Decimal(365))
        hourly = compute_sharpe_ratio(equities, periods_per_year=Decimal(365 * 24))
        assert daily is not None and hourly is not None
        assert hourly > daily


class TestWinRate:
    def test_ignores_fills_with_zero_realized_pnl(self) -> None:
        fills = [_fill("0"), _fill("10"), _fill("-5")]
        assert compute_win_rate(fills) == Decimal("1") / Decimal("2")

    def test_zero_with_no_closing_fills(self) -> None:
        assert compute_win_rate([_fill("0"), _fill("0")]) == Decimal("0")

    def test_zero_with_no_fills_at_all(self) -> None:
        assert compute_win_rate([]) == Decimal("0")


class TestAvgDrawdown:
    def test_averages_the_drawdown_series_not_just_the_worst_point(self) -> None:
        # Peak 1200 the whole way; drawdowns are 0, 0, 300/1200, 100/1200.
        equities = [Decimal("1000"), Decimal("1200"), Decimal("900"), Decimal("1100")]
        expected = (Decimal("0") + Decimal("0") + Decimal("300") / Decimal("1200") + Decimal("100") / Decimal("1200")) / 4
        assert compute_avg_drawdown(equities) == expected

    def test_empty_curve_is_zero(self) -> None:
        assert compute_avg_drawdown([]) == Decimal("0")

    def test_less_than_or_equal_to_max_drawdown(self) -> None:
        equities = [Decimal("1000"), Decimal("1200"), Decimal("600"), Decimal("1100"), Decimal("1300")]
        assert compute_avg_drawdown(equities) <= compute_max_drawdown(equities)


class TestSortinoRatio:
    def test_none_with_too_little_history(self) -> None:
        assert compute_sortino_ratio([Decimal("1000"), Decimal("1010")], periods_per_year=Decimal(365)) is None

    def test_positive_for_a_curve_with_a_net_positive_drift(self) -> None:
        # Net upward, but with real down-candles too, so downside deviation
        # is nonzero and the ratio is actually defined.
        equities = [Decimal(v) for v in [1000, 1050, 1020, 1090, 1060, 1140]]
        ratio = compute_sortino_ratio(equities, periods_per_year=Decimal(365))
        assert ratio is not None
        assert ratio > 0

    def test_none_when_there_is_no_downside_at_all(self) -> None:
        equities = [Decimal(1000 + i * 10) for i in range(6)]  # strictly monotonic up — no negative returns
        assert compute_sortino_ratio(equities, periods_per_year=Decimal(365)) is None

    def test_rewards_a_curve_with_smaller_downside_swings(self) -> None:
        # Same net drift, but one path's down-candles are much smaller.
        choppy = [Decimal(v) for v in [1000, 1050, 900, 1080, 950, 1120]]
        smooth = [Decimal(v) for v in [1000, 1050, 1020, 1080, 1060, 1120]]
        choppy_ratio = compute_sortino_ratio(choppy, periods_per_year=Decimal(365))
        smooth_ratio = compute_sortino_ratio(smooth, periods_per_year=Decimal(365))
        assert choppy_ratio is not None and smooth_ratio is not None
        assert smooth_ratio > choppy_ratio


class TestCagr:
    def test_doubling_in_one_year_is_roughly_100_percent(self) -> None:
        equities = [Decimal("1000"), Decimal("2000")]
        cagr = compute_cagr(equities, periods_per_year=Decimal(1))
        assert cagr is not None
        assert cagr == Decimal("1")

    def test_none_with_a_single_point(self) -> None:
        assert compute_cagr([Decimal("1000")], periods_per_year=Decimal(365)) is None

    def test_none_when_equity_ever_touches_zero_or_below(self) -> None:
        assert compute_cagr([Decimal("1000"), Decimal("0")], periods_per_year=Decimal(365)) is None


class TestCalmarRatio:
    def test_divides_cagr_by_max_drawdown(self) -> None:
        assert compute_calmar_ratio(Decimal("0.5"), Decimal("0.25")) == Decimal("2")

    def test_none_without_a_cagr(self) -> None:
        assert compute_calmar_ratio(None, Decimal("0.25")) is None

    def test_none_without_any_drawdown(self) -> None:
        assert compute_calmar_ratio(Decimal("0.5"), Decimal("0")) is None


class TestProfitFactor:
    def test_gross_profit_over_gross_loss(self) -> None:
        fills = [_fill("30"), _fill("20"), _fill("-10")]
        assert compute_profit_factor(fills) == Decimal("50") / Decimal("10")

    def test_none_with_no_losses(self) -> None:
        assert compute_profit_factor([_fill("10"), _fill("20")]) is None

    def test_none_with_no_realized_fills(self) -> None:
        assert compute_profit_factor([_fill("0")]) is None


class TestTradeStats:
    def test_expectancy_is_the_mean_realized_pnl(self) -> None:
        stats = compute_trade_stats([_fill("30"), _fill("-10")])
        assert stats.expectancy == Decimal("10")

    def test_avg_and_largest_win_loss(self) -> None:
        stats = compute_trade_stats([_fill("10"), _fill("30"), _fill("-5"), _fill("-15")])
        assert stats.avg_win == Decimal("20")
        assert stats.avg_loss == Decimal("-10")
        assert stats.largest_win == Decimal("30")
        assert stats.largest_loss == Decimal("-15")

    def test_consecutive_streaks_walk_fills_in_order(self) -> None:
        # win, win, win, loss, loss, win
        fills = [_fill("10"), _fill("5"), _fill("1"), _fill("-1"), _fill("-2"), _fill("3")]
        stats = compute_trade_stats(fills)
        assert stats.max_consecutive_wins == 3
        assert stats.max_consecutive_losses == 2

    def test_zero_valued_defaults_with_no_realized_fills(self) -> None:
        stats = compute_trade_stats([_fill("0")])
        assert stats.expectancy == Decimal("0")
        assert stats.max_consecutive_wins == 0
        assert stats.max_consecutive_losses == 0


class TestApplySlippage:
    def test_buy_fills_worse_higher(self) -> None:
        price = apply_slippage(Decimal("100"), OrderSide.BUY, slippage_bps=Decimal("50"))
        assert price == Decimal("100") * Decimal("1.005")

    def test_sell_fills_worse_lower(self) -> None:
        price = apply_slippage(Decimal("100"), OrderSide.SELL, slippage_bps=Decimal("50"))
        assert price == Decimal("100") / Decimal("1.005")

    def test_zero_slippage_is_a_no_op(self) -> None:
        assert apply_slippage(Decimal("100"), OrderSide.BUY, slippage_bps=Decimal("0")) == Decimal("100")


class TestLimitOrderTouched:
    def test_buy_limit_touches_when_low_reaches_it(self) -> None:
        order = PendingEntryOrder(side=OrderSide.BUY, remaining_quantity=Decimal("1"), limit_price=Decimal("95"))
        candle = _candle(open_="100", high="101", low="94", close="99")
        assert limit_order_touched(order, candle) is True

    def test_buy_limit_does_not_touch_when_low_stays_above_it(self) -> None:
        order = PendingEntryOrder(side=OrderSide.BUY, remaining_quantity=Decimal("1"), limit_price=Decimal("90"))
        candle = _candle(open_="100", high="101", low="94", close="99")
        assert limit_order_touched(order, candle) is False

    def test_sell_limit_touches_when_high_reaches_it(self) -> None:
        order = PendingEntryOrder(side=OrderSide.SELL, remaining_quantity=Decimal("1"), limit_price=Decimal("105"))
        candle = _candle(open_="100", high="106", low="99", close="101")
        assert limit_order_touched(order, candle) is True


class TestCappedFillQuantity:
    def test_caps_at_the_configured_volume_fraction(self) -> None:
        candle = _candle(open_="100", high="101", low="99", close="100", volume="1000")
        # MAX_LIMIT_FILL_VOLUME_FRACTION is 0.1 -> at most 100 of a 1000-volume candle.
        assert capped_fill_quantity(Decimal("500"), candle) == Decimal("100")

    def test_does_not_exceed_the_remaining_quantity(self) -> None:
        candle = _candle(open_="100", high="101", low="99", close="100", volume="1000")
        assert capped_fill_quantity(Decimal("5"), candle) == Decimal("5")

    def test_zero_volume_candle_fills_nothing(self) -> None:
        candle = _candle(open_="100", high="101", low="99", close="100", volume="0")
        assert capped_fill_quantity(Decimal("5"), candle) == Decimal("0")


class TestUpdateTrailingStop:
    def test_no_op_without_a_trailing_pct(self) -> None:
        bracket = PositionBracket()
        candle = _candle(open_="100", high="110", low="95", close="105")
        assert update_trailing_stop(bracket, OrderSide.BUY, candle) is bracket

    def test_initializes_from_the_first_candles_high_for_a_long(self) -> None:
        bracket = PositionBracket(trailing_stop_pct=Decimal("0.1"))
        candle = _candle(open_="100", high="110", low="95", close="105")
        updated = update_trailing_stop(bracket, OrderSide.BUY, candle)
        assert updated.trailing_stop_price == Decimal("110") * Decimal("0.9")

    def test_ratchets_up_but_never_down_for_a_long(self) -> None:
        bracket = PositionBracket(trailing_stop_pct=Decimal("0.1"), trailing_stop_price=Decimal("99"))
        pullback = _candle(open_="100", high="102", low="95", close="98")  # high * 0.9 = 91.8 < 99
        updated = update_trailing_stop(bracket, OrderSide.BUY, pullback)
        assert updated.trailing_stop_price == Decimal("99")  # unchanged, doesn't loosen

        rally = _candle(open_="100", high="120", low="99", close="118")  # high * 0.9 = 108 > 99
        updated_again = update_trailing_stop(updated, OrderSide.BUY, rally)
        assert updated_again.trailing_stop_price == Decimal("120") * Decimal("0.9")

    def test_ratchets_down_but_never_up_for_a_short(self) -> None:
        bracket = PositionBracket(trailing_stop_pct=Decimal("0.1"), trailing_stop_price=Decimal("100"))
        rally = _candle(open_="100", high="105", low="98", close="103")  # low * 1.1 = 107.8 > 100
        updated = update_trailing_stop(bracket, OrderSide.SELL, rally)
        assert updated.trailing_stop_price == Decimal("100")  # unchanged, doesn't loosen


class TestCheckBracketTrigger:
    def test_long_position_stop_loss_triggers_on_a_low_touch(self) -> None:
        bracket = PositionBracket(stop_loss_price=Decimal("90"))
        candle = _candle(open_="100", high="101", low="89", close="95")
        assert check_bracket_trigger(bracket, OrderSide.BUY, candle) == ("stop_loss", Decimal("90"))

    def test_long_position_take_profit_triggers_on_a_high_touch(self) -> None:
        bracket = PositionBracket(take_profit_price=Decimal("110"))
        candle = _candle(open_="100", high="112", low="99", close="108")
        assert check_bracket_trigger(bracket, OrderSide.BUY, candle) == ("take_profit", Decimal("110"))

    def test_stop_wins_when_both_could_trigger_the_same_candle(self) -> None:
        bracket = PositionBracket(stop_loss_price=Decimal("90"), take_profit_price=Decimal("110"))
        candle = _candle(open_="100", high="112", low="89", close="95")
        reason, _ = check_bracket_trigger(bracket, OrderSide.BUY, candle)
        assert reason == "stop_loss"

    def test_trailing_stop_price_is_used_instead_of_stop_loss_price_once_set(self) -> None:
        bracket = PositionBracket(stop_loss_price=Decimal("50"), trailing_stop_pct=Decimal("0.1"), trailing_stop_price=Decimal("95"))
        candle = _candle(open_="100", high="101", low="94", close="98")
        assert check_bracket_trigger(bracket, OrderSide.BUY, candle) == ("trailing_stop", Decimal("95"))

    def test_short_position_stop_loss_triggers_on_a_high_touch(self) -> None:
        bracket = PositionBracket(stop_loss_price=Decimal("110"))
        candle = _candle(open_="100", high="111", low="99", close="105")
        assert check_bracket_trigger(bracket, OrderSide.SELL, candle) == ("stop_loss", Decimal("110"))

    def test_short_position_take_profit_triggers_on_a_low_touch(self) -> None:
        bracket = PositionBracket(take_profit_price=Decimal("90"))
        candle = _candle(open_="100", high="101", low="89", close="95")
        assert check_bracket_trigger(bracket, OrderSide.SELL, candle) == ("take_profit", Decimal("90"))

    def test_no_trigger_when_nothing_is_touched(self) -> None:
        bracket = PositionBracket(stop_loss_price=Decimal("90"), take_profit_price=Decimal("110"))
        candle = _candle(open_="100", high="105", low="95", close="102")
        assert check_bracket_trigger(bracket, OrderSide.BUY, candle) is None
