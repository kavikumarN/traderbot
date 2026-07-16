"""seed default roles and permissions

Revision ID: 577603bf8426
Revises: 04251e479d5d
Create Date: 2026-07-08 01:06:48.790759
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "577603bf8426"
down_revision: Union[str, None] = "04251e479d5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Raw table handles — deliberately not imported from app.infrastructure.db.models.
# Migrations must stay correct forever, even after the ORM models they were
# generated from have since changed shape.
permissions_table = sa.table(
    "permissions", sa.column("id", PGUUID(as_uuid=True)), sa.column("code", sa.String), sa.column("description", sa.String)
)
roles_table = sa.table(
    "roles", sa.column("id", PGUUID(as_uuid=True)), sa.column("name", sa.String), sa.column("description", sa.String)
)
role_permissions_table = sa.table(
    "role_permissions",
    sa.column("role_id", PGUUID(as_uuid=True)),
    sa.column("permission_id", PGUUID(as_uuid=True)),
)

PERMISSIONS = [
    ("users:read", "View user accounts"),
    ("users:write", "Activate/deactivate user accounts"),
    ("roles:read", "View roles and the permission catalog"),
    ("roles:manage", "Create roles and grant/revoke permissions and role assignments"),
    ("permissions:read", "View the permission catalog"),
]

ROLES = {
    "admin": ("Full administrative access", {code for code, _ in PERMISSIONS}),
    "viewer": ("Read-only access to users, roles, and permissions", {"users:read", "roles:read", "permissions:read"}),
    "trader": ("Default role granted on self-registration", set()),
}


def upgrade() -> None:
    permission_ids: dict[str, uuid.UUID] = {code: uuid.uuid4() for code, _ in PERMISSIONS}

    op.bulk_insert(
        permissions_table,
        [
            {"id": permission_ids[code], "code": code, "description": description}
            for code, description in PERMISSIONS
        ],
    )

    role_ids: dict[str, uuid.UUID] = {name: uuid.uuid4() for name in ROLES}
    op.bulk_insert(
        roles_table,
        [
            {"id": role_ids[name], "name": name, "description": description}
            for name, (description, _codes) in ROLES.items()
        ],
    )

    role_permission_rows = [
        {"role_id": role_ids[name], "permission_id": permission_ids[code]}
        for name, (_description, codes) in ROLES.items()
        for code in codes
    ]
    if role_permission_rows:
        op.bulk_insert(role_permissions_table, role_permission_rows)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        roles_table.delete().where(roles_table.c.name.in_(list(ROLES.keys())))
    )
    conn.execute(
        permissions_table.delete().where(
            permissions_table.c.code.in_([code for code, _ in PERMISSIONS])
        )
    )
