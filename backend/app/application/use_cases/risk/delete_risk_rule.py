from __future__ import annotations

import uuid

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.exceptions import EntityNotFoundError


class DeleteRiskRuleUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, user_id: uuid.UUID, rule_id: uuid.UUID) -> None:
        async with self._uow_factory() as uow:
            rule = await uow.risk_rules.get_by_id(rule_id)
            if rule is None or rule.user_id != user_id:
                raise EntityNotFoundError("RiskRule", rule_id)

            await uow.risk_rules.delete(rule_id)
            await uow.commit()
