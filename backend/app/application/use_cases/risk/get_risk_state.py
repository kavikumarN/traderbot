"""Reads the current user's risk dashboard state — circuit breaker status,
emergency stop status, today's realized loss, the loss streak, and the
equity high-water mark drawdown is measured from. Rolls the daily-loss
window and auto-resumes an expired circuit breaker as a side effect of
reading, same as `RiskEngine.evaluate` does before a trade."""

from __future__ import annotations

import uuid

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.services.risk_engine import RiskEngine
from app.domain.risk.entities import RiskState


class GetRiskStateUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, risk_engine: RiskEngine) -> None:
        self._uow_factory = uow_factory
        self._risk_engine = risk_engine

    async def execute(self, *, user_id: uuid.UUID) -> RiskState:
        async with self._uow_factory() as uow:
            state = await self._risk_engine.get_state(uow, user_id=user_id)
            await uow.commit()
        return state
