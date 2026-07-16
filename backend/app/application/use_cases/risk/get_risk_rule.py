from __future__ import annotations

import uuid

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.exceptions import EntityNotFoundError
from app.domain.risk.entities import RiskRule


class GetRiskRuleUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, user_id: uuid.UUID, rule_id: uuid.UUID) -> RiskRule:
        async with self._uow_factory() as uow:
            rule = await uow.risk_rules.get_by_id(rule_id)
        # Same 404 whether the rule doesn't exist or belongs to someone
        # else — an id that exists but isn't yours shouldn't be
        # distinguishable from one that doesn't exist at all.
        if rule is None or rule.user_id != user_id:
            raise EntityNotFoundError("RiskRule", rule_id)
        return rule
