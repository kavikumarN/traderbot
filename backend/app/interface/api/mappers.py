"""Domain entity -> API response model mapping, kept in one place so every
route returns a consistently-shaped payload."""

from __future__ import annotations

from app.domain.entities.permission import Permission
from app.domain.entities.role import Role
from app.domain.entities.user import User
from app.interface.api.schemas.role import PermissionResponse, RoleResponse
from app.interface.api.schemas.user import UserResponse


def user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=str(user.email),
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        role_names=sorted(user.role_names),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def role_to_response(role: Role) -> RoleResponse:
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        permission_codes=sorted(role.permission_codes),
    )


def permission_to_response(permission: Permission) -> PermissionResponse:
    return PermissionResponse(id=permission.id, code=permission.code, description=permission.description)
