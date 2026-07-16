"""Risk rule management, the risk dashboard, and manual overrides — the
Risk Engine's (Phase 8) HTTP surface. Placing an order is still done
through `/trading/orders/*`; every one of those routes already goes
through `RiskEngine.evaluate` inside `TradingService`, so there is no
separate "check this order" endpoint here — the position-size calculator
below is the only order-shaped read, and it never places anything.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.application.use_cases.risk.calculate_position_size import (
    CalculatePositionSizeCommand,
    CalculatePositionSizeUseCase,
)
from app.application.use_cases.risk.create_risk_rule import CreateRiskRuleCommand, CreateRiskRuleUseCase
from app.application.use_cases.risk.delete_risk_rule import DeleteRiskRuleUseCase
from app.application.use_cases.risk.get_risk_rule import GetRiskRuleUseCase
from app.application.use_cases.risk.get_risk_state import GetRiskStateUseCase
from app.application.use_cases.risk.list_risk_rules import ListRiskRulesUseCase
from app.application.use_cases.risk.reset_circuit_breaker import ResetCircuitBreakerUseCase
from app.application.use_cases.risk.set_emergency_stop import (
    SetEmergencyStopCommand,
    SetEmergencyStopUseCase,
)
from app.application.use_cases.risk.update_risk_rule import UpdateRiskRuleCommand, UpdateRiskRuleUseCase
from app.domain.entities.user import User
from app.interface.api.deps import (
    get_calculate_position_size_use_case,
    get_create_risk_rule_use_case,
    get_current_user,
    get_delete_risk_rule_use_case,
    get_get_risk_rule_use_case,
    get_get_risk_state_use_case,
    get_list_risk_rules_use_case,
    get_reset_circuit_breaker_use_case,
    get_set_emergency_stop_use_case,
    get_update_risk_rule_use_case,
    require_permission,
)
from app.interface.api.risk_mappers import (
    position_size_to_response,
    risk_rule_to_response,
    risk_state_to_response,
)
from app.interface.api.schemas.risk import (
    CreateRiskRuleRequest,
    PositionSizeRequest,
    PositionSizeResponse,
    RiskRuleResponse,
    RiskStateResponse,
    SetEmergencyStopRequest,
    UpdateRiskRuleRequest,
)

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post(
    "/rules",
    response_model=RiskRuleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("risk:write"))],
    summary="Create a risk rule (account-wide, or scoped to one strategy)",
)
async def create_risk_rule(
    body: CreateRiskRuleRequest,
    user: User = Depends(get_current_user),
    use_case: CreateRiskRuleUseCase = Depends(get_create_risk_rule_use_case),
) -> RiskRuleResponse:
    rule = await use_case.execute(
        CreateRiskRuleCommand(
            user_id=user.id,
            rule_type=body.rule_type,
            threshold=body.threshold,
            strategy_id=body.strategy_id,
            is_active=body.is_active,
            config=body.config,
        )
    )
    return risk_rule_to_response(rule)


@router.get(
    "/rules",
    response_model=list[RiskRuleResponse],
    dependencies=[Depends(require_permission("risk:read"))],
    summary="List the current user's risk rules",
)
async def list_risk_rules(
    user: User = Depends(get_current_user),
    use_case: ListRiskRulesUseCase = Depends(get_list_risk_rules_use_case),
) -> list[RiskRuleResponse]:
    rules = await use_case.execute(user_id=user.id)
    return [risk_rule_to_response(rule) for rule in rules]


@router.get(
    "/rules/{rule_id}",
    response_model=RiskRuleResponse,
    dependencies=[Depends(require_permission("risk:read"))],
    summary="Get a risk rule",
)
async def get_risk_rule(
    rule_id: uuid.UUID,
    user: User = Depends(get_current_user),
    use_case: GetRiskRuleUseCase = Depends(get_get_risk_rule_use_case),
) -> RiskRuleResponse:
    rule = await use_case.execute(user_id=user.id, rule_id=rule_id)
    return risk_rule_to_response(rule)


@router.patch(
    "/rules/{rule_id}",
    response_model=RiskRuleResponse,
    dependencies=[Depends(require_permission("risk:write"))],
    summary="Update a risk rule's threshold/config, or activate/deactivate it",
)
async def update_risk_rule(
    rule_id: uuid.UUID,
    body: UpdateRiskRuleRequest,
    user: User = Depends(get_current_user),
    use_case: UpdateRiskRuleUseCase = Depends(get_update_risk_rule_use_case),
) -> RiskRuleResponse:
    rule = await use_case.execute(
        UpdateRiskRuleCommand(
            rule_id=rule_id,
            user_id=user.id,
            is_active=body.is_active,
            threshold=body.threshold,
            config=body.config,
        )
    )
    return risk_rule_to_response(rule)


@router.delete(
    "/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[Depends(require_permission("risk:write"))],
    summary="Delete a risk rule",
)
async def delete_risk_rule(
    rule_id: uuid.UUID,
    user: User = Depends(get_current_user),
    use_case: DeleteRiskRuleUseCase = Depends(get_delete_risk_rule_use_case),
) -> None:
    await use_case.execute(user_id=user.id, rule_id=rule_id)


@router.get(
    "/state",
    response_model=RiskStateResponse,
    dependencies=[Depends(require_permission("risk:read"))],
    summary="Get the current user's risk dashboard: circuit breaker, emergency stop, daily loss, drawdown",
)
async def get_risk_state(
    user: User = Depends(get_current_user),
    use_case: GetRiskStateUseCase = Depends(get_get_risk_state_use_case),
) -> RiskStateResponse:
    state = await use_case.execute(user_id=user.id)
    return risk_state_to_response(state)


@router.post(
    "/emergency-stop",
    response_model=RiskStateResponse,
    dependencies=[Depends(require_permission("risk:write"))],
    summary="Manually halt (or resume) all trading on this account",
)
async def set_emergency_stop(
    body: SetEmergencyStopRequest,
    user: User = Depends(get_current_user),
    use_case: SetEmergencyStopUseCase = Depends(get_set_emergency_stop_use_case),
) -> RiskStateResponse:
    state = await use_case.execute(SetEmergencyStopCommand(user_id=user.id, active=body.active, reason=body.reason))
    return risk_state_to_response(state)


@router.post(
    "/circuit-breaker/reset",
    response_model=RiskStateResponse,
    dependencies=[Depends(require_permission("risk:write"))],
    summary="Manually clear a tripped circuit breaker before its cooldown expires",
)
async def reset_circuit_breaker(
    user: User = Depends(get_current_user),
    use_case: ResetCircuitBreakerUseCase = Depends(get_reset_circuit_breaker_use_case),
) -> RiskStateResponse:
    state = await use_case.execute(user_id=user.id)
    return risk_state_to_response(state)


@router.post(
    "/position-size",
    response_model=PositionSizeResponse,
    dependencies=[Depends(require_permission("risk:read"))],
    summary="Preview a risk-based position size, stop-loss, and take-profit for a hypothetical trade",
)
async def calculate_position_size(
    body: PositionSizeRequest,
    user: User = Depends(get_current_user),
    use_case: CalculatePositionSizeUseCase = Depends(get_calculate_position_size_use_case),
) -> PositionSizeResponse:
    result = await use_case.execute(
        CalculatePositionSizeCommand(
            user_id=user.id,
            side=body.side,
            entry_price=body.entry_price,
            stop_loss_price=body.stop_loss_price,
            stop_loss_pct=body.stop_loss_pct,
            risk_per_trade_pct=body.risk_per_trade_pct,
            reward_risk_ratio=body.reward_risk_ratio,
        )
    )
    return position_size_to_response(result)
