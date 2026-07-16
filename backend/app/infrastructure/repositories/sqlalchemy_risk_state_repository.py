from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.risk.entities import RiskState
from app.domain.risk.repositories import RiskStateRepository
from app.infrastructure.db.models import RiskStateModel


def _to_domain(model: RiskStateModel) -> RiskState:
    return RiskState(
        id=model.id,
        user_id=model.user_id,
        circuit_breaker=model.circuit_breaker,
        updated_at=model.updated_at,
        circuit_breaker_reason=model.circuit_breaker_reason,
        circuit_breaker_tripped_at=model.circuit_breaker_tripped_at,
        circuit_breaker_resume_at=model.circuit_breaker_resume_at,
        emergency_stop=model.emergency_stop,
        emergency_stop_reason=model.emergency_stop_reason,
        emergency_stop_at=model.emergency_stop_at,
        consecutive_losses=model.consecutive_losses,
        daily_loss=model.daily_loss,
        daily_loss_date=model.daily_loss_date,
        equity_peak=model.equity_peak,
    )


class SqlAlchemyRiskStateRepository(RiskStateRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_user(self, user_id: uuid.UUID) -> RiskState | None:
        stmt = select(RiskStateModel).where(RiskStateModel.user_id == user_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(model) if model else None

    async def upsert(self, state: RiskState) -> None:
        stmt = select(RiskStateModel).where(RiskStateModel.user_id == state.user_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()

        if model is None:
            self._session.add(
                RiskStateModel(
                    id=state.id,
                    user_id=state.user_id,
                    circuit_breaker=state.circuit_breaker,
                    circuit_breaker_reason=state.circuit_breaker_reason,
                    circuit_breaker_tripped_at=state.circuit_breaker_tripped_at,
                    circuit_breaker_resume_at=state.circuit_breaker_resume_at,
                    emergency_stop=state.emergency_stop,
                    emergency_stop_reason=state.emergency_stop_reason,
                    emergency_stop_at=state.emergency_stop_at,
                    consecutive_losses=state.consecutive_losses,
                    daily_loss=state.daily_loss,
                    daily_loss_date=state.daily_loss_date,
                    equity_peak=state.equity_peak,
                    updated_at=state.updated_at,
                )
            )
        else:
            model.circuit_breaker = state.circuit_breaker
            model.circuit_breaker_reason = state.circuit_breaker_reason
            model.circuit_breaker_tripped_at = state.circuit_breaker_tripped_at
            model.circuit_breaker_resume_at = state.circuit_breaker_resume_at
            model.emergency_stop = state.emergency_stop
            model.emergency_stop_reason = state.emergency_stop_reason
            model.emergency_stop_at = state.emergency_stop_at
            model.consecutive_losses = state.consecutive_losses
            model.daily_loss = state.daily_loss
            model.daily_loss_date = state.daily_loss_date
            model.equity_peak = state.equity_peak
            model.updated_at = state.updated_at

        await self._session.flush()
