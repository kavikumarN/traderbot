"""Domain entity -> response schema mappers for the risk API — pure
functions, no logic beyond field copying/`str()`, matching
`app.interface.api.strategy_mappers`."""

from __future__ import annotations

from app.application.use_cases.risk.calculate_position_size import PositionSizeResult
from app.domain.risk.entities import RiskRule, RiskState
from app.interface.api.schemas.risk import PositionSizeResponse, RiskRuleResponse, RiskStateResponse


def risk_rule_to_response(rule: RiskRule) -> RiskRuleResponse:
    return RiskRuleResponse(
        id=rule.id,
        user_id=rule.user_id,
        strategy_id=rule.strategy_id,
        rule_type=rule.rule_type,
        threshold=str(rule.threshold) if rule.threshold is not None else None,
        is_active=rule.is_active,
        config=rule.config,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def risk_state_to_response(state: RiskState) -> RiskStateResponse:
    return RiskStateResponse(
        user_id=state.user_id,
        circuit_breaker=state.circuit_breaker,
        circuit_breaker_reason=state.circuit_breaker_reason,
        circuit_breaker_tripped_at=state.circuit_breaker_tripped_at,
        circuit_breaker_resume_at=state.circuit_breaker_resume_at,
        emergency_stop=state.emergency_stop,
        emergency_stop_reason=state.emergency_stop_reason,
        emergency_stop_at=state.emergency_stop_at,
        consecutive_losses=state.consecutive_losses,
        daily_loss=str(state.daily_loss),
        daily_loss_date=state.daily_loss_date,
        equity_peak=str(state.equity_peak),
        de_risked=state.de_risked,
        de_risk_multiplier=str(state.de_risk_multiplier),
        de_risk_reason=state.de_risk_reason,
        de_risked_at=state.de_risked_at,
        is_trading_allowed=state.is_trading_allowed,
        updated_at=state.updated_at,
    )


def position_size_to_response(result: PositionSizeResult) -> PositionSizeResponse:
    return PositionSizeResponse(
        quantity=str(result.quantity),
        stop_loss_price=str(result.stop_loss_price),
        take_profit_price=str(result.take_profit_price),
        equity=str(result.equity),
    )
