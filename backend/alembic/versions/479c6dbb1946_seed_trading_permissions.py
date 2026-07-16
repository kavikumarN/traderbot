"""seed trading permissions

Revision ID: 479c6dbb1946
Revises: 4eea660daade
Create Date: 2026-07-10 00:00:00.000000
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "479c6dbb1946"
down_revision: Union[str, None] = "4eea660daade"
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
    ("trading:read", "View orders, order history, order status, and trading audit logs"),
    ("trading:write", "Place, cancel, and sync orders"),
]

# "trader" needs both to actually use the trading engine; "viewer" gets
# read-only visibility, matching its existing read-only role elsewhere.
# "admin" is granted every permission that exists, so it needs these two
# added explicitly here rather than relying on 577603bf8426's now-already-run
# "every permission" computation.
ROLE_GRANTS = {
    "admin": {"trading:read", "trading:write"},
    "trader": {"trading:read", "trading:write"},
    "viewer": {"trading:read"},
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
