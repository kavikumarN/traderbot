"""seed risk permissions

Revision ID: c4a2e8f91b3d
Revises: b3f1a9c7d2e5
Create Date: 2026-07-13 09:05:00.000000
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4a2e8f91b3d"
down_revision: Union[str, None] = "b3f1a9c7d2e5"
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
    ("risk:read", "View risk rules, the risk dashboard, and position-size previews"),
    ("risk:write", "Create/update/delete risk rules and trigger emergency stop / circuit breaker resets"),
]

# Same split as 8f3b6a1c2d4e: "trader" gets both (a trader manages their own
# risk limits), "viewer" gets read-only, "admin" is granted every
# permission that exists but needs these two added explicitly for the same
# reason documented there.
ROLE_GRANTS = {
    "admin": {"risk:read", "risk:write"},
    "trader": {"risk:read", "risk:write"},
    "viewer": {"risk:read"},
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
