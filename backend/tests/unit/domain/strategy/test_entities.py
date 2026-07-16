from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.exchange.enums import OrderSide
from app.domain.strategy.entities import Signal, Strategy
from app.domain.strategy.enums import SignalStatus, StrategyStatus


def make_strategy(**overrides: object) -> Strategy:
    now = datetime.now(UTC)
    defaults: dict[object, object] = dict(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="EMA crossover",
        description="",
        symbol="BTCUSDT",
        status=StrategyStatus.DRAFT,
        version=1,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return Strategy(**defaults)  # type: ignore[arg-type]


def make_signal(**overrides: object) -> Signal:
    defaults: dict[object, object] = dict(
        id=uuid.uuid4(),
        strategy_id=uuid.uuid4(),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        status=SignalStatus.PENDING,
        generated_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return Signal(**defaults)  # type: ignore[arg-type]


NON_PAPER_TRADING_STATUSES = [status for status in StrategyStatus if status != StrategyStatus.PAPER_TRADING]
NON_LIVE_STATUSES = [status for status in StrategyStatus if status != StrategyStatus.LIVE]


class TestStrategy:
    def test_promote_to_live_succeeds_from_paper_trading(self) -> None:
        strategy = make_strategy(status=StrategyStatus.PAPER_TRADING)
        strategy.promote_to_live()
        assert strategy.status == StrategyStatus.LIVE

    @pytest.mark.parametrize("status", NON_PAPER_TRADING_STATUSES)
    def test_promote_to_live_raises_from_every_other_status(self, status: StrategyStatus) -> None:
        strategy = make_strategy(status=status)
        with pytest.raises(ValueError):
            strategy.promote_to_live()

    def test_pause_succeeds_from_live(self) -> None:
        strategy = make_strategy(status=StrategyStatus.LIVE)
        strategy.pause()
        assert strategy.status == StrategyStatus.PAUSED

    @pytest.mark.parametrize("status", NON_LIVE_STATUSES)
    def test_pause_raises_from_every_other_status(self, status: StrategyStatus) -> None:
        strategy = make_strategy(status=status)
        with pytest.raises(ValueError):
            strategy.pause()

    def test_is_live_true_only_when_live(self) -> None:
        assert make_strategy(status=StrategyStatus.LIVE).is_live is True
        assert make_strategy(status=StrategyStatus.PAPER_TRADING).is_live is False


class TestSignal:
    def test_is_expired_false_when_no_expiry_set(self) -> None:
        signal = make_signal(expires_at=None)
        assert signal.is_expired(datetime.now(UTC) + timedelta(days=365)) is False

    def test_is_expired_false_before_expiry(self) -> None:
        now = datetime.now(UTC)
        signal = make_signal(expires_at=now + timedelta(minutes=5))
        assert signal.is_expired(now) is False

    def test_is_expired_true_exactly_at_expiry_boundary(self) -> None:
        now = datetime.now(UTC)
        signal = make_signal(expires_at=now)
        assert signal.is_expired(now) is True

    def test_is_expired_true_after_expiry(self) -> None:
        now = datetime.now(UTC)
        signal = make_signal(expires_at=now - timedelta(seconds=1))
        assert signal.is_expired(now) is True

    def test_is_actionable_true_when_pending_and_not_expired(self) -> None:
        now = datetime.now(UTC)
        signal = make_signal(status=SignalStatus.PENDING, expires_at=now + timedelta(minutes=5))
        assert signal.is_actionable(now) is True

    def test_is_actionable_false_when_pending_but_expired(self) -> None:
        now = datetime.now(UTC)
        signal = make_signal(status=SignalStatus.PENDING, expires_at=now - timedelta(seconds=1))
        assert signal.is_actionable(now) is False

    @pytest.mark.parametrize("status", [s for s in SignalStatus if s != SignalStatus.PENDING])
    def test_is_actionable_false_for_every_non_pending_status(self, status: SignalStatus) -> None:
        signal = make_signal(status=status, expires_at=None)
        assert signal.is_actionable(datetime.now(UTC)) is False
