from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit.entities import AuditLog
from app.domain.audit.repositories import AuditLogRepository
from app.infrastructure.db.models import AuditLogModel


def _to_domain(model: AuditLogModel) -> AuditLog:
    return AuditLog(
        id=model.id,
        event_type=model.event_type,
        entity_type=model.entity_type,
        occurred_at=model.occurred_at,
        entity_id=model.entity_id,
        actor_user_id=model.actor_user_id,
        payload=dict(model.payload),
    )


class SqlAlchemyAuditLogRepository(AuditLogRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: AuditLog) -> None:
        self._session.add(
            AuditLogModel(
                id=entry.id,
                event_type=entry.event_type,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                actor_user_id=entry.actor_user_id,
                occurred_at=entry.occurred_at,
                payload=entry.payload,
            )
        )
        await self._session.flush()

    async def list_for_entity(self, entity_type: str, entity_id: uuid.UUID) -> list[AuditLog]:
        stmt = (
            select(AuditLogModel)
            .where(AuditLogModel.entity_type == entity_type, AuditLogModel.entity_id == entity_id)
            .order_by(AuditLogModel.occurred_at.desc())
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def list_recent(self, *, limit: int = 100, offset: int = 0) -> list[AuditLog]:
        stmt = select(AuditLogModel).order_by(AuditLogModel.occurred_at.desc()).offset(offset).limit(limit)
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]
