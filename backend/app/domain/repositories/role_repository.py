from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.entities.role import Role


class RoleRepository(ABC):
    @abstractmethod
    async def add(self, role: Role) -> None: ...

    @abstractmethod
    async def get_by_id(self, role_id: uuid.UUID) -> Role | None: ...

    @abstractmethod
    async def get_by_name(self, name: str) -> Role | None: ...

    @abstractmethod
    async def list(self) -> list[Role]: ...

    @abstractmethod
    async def update(self, role: Role) -> None: ...

    @abstractmethod
    async def get_permission_codes_for_roles(self, role_names: set[str]) -> set[str]:
        """Union of permission codes granted by any of the given roles."""
        ...
