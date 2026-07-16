from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.audit.entities import AuditLog


class AuditLogRepository(ABC):
    @abstractmethod
    async def add(self, entry: AuditLog) -> None:
        """The only write this port exposes — audit records are immutable
        once written."""
        ...

    @abstractmethod
    async def list_for_entity(self, entity_type: str, entity_id: uuid.UUID) -> list[AuditLog]: ...

    @abstractmethod
    async def list_recent(self, *, limit: int = 100, offset: int = 0) -> list[AuditLog]: ...
