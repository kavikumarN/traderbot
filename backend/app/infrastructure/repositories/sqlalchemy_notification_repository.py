from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import EntityNotFoundError
from app.domain.notification.entities import Notification
from app.domain.notification.repositories import NotificationRepository
from app.infrastructure.db.models import NotificationModel


def _to_domain(model: NotificationModel) -> Notification:
    return Notification(
        id=model.id,
        user_id=model.user_id,
        channel=model.channel,
        severity=model.severity,
        title=model.title,
        message=model.message,
        is_read=model.is_read,
        created_at=model.created_at,
        read_at=model.read_at,
        metadata=dict(model.metadata_),
    )


class SqlAlchemyNotificationRepository(NotificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, notification: Notification) -> None:
        self._session.add(
            NotificationModel(
                id=notification.id,
                user_id=notification.user_id,
                channel=notification.channel,
                severity=notification.severity,
                title=notification.title,
                message=notification.message,
                is_read=notification.is_read,
                read_at=notification.read_at,
                created_at=notification.created_at,
                metadata_=notification.metadata,
            )
        )
        await self._session.flush()

    async def get_by_id(self, notification_id: uuid.UUID) -> Notification | None:
        model = await self._session.get(NotificationModel, notification_id)
        return _to_domain(model) if model else None

    async def list_for_user(
        self, user_id: uuid.UUID, *, unread_only: bool = False, limit: int = 50, offset: int = 0
    ) -> list[Notification]:
        stmt = select(NotificationModel).where(NotificationModel.user_id == user_id)
        if unread_only:
            stmt = stmt.where(NotificationModel.is_read.is_(False))
        stmt = stmt.order_by(NotificationModel.created_at.desc()).offset(offset).limit(limit)
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def update(self, notification: Notification) -> None:
        model = await self._session.get(NotificationModel, notification.id)
        if model is None:
            raise EntityNotFoundError("Notification", notification.id)

        model.is_read = notification.is_read
        model.read_at = notification.read_at
        await self._session.flush()
