from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.application.use_cases.roles.create_role import CreateRoleCommand, CreateRoleUseCase
from app.application.use_cases.roles.list_permissions import ListPermissionsUseCase
from app.application.use_cases.roles.list_roles import ListRolesUseCase
from app.application.use_cases.roles.manage_role_permissions import (
    GrantPermissionCommand,
    GrantPermissionUseCase,
    RevokePermissionCommand,
    RevokePermissionUseCase,
)
from app.interface.api.deps import (
    get_create_role_use_case,
    get_grant_permission_use_case,
    get_list_permissions_use_case,
    get_list_roles_use_case,
    get_revoke_permission_use_case,
    require_permission,
)
from app.interface.api.mappers import permission_to_response, role_to_response
from app.interface.api.schemas.role import (
    CreateRoleRequest,
    GrantPermissionRequest,
    PermissionResponse,
    RoleResponse,
)

router = APIRouter(prefix="/roles", tags=["roles"])
permissions_router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get(
    "",
    response_model=list[RoleResponse],
    dependencies=[Depends(require_permission("roles:read"))],
    summary="List roles",
)
async def list_roles(use_case: ListRolesUseCase = Depends(get_list_roles_use_case)) -> list[RoleResponse]:
    roles = await use_case.execute()
    return [role_to_response(role) for role in roles]


@router.post(
    "",
    response_model=RoleResponse,
    status_code=201,
    dependencies=[Depends(require_permission("roles:manage"))],
    summary="Create a role",
)
async def create_role(
    body: CreateRoleRequest, use_case: CreateRoleUseCase = Depends(get_create_role_use_case)
) -> RoleResponse:
    role = await use_case.execute(CreateRoleCommand(name=body.name, description=body.description))
    return role_to_response(role)


@router.post(
    "/{role_id}/permissions",
    response_model=RoleResponse,
    dependencies=[Depends(require_permission("roles:manage"))],
    summary="Grant a permission to a role",
)
async def grant_permission(
    role_id: uuid.UUID,
    body: GrantPermissionRequest,
    use_case: GrantPermissionUseCase = Depends(get_grant_permission_use_case),
) -> RoleResponse:
    role = await use_case.execute(
        GrantPermissionCommand(role_id=role_id, permission_code=body.permission_code)
    )
    return role_to_response(role)


@router.delete(
    "/{role_id}/permissions/{permission_code}",
    response_model=RoleResponse,
    dependencies=[Depends(require_permission("roles:manage"))],
    summary="Revoke a permission from a role",
)
async def revoke_permission(
    role_id: uuid.UUID,
    permission_code: str,
    use_case: RevokePermissionUseCase = Depends(get_revoke_permission_use_case),
) -> RoleResponse:
    role = await use_case.execute(
        RevokePermissionCommand(role_id=role_id, permission_code=permission_code)
    )
    return role_to_response(role)


@permissions_router.get(
    "",
    response_model=list[PermissionResponse],
    dependencies=[Depends(require_permission("permissions:read"))],
    summary="List the permission catalog",
)
async def list_permissions(
    use_case: ListPermissionsUseCase = Depends(get_list_permissions_use_case),
) -> list[PermissionResponse]:
    permissions = await use_case.execute()
    return [permission_to_response(permission) for permission in permissions]
