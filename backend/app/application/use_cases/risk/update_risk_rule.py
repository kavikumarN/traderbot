from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.exceptions import EntityNotFoundError
from app.domain.risk.entities import RiskRule


@dataclass(frozen=True, slots=True)
class UpdateRiskRuleCommand:
    """`None` on any optional field means "leave unchanged" — there's no
    supported way to clear a threshold/config back to empty once set,
    matching how `RiskRule.__post_init__` never lets a threshold-required
    rule exist without one in the first place."""

    rule_id: uuid.UUID
    user_id: uuid.UUID
    is_active: bool | None = None
    threshold: Decimal | None = None
    config: dict[str, Any] | None = None


class UpdateRiskRuleUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: UpdateRiskRuleCommand) -> RiskRule:
        async with self._uow_factory() as uow:
            rule = await uow.risk_rules.get_by_id(command.rule_id)
            if rule is None or rule.user_id != command.user_id:
                raise EntityNotFoundError("RiskRule", command.rule_id)

            if command.is_active is not None:
                rule.is_active = command.is_active
            if command.threshold is not None:
                rule.threshold = command.threshold
            if command.config is not None:
                rule.config = command.config
            rule.updated_at = datetime.now(UTC)

            await uow.risk_rules.update(rule)
            await uow.commit()
        return rule
