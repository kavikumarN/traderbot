"""seed strategy permissions

Revision ID: 8f3b6a1c2d4e
Revises: 479c6dbb1946
Create Date: 2026-07-10 13:30:00.000000
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f3b6a1c2d4e"
down_revision: Union[str, None] = "479c6dbb1946"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Raw table handles — see 577603bf8426's own note on why these aren't
# imported from app.infrastructure.db.models: migrations must stay correct
# forever, independent of how the ORM models they were generated from
# later evolve.
permissions_table = sa.table(
    "permissions", sa.column("id", PGUUID(as_uuid=True)), sa.column("code", sa.String), sa.column("description", sa.String)
)
roles_table = sa.table("roles", sa.column("id", PGUUID(as_uuid=True)), sa.column("name", sa.String))
role_permissions_table = sa.table(
    "role_permissions",
    sa.column("role_id", PGUUID(as_uuid=True)),
    sa.column("permission_id", PGUUID(as_uuid=True)),
)

PERMISSIONS = [
    ("strategies:read", "View strategies and their generated signals"),
    ("strategies:write", "Create strategies and change their lifecycle status"),
]

# Same split as 479c6dbb1946: "trader" gets both (they run strategies),
# "viewer" gets read-only, "admin" is granted every permission that exists
# but needs these two added explicitly for the same reason documented there.
ROLE_GRANTS = {
    "admin": {"strategies:read", "strategies:write"},
    "trader": {"strategies:read", "strategies:write"},
    "viewer": {"strategies:read"},
}


def upgrade() -> None:
    conn = op.get_bind()

    permission_ids: dict[str, uuid.UUID] = {code: uuid.uuid4() for code, _ in PERMISSIONS}
    op.bulk_insert(
        permissions_table,
        [
            {"id": permission_ids[code], "code": code, "description": description}
            for code, description in PERMISSIONS
        ],
    )

    existing_roles = conn.execute(sa.select(roles_table.c.id, roles_table.c.name)).fetchall()
    role_ids: dict[str, uuid.UUID] = {row.name: row.id for row in existing_roles}

    role_permission_rows = [
        {"role_id": role_ids[role_name], "permission_id": permission_ids[code]}
        for role_name, codes in ROLE_GRANTS.items()
        if role_name in role_ids
        for code in codes
    ]
    if role_permission_rows:
        op.bulk_insert(role_permissions_table, role_permission_rows)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        permissions_table.delete().where(permissions_table.c.code.in_([code for code, _ in PERMISSIONS]))
    )
