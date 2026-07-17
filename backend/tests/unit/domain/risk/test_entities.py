from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.exceptions import ValidationError
from app.domain.risk.entities import RiskRule, RiskState
from app.domain.risk.enums import CircuitBreakerState, RiskRuleType

_NOW = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)


def make_rule(**overrides: object) -> RiskRule:
    defaults: dict[object, object] = dict(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        rule_type=RiskRuleType.MAX_DAILY_LOSS,
        is_active=True,
        created_at=_NOW,
        updated_at=_NOW,
        strategy_id=None,
        threshold=Decimal("100"),
        config={},
    )
    defaults.update(overrides)
    return RiskRule(**defaults)  # type: ignore[arg-type]


def make_state(**overrides: object) -> RiskState:
    defaults: dict[object, object] = dict(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        circuit_breaker=CircuitBreakerState.CLOSED,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return RiskState(**defaults)  # type: ignore[arg-type]


def test_threshold_required_rule_type_without_threshold_raises() -> None:
    with pytest.raises(ValidationError):
        make_rule(rule_type=RiskRuleType.MAX_OPEN_TRADES, threshold=None)


def test_symbol_whitelist_without_symbols_raises() -> None:
    with pytest.raises(ValidationError):
        make_rule(rule_type=RiskRuleType.SYMBOL_WHITELIST, threshold=None, config={})


def test_symbol_whitelist_with_symbols_is_valid() -> None:
    rule = make_rule(rule_type=RiskRuleType.SYMBOL_WHITELIST, threshold=None, config={"symbols": ["BTCUSDT"]})

    assert rule.config["symbols"] == ["BTCUSDT"]


def test_account_wide_rule_applies_to_any_strategy() -> None:
    rule = make_rule(strategy_id=None)

    assert rule.applies_to(uuid.uuid4()) is True


def test_strategy_scoped_rule_does_not_apply_to_other_strategy() -> None:
    strategy_id = uuid.uuid4()
    rule = make_rule(strategy_id=strategy_id)

    assert rule.applies_to(uuid.uuid4()) is False
    assert rule.applies_to(strategy_id) is True


def test_inactive_rule_never_applies() -> None:
    rule = make_rule(strategy_id=None, is_active=False)

    assert rule.applies_to(uuid.uuid4()) is False


def test_roll_daily_window_resets_loss_on_new_day() -> None:
    state = make_state(daily_loss=Decimal("50"), daily_loss_date=_NOW.date())

    state.roll_daily_window((_NOW + timedelta(days=1)).date())

    assert state.daily_loss == Decimal("0")


def test_roll_daily_window_keeps_loss_on_same_day() -> None:
    state = make_state(daily_loss=Decimal("50"), daily_loss_date=_NOW.date())

    state.roll_daily_window(_NOW.date())

    assert state.daily_loss == Decimal("50")


def test_record_trade_result_tracks_loss_and_streak() -> None:
    state = make_state()

    state.record_trade_result(Decimal("-20"))
    state.record_trade_result(Decimal("-10"))

    assert state.daily_loss == Decimal("30")
    assert state.consecutive_losses == 2


def test_record_trade_result_win_resets_streak() -> None:
    state = make_state(consecutive_losses=3)

    state.record_trade_result(Decimal("15"))

    assert state.consecutive_losses == 0
    assert state.daily_loss == Decimal("0")


def test_trip_and_reset_circuit_breaker() -> None:
    state = make_state()
    resume_at = _NOW + timedelta(hours=1)

    state.trip_circuit_breaker(reason="daily loss breached", now=_NOW, resume_at=resume_at)
    assert state.circuit_breaker == CircuitBreakerState.OPEN
    assert state.is_trading_allowed is False

    state.reset_circuit_breaker()
    assert state.circuit_breaker == CircuitBreakerState.CLOSED
    assert state.is_trading_allowed is True


def test_auto_resume_if_due_clears_expired_trip() -> None:
    state = make_state()
    state.trip_circuit_breaker(reason="x", now=_NOW, resume_at=_NOW + timedelta(minutes=30))

    state.auto_resume_if_due(_NOW + timedelta(minutes=29))
    assert state.circuit_breaker == CircuitBreakerState.OPEN

    state.auto_resume_if_due(_NOW + timedelta(minutes=31))
    assert state.circuit_breaker == CircuitBreakerState.CLOSED


def test_emergency_stop_blocks_trading_independent_of_circuit_breaker() -> None:
    state = make_state()

    state.activate_emergency_stop(reason="manual halt", now=_NOW)
    assert state.is_trading_allowed is False

    state.deactivate_emergency_stop()
    assert state.is_trading_allowed is True


def test_drawdown_pct_from_peak() -> None:
    state = make_state(equity_peak=Decimal("1000"))

    assert state.drawdown_pct(Decimal("800")) == Decimal("0.2")
    assert state.drawdown_pct(Decimal("1200")) == Decimal("0")


def test_update_equity_peak_only_increases() -> None:
    state = make_state(equity_peak=Decimal("1000"))

    state.update_equity_peak(Decimal("900"))
    assert state.equity_peak == Decimal("1000")

    state.update_equity_peak(Decimal("1100"))
    assert state.equity_peak == Decimal("1100")


def test_de_risk_defaults_to_full_size_and_not_de_risked() -> None:
    state = make_state()

    assert state.de_risked is False
    assert state.de_risk_multiplier == Decimal("1")


def test_activate_and_rearm_de_risk() -> None:
    state = make_state()

    state.activate_de_risk(multiplier=Decimal("0.5"), reason="drawdown breach", now=_NOW)
    assert state.de_risked is True
    assert state.de_risk_multiplier == Decimal("0.5")
    assert state.de_risk_reason == "drawdown breach"
    assert state.de_risked_at == _NOW

    state.rearm_de_risk()
    assert state.de_risked is False
    assert state.de_risk_multiplier == Decimal("1")
    assert state.de_risk_reason is None
    assert state.de_risked_at is None
