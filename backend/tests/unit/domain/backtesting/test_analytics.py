from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.domain.backtesting.analytics import (
    Fill,
    PositionState,
    compute_max_drawdown,
    compute_sharpe_ratio,
    compute_win_rate,
    simulate_fill,
)
from app.domain.exchange.enums import OrderSide

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


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
