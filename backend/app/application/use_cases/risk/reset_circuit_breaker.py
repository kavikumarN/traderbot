"""Manually clears a tripped circuit breaker before its cooldown expires —
an operator override for when the underlying cause (a bad feed, a stuck
strategy) has already been fixed and there's no reason to wait out the
rest of the cooldown."""

from __future__ import annotations

import uuid

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.services.risk_engine import RiskEngine
from app.domain.risk.entities import RiskState


class ResetCircuitBreakerUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, risk_engine: RiskEngine) -> None:
        self._uow_factory = uow_factory
        self._risk_engine = risk_engine

    async def execute(self, *, user_id: uuid.UUID) -> RiskState:
        async with self._uow_factory() as uow:
            state = await self._risk_engine.reset_circuit_breaker(uow, user_id=user_id)
            await uow.commit()
        return state
