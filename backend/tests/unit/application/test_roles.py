from __future__ import annotations

import uuid

import pytest

from app.application.use_cases.roles.assign_role_to_user import (
    AssignRoleToUserCommand,
    AssignRoleToUserUseCase,
    RevokeRoleFromUserCommand,
    RevokeRoleFromUserUseCase,
)
from app.application.use_cases.roles.create_role import CreateRoleCommand, CreateRoleUseCase
from app.application.use_cases.roles.manage_role_permissions import (
    GrantPermissionCommand,
    GrantPermissionUseCase,
    RevokePermissionCommand,
    RevokePermissionUseCase,
)
from app.application.use_cases.roles.resolve_user_permissions import ResolveUserPermissionsUseCase
from app.domain.entities.permission import Permission
from app.domain.exceptions import EntityAlreadyExistsError, EntityNotFoundError
from tests.unit.application.helpers import seed_user


@pytest.mark.asyncio
async def test_create_role_rejects_duplicate_name(uow_factory) -> None:
    use_case = CreateRoleUseCase(uow_factory)
    await use_case.execute(CreateRoleCommand(name="ops", description="Operations"))

    with pytest.raises(EntityAlreadyExistsError):
        await use_case.execute(CreateRoleCommand(name="ops", description="Operations, again"))


@pytest.mark.asyncio
async def test_grant_permission_requires_existing_role_and_permission(uow, uow_factory) -> None:
    role = await CreateRoleUseCase(uow_factory).execute(CreateRoleCommand(name="ops", description=""))
    use_case = GrantPermissionUseCase(uow_factory)

    with pytest.raises(EntityNotFoundError):
        await use_case.execute(GrantPermissionCommand(role_id=role.id, permission_code="users:read"))

    await uow.permissions.add(Permission(id=uuid.uuid4(), code="users:read", description=""))
    updated = await use_case.execute(
        GrantPermissionCommand(role_id=role.id, permission_code="users:read")
    )
    assert "users:read" in updated.permission_codes


@pytest.mark.asyncio
async def test_grant_then_revoke_permission(uow, uow_factory) -> None:
    role = await CreateRoleUseCase(uow_factory).execute(CreateRoleCommand(name="ops", description=""))
    await uow.permissions.add(Permission(id=uuid.uuid4(), code="users:read", description=""))
    await GrantPermissionUseCase(uow_factory).execute(
        GrantPermissionCommand(role_id=role.id, permission_code="users:read")
    )

    updated = await RevokePermissionUseCase(uow_factory).execute(
        RevokePermissionCommand(role_id=role.id, permission_code="users:read")
    )
    assert "users:read" not in updated.permission_codes


@pytest.mark.asyncio
async def test_assign_role_requires_existing_role(uow, uow_factory, password_hasher) -> None:
    user = await seed_user(uow, password_hasher)
    use_case = AssignRoleToUserUseCase(uow_factory)

    with pytest.raises(EntityNotFoundError):
        await use_case.execute(AssignRoleToUserCommand(user_id=user.id, role_name="admin"))

    await CreateRoleUseCase(uow_factory).execute(CreateRoleCommand(name="admin", description=""))
    updated = await use_case.execute(AssignRoleToUserCommand(user_id=user.id, role_name="admin"))
    assert updated.has_role("admin")


@pytest.mark.asyncio
async def test_revoke_role_from_user(uow, uow_factory, password_hasher) -> None:
    user = await seed_user(uow, password_hasher)
    await CreateRoleUseCase(uow_factory).execute(CreateRoleCommand(name="admin", description=""))
    await AssignRoleToUserUseCase(uow_factory).execute(
        AssignRoleToUserCommand(user_id=user.id, role_name="admin")
    )

    updated = await RevokeRoleFromUserUseCase(uow_factory).execute(
        RevokeRoleFromUserCommand(user_id=user.id, role_name="admin")
    )
    assert not updated.has_role("admin")


@pytest.mark.asyncio
async def test_resolve_user_permissions_unions_across_roles(uow, uow_factory) -> None:
    await uow.permissions.add(Permission(id=uuid.uuid4(), code="users:read", description=""))
    await uow.permissions.add(Permission(id=uuid.uuid4(), code="roles:manage", description=""))

    role_a = await CreateRoleUseCase(uow_factory).execute(CreateRoleCommand(name="reader", description=""))
    role_b = await CreateRoleUseCase(uow_factory).execute(CreateRoleCommand(name="manager", description=""))
    await GrantPermissionUseCase(uow_factory).execute(
        GrantPermissionCommand(role_id=role_a.id, permission_code="users:read")
    )
    await GrantPermissionUseCase(uow_factory).execute(
        GrantPermissionCommand(role_id=role_b.id, permission_code="roles:manage")
    )

    permissions = await ResolveUserPermissionsUseCase(uow_factory).execute({"reader", "manager"})

    assert permissions == {"users:read", "roles:manage"}


@pytest.mark.asyncio
async def test_resolve_user_permissions_empty_role_set(uow_factory) -> None:
    permissions = await ResolveUserPermissionsUseCase(uow_factory).execute(set())
    assert permissions == set()
