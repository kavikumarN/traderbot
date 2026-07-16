from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    is_active: bool
    is_verified: bool
    role_names: list[str]
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    offset: int
    limit: int


class SetUserActiveRequest(BaseModel):
    is_active: bool


class AssignRoleRequest(BaseModel):
    role_name: str = Field(min_length=1, max_length=50)
