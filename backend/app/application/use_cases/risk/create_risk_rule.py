"""Register a new `RiskRule`. Validation of the rule's own shape (does a
threshold-required type have one, does `SYMBOL_WHITELIST` have a symbol
list) happens for free in `RiskRule.__post_init__` — this use case only
adds the one check that isn't a domain invariant of `RiskRule` itself:
that a strategy-scoped rule's `strategy_id` actually belongs to the caller.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.exceptions import EntityNotFoundError
from app.domain.risk.entities import RiskRule
from app.domain.risk.enums import RiskRuleType


@dataclass(frozen=True, slots=True)
class CreateRiskRuleCommand:
    user_id: uuid.UUID
    rule_type: RiskRuleType
    threshold: Decimal | None = None
    strategy_id: uuid.UUID | None = None
    is_active: bool = True
    config: dict[str, Any] = field(default_factory=dict)


class CreateRiskRuleUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: CreateRiskRuleCommand) -> RiskRule:
        now = datetime.now(UTC)
        rule = RiskRule(
            id=uuid.uuid4(),
            user_id=command.user_id,
            rule_type=command.rule_type,
            is_active=command.is_active,
            created_at=now,
            updated_at=now,
            strategy_id=command.strategy_id,
            threshold=command.threshold,
            config=command.config,
        )
        async with self._uow_factory() as uow:
            if command.strategy_id is not None:
                strategy = await uow.strategies.get_by_id(command.strategy_id)
                if strategy is None or strategy.user_id != command.user_id:
                    raise EntityNotFoundError("Strategy", command.strategy_id)

            await uow.risk_rules.add(rule)
            await uow.commit()
        return rule
