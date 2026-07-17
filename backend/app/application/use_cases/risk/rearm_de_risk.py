"""Manually clears an active drawdown de-risk (restores full position
sizing) — de-risking never auto-clears on its own, so this is the only way
an account returns to full size after a drawdown-triggered cut."""

from __future__ import annotations

import uuid

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.services.risk_engine import RiskEngine
from app.domain.risk.entities import RiskState


class RearmDeRiskUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, risk_engine: RiskEngine) -> None:
        self._uow_factory = uow_factory
        self._risk_engine = risk_engine

    async def execute(self, *, user_id: uuid.UUID) -> RiskState:
        async with self._uow_factory() as uow:
            state = await self._risk_engine.rearm_de_risk(uow, user_id=user_id)
            await uow.commit()
        return state
