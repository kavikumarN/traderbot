from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from app.domain.exchange.enums import OrderSide
from app.domain.portfolio.analytics import (
    EquityPoint,
    bucket_monthly_returns,
    build_equity_curve,
    compute_current_drawdown,
    compute_max_drawdown,
    compute_sharpe_ratio,
    replay_realized_pnl,
)
from app.domain.trading.entities import Trade


def _trade(
    *, symbol: str, side: OrderSide, price: str, quantity: str, commission: str, executed_at: datetime
) -> Trade:
    return Trade(
        id=uuid.uuid4(),
        order_id=uuid.uuid4(),
        exchange_account_id=uuid.uuid4(),
        symbol=symbol,
        side=side,
        price=Decimal(price),
        quantity=Decimal(quantity),
        quote_quantity=Decimal(price) * Decimal(quantity),
        commission=Decimal(commission),
        exchange_trade_id=1,
        executed_at=executed_at,
        commission_asset="USDT",
    )


def _point(day: str, equity: str) -> EquityPoint:
    year, month, day_of_month = (int(part) for part in day.split("-"))
    return EquityPoint(date=date(year, month, day_of_month), equity=Decimal(equity), realized_pnl_cum=Decimal(0), fees_cum=Decimal(0))


class TestReplayRealizedPnl:
    def test_buy_then_full_sell_realizes_the_spread(self) -> None:
        buy = _trade(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            price="100",
            quantity="1",
            commission="0.1",
            executed_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        sell = _trade(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            price="150",
            quantity="1",
            commission="0.15",
            executed_at=datetime(2026, 1, 5, tzinfo=UTC),
        )

        # Deliberately unsorted input — the replay must sort by executed_at itself.
        events = replay_realized_pnl([sell, buy])

        assert [delta for _, delta, _ in events] == [Decimal("0"), Decimal("50")]
        assert [fee for _, _, fee in events] == [Decimal("0.1"), Decimal("0.15")]

    def test_partial_close_realizes_only_the_closed_portion(self) -> None:
        buy = _trade(
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            price="10",
            quantity="2",
            commission="0",
            executed_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        sell = _trade(
            symbol="ETHUSDT",
            side=OrderSide.SELL,
            price="15",
            quantity="1",
            commission="0",
            executed_at=datetime(2026, 1, 2, tzinfo=UTC),
        )

        events = replay_realized_pnl([buy, sell])

        assert [delta for _, delta, _ in events] == [Decimal("0"), Decimal("5")]


class TestBuildEquityCurve:
    def test_anchors_to_current_equity_and_walks_backward(self) -> None:
        buy = _trade(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            price="100",
            quantity="1",
            commission="0.1",
            executed_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        sell = _trade(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            price="150",
            quantity="1",
            commission="0.15",
            executed_at=datetime(2026, 1, 5, tzinfo=UTC),
        )

        points = build_equity_curve([buy, sell], current_equity=Decimal("1050"), as_of=date(2026, 1, 5))

        assert len(points) == 5  # Jan 1 through Jan 5, forward-filled between trade days
        assert points[0].date == date(2026, 1, 1)
        assert points[0].equity == Decimal("1000.15")
        assert points[-1].date == date(2026, 1, 5)
        # Anchored to today's true mark-to-market figure, not the realized-only projection.
        assert points[-1].equity == Decimal("1050")

    def test_extends_through_as_of_even_with_no_trades_since(self) -> None:
        buy = _trade(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            price="100",
            quantity="1",
            commission="0",
            executed_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        points = build_equity_curve([buy], current_equity=Decimal("1000"), as_of=date(2026, 1, 3))

        assert [p.date for p in points] == [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]

    def test_empty_trade_history_returns_no_points(self) -> None:
        assert build_equity_curve([], current_equity=Decimal("100"), as_of=date(2026, 1, 1)) == []


class TestSharpeRatio:
    def test_none_with_too_little_history(self) -> None:
        points = [_point("2026-01-01", "1000"), _point("2026-01-02", "1010")]
        assert compute_sharpe_ratio(points) is None

    def test_positive_for_a_steadily_rising_curve(self) -> None:
        points = [_point(f"2026-01-0{i}", str(1000 + i * 10)) for i in range(1, 6)]
        ratio = compute_sharpe_ratio(points)
        assert ratio is not None
        assert ratio > 0

    def test_none_when_returns_have_no_variance(self) -> None:
        points = [_point(f"2026-01-0{i}", "1000") for i in range(1, 6)]
        assert compute_sharpe_ratio(points) is None


class TestDrawdown:
    def test_max_drawdown_from_peak_to_trough(self) -> None:
        points = [
            _point("2026-01-01", "1000"),
            _point("2026-01-02", "1200"),
            _point("2026-01-03", "900"),
            _point("2026-01-04", "1100"),
        ]
        assert compute_max_drawdown(points) == (Decimal("1200") - Decimal("900")) / Decimal("1200")

    def test_current_drawdown_measures_from_the_all_time_high(self) -> None:
        points = [_point("2026-01-01", "1000"), _point("2026-01-02", "1200"), _point("2026-01-03", "900")]
        assert compute_current_drawdown(points) == (Decimal("1200") - Decimal("900")) / Decimal("1200")

    def test_zero_for_an_ever_rising_curve(self) -> None:
        points = [_point("2026-01-01", "1000"), _point("2026-01-02", "1100")]
        assert compute_max_drawdown(points) == Decimal("0")
        assert compute_current_drawdown(points) == Decimal("0")

    def test_empty_curve_has_zero_drawdown(self) -> None:
        assert compute_max_drawdown([]) == Decimal("0")
        assert compute_current_drawdown([]) == Decimal("0")


class TestMonthlyReturns:
    def test_buckets_by_calendar_month(self) -> None:
        points = [
            _point("2026-01-01", "1000"),
            _point("2026-01-31", "1100"),
            _point("2026-02-15", "1210"),
        ]

        results = bucket_monthly_returns(points)

        assert [r.month for r in results] == ["2026-01", "2026-02"]
        assert results[0].pnl == Decimal("100")
        assert results[0].return_pct == Decimal("100") / Decimal("1000")
        assert results[1].pnl == Decimal("110")

    def test_empty_curve_has_no_months(self) -> None:
        assert bucket_monthly_returns([]) == []
