"""Resolve the effective permission set for a set of role names.

Used by the ``require_permission`` API dependency on every authenticated
request. Access tokens intentionally carry only role names (see
``app.application.ports.token_service``); permissions are looked up fresh
so revoking a permission from a role takes effect immediately instead of
waiting for the access token to expire.
"""

from __future__ import annotations

from app.application.ports.unit_of_work import UnitOfWorkFactory


class ResolveUserPermissionsUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, role_names: set[str]) -> set[str]:
        if not role_names:
            return set()
        async with self._uow_factory() as uow:
            return await uow.roles.get_permission_codes_for_roles(role_names)
