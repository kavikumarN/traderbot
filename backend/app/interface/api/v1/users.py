from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.application.use_cases.roles.assign_role_to_user import (
    AssignRoleToUserCommand,
    AssignRoleToUserUseCase,
    RevokeRoleFromUserCommand,
    RevokeRoleFromUserUseCase,
)
from app.application.use_cases.users.get_user import GetUserUseCase
from app.application.use_cases.users.list_users import ListUsersQuery, ListUsersUseCase
from app.application.use_cases.users.set_user_active import SetUserActiveCommand, SetUserActiveUseCase
from app.interface.api.deps import (
    get_assign_role_to_user_use_case,
    get_get_user_use_case,
    get_list_users_use_case,
    get_revoke_role_from_user_use_case,
    get_set_user_active_use_case,
    require_permission,
)
from app.interface.api.mappers import user_to_response
from app.interface.api.schemas.user import AssignRoleRequest, SetUserActiveRequest, UserListResponse, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    response_model=UserListResponse,
    dependencies=[Depends(require_permission("users:read"))],
    summary="List users",
)
async def list_users(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    use_case: ListUsersUseCase = Depends(get_list_users_use_case),
) -> UserListResponse:
    users, total = await use_case.execute(ListUsersQuery(offset=offset, limit=limit))
    return UserListResponse(
        items=[user_to_response(user) for user in users], total=total, offset=offset, limit=limit
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_permission("users:read"))],
    summary="Get a user by id",
)
async def get_user(
    user_id: uuid.UUID, use_case: GetUserUseCase = Depends(get_get_user_use_case)
) -> UserResponse:
    user = await use_case.execute(user_id)
    return user_to_response(user)


@router.patch(
    "/{user_id}/status",
    response_model=UserResponse,
    dependencies=[Depends(require_permission("users:write"))],
    summary="Activate or deactivate a user",
)
async def set_user_active(
    user_id: uuid.UUID,
    body: SetUserActiveRequest,
    use_case: SetUserActiveUseCase = Depends(get_set_user_active_use_case),
) -> UserResponse:
    user = await use_case.execute(SetUserActiveCommand(user_id=user_id, is_active=body.is_active))
    return user_to_response(user)


@router.post(
    "/{user_id}/roles",
    response_model=UserResponse,
    dependencies=[Depends(require_permission("roles:manage"))],
    summary="Assign a role to a user",
)
async def assign_role(
    user_id: uuid.UUID,
    body: AssignRoleRequest,
    use_case: AssignRoleToUserUseCase = Depends(get_assign_role_to_user_use_case),
) -> UserResponse:
    user = await use_case.execute(AssignRoleToUserCommand(user_id=user_id, role_name=body.role_name))
    return user_to_response(user)


@router.delete(
    "/{user_id}/roles/{role_name}",
    response_model=UserResponse,
    dependencies=[Depends(require_permission("roles:manage"))],
    status_code=status.HTTP_200_OK,
    summary="Revoke a role from a user",
)
async def revoke_role(
    user_id: uuid.UUID,
    role_name: str,
    use_case: RevokeRoleFromUserUseCase = Depends(get_revoke_role_from_user_use_case),
) -> UserResponse:
    user = await use_case.execute(RevokeRoleFromUserCommand(user_id=user_id, role_name=role_name))
    return user_to_response(user)
