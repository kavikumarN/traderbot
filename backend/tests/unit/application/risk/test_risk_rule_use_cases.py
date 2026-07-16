from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.application.use_cases.risk.create_risk_rule import CreateRiskRuleCommand, CreateRiskRuleUseCase
from app.application.use_cases.risk.delete_risk_rule import DeleteRiskRuleUseCase
from app.application.use_cases.risk.get_risk_rule import GetRiskRuleUseCase
from app.application.use_cases.risk.list_risk_rules import ListRiskRulesUseCase
from app.application.use_cases.risk.update_risk_rule import UpdateRiskRuleCommand, UpdateRiskRuleUseCase
from app.domain.exceptions import EntityNotFoundError, ValidationError
from app.domain.risk.enums import RiskRuleType
from app.domain.strategy.entities import Strategy
from app.domain.strategy.enums import StrategyStatus

pytestmark = pytest.mark.asyncio


async def test_create_persists_rule_and_commits(uow, uow_factory) -> None:
    use_case = CreateRiskRuleUseCase(uow_factory)
    user_id = uuid.uuid4()

    rule = await use_case.execute(
        CreateRiskRuleCommand(user_id=user_id, rule_type=RiskRuleType.MAX_DAILY_LOSS, threshold=Decimal("500"))
    )

    assert rule.user_id == user_id
    assert rule.is_active is True
    stored = await uow.risk_rules.get_by_id(rule.id)
    assert stored is not None
    assert uow.committed


async def test_create_threshold_required_type_without_threshold_raises(uow_factory) -> None:
    use_case = CreateRiskRuleUseCase(uow_factory)

    with pytest.raises(ValidationError):
        await use_case.execute(
            CreateRiskRuleCommand(user_id=uuid.uuid4(), rule_type=RiskRuleType.MAX_DAILY_LOSS, threshold=None)
        )


async def test_create_for_strategy_owned_by_another_user_raises_not_found(uow, uow_factory) -> None:
    owner_id = uuid.uuid4()
    strategy = Strategy(
        id=uuid.uuid4(),
        user_id=owner_id,
        name="s",
        description="",
        symbol="BTCUSDT",
        status=StrategyStatus.DRAFT,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await uow.strategies.add(strategy)
    use_case = CreateRiskRuleUseCase(uow_factory)

    with pytest.raises(EntityNotFoundError):
        await use_case.execute(
            CreateRiskRuleCommand(
                user_id=uuid.uuid4(),
                rule_type=RiskRuleType.MAX_DAILY_LOSS,
                threshold=Decimal("500"),
                strategy_id=strategy.id,
            )
        )


async def test_list_returns_only_current_users_rules(uow, uow_factory) -> None:
    create_use_case = CreateRiskRuleUseCase(uow_factory)
    user_id = uuid.uuid4()
    await create_use_case.execute(
        CreateRiskRuleCommand(user_id=user_id, rule_type=RiskRuleType.MAX_DAILY_LOSS, threshold=Decimal("500"))
    )
    await create_use_case.execute(
        CreateRiskRuleCommand(user_id=uuid.uuid4(), rule_type=RiskRuleType.MAX_DAILY_LOSS, threshold=Decimal("500"))
    )

    rules = await ListRiskRulesUseCase(uow_factory).execute(user_id=user_id)

    assert len(rules) == 1
    assert rules[0].user_id == user_id


async def test_get_rule_owned_by_another_user_raises_not_found(uow, uow_factory) -> None:
    create_use_case = CreateRiskRuleUseCase(uow_factory)
    rule = await create_use_case.execute(
        CreateRiskRuleCommand(user_id=uuid.uuid4(), rule_type=RiskRuleType.MAX_DAILY_LOSS, threshold=Decimal("500"))
    )

    with pytest.raises(EntityNotFoundError):
        await GetRiskRuleUseCase(uow_factory).execute(user_id=uuid.uuid4(), rule_id=rule.id)


async def test_update_changes_threshold_and_active_flag(uow, uow_factory) -> None:
    user_id = uuid.uuid4()
    rule = await CreateRiskRuleUseCase(uow_factory).execute(
        CreateRiskRuleCommand(user_id=user_id, rule_type=RiskRuleType.MAX_DAILY_LOSS, threshold=Decimal("500"))
    )

    updated = await UpdateRiskRuleUseCase(uow_factory).execute(
        UpdateRiskRuleCommand(rule_id=rule.id, user_id=user_id, is_active=False, threshold=Decimal("750"))
    )

    assert updated.is_active is False
    assert updated.threshold == Decimal("750")


async def test_update_rule_owned_by_another_user_raises_not_found(uow_factory) -> None:
    user_id = uuid.uuid4()
    rule = await CreateRiskRuleUseCase(uow_factory).execute(
        CreateRiskRuleCommand(user_id=user_id, rule_type=RiskRuleType.MAX_DAILY_LOSS, threshold=Decimal("500"))
    )

    with pytest.raises(EntityNotFoundError):
        await UpdateRiskRuleUseCase(uow_factory).execute(
            UpdateRiskRuleCommand(rule_id=rule.id, user_id=uuid.uuid4(), is_active=False)
        )


async def test_delete_removes_rule(uow, uow_factory) -> None:
    user_id = uuid.uuid4()
    rule = await CreateRiskRuleUseCase(uow_factory).execute(
        CreateRiskRuleCommand(user_id=user_id, rule_type=RiskRuleType.MAX_DAILY_LOSS, threshold=Decimal("500"))
    )

    await DeleteRiskRuleUseCase(uow_factory).execute(user_id=user_id, rule_id=rule.id)

    assert await uow.risk_rules.get_by_id(rule.id) is None


async def test_delete_rule_owned_by_another_user_raises_not_found(uow_factory) -> None:
    user_id = uuid.uuid4()
    rule = await CreateRiskRuleUseCase(uow_factory).execute(
        CreateRiskRuleCommand(user_id=user_id, rule_type=RiskRuleType.MAX_DAILY_LOSS, threshold=Decimal("500"))
    )

    with pytest.raises(EntityNotFoundError):
        await DeleteRiskRuleUseCase(uow_factory).execute(user_id=uuid.uuid4(), rule_id=rule.id)
