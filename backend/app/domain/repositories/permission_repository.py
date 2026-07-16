from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.entities.permission import Permission


class PermissionRepository(ABC):
    @abstractmethod
    async def add(self, permission: Permission) -> None: ...

    @abstractmethod
    async def get_by_id(self, permission_id: uuid.UUID) -> Permission | None: ...

    @abstractmethod
    async def get_by_code(self, code: str) -> Permission | None: ...

    @abstractmethod
    async def list(self) -> list[Permission]: ...
