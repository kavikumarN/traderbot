from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.notification.entities import Notification


class NotificationRepository(ABC):
    @abstractmethod
    async def add(self, notification: Notification) -> None: ...

    @abstractmethod
    async def get_by_id(self, notification_id: uuid.UUID) -> Notification | None: ...

    @abstractmethod
    async def list_for_user(
        self, user_id: uuid.UUID, *, unread_only: bool = False, limit: int = 50, offset: int = 0
    ) -> list[Notification]: ...

    @abstractmethod
    async def update(self, notification: Notification) -> None: ...
