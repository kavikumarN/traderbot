from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class PermissionResponse(BaseModel):
    id: uuid.UUID
    code: str
    description: str


class RoleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    permission_codes: list[str]


class CreateRoleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str = Field(default="", max_length=255)


class GrantPermissionRequest(BaseModel):
    permission_code: str = Field(min_length=1, max_length=100)
