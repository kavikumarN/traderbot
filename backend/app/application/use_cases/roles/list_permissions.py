from __future__ import annotations

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.entities.permission import Permission


class ListPermissionsUseCase:
    """Read-only: the permission catalog is seeded by migrations, not created via the API.

    A permission code is only meaningful if some endpoint actually checks
    for it (see ``require_permission`` in ``app.interface.api.deps``), so
    the catalog is developer-managed rather than admin-editable.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self) -> list[Permission]:
        async with self._uow_factory() as uow:
            return await uow.permissions.list()
