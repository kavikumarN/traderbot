"""add drawdown de-risk state

Revision ID: d1a4c7f2e6b8
Revises: 08984ea9d2c2
Create Date: 2026-07-17 12:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1a4c7f2e6b8"
down_revision: Union[str, None] = "08984ea9d2c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drawdown-based de-risking (FEATURES.md §1): a softer sibling of the
    # circuit breaker that scales `RiskEngine.suggest_position_size` down
    # instead of halting trading outright, and — unlike the breaker's
    # cooldown — never auto-clears; see `app.domain.risk.entities.RiskState`.
    op.add_column("risk_states", sa.Column("de_risked", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column(
        "risk_states",
        sa.Column("de_risk_multiplier", sa.Numeric(precision=36, scale=18), nullable=False, server_default="1"),
    )
    op.add_column("risk_states", sa.Column("de_risk_reason", sa.String(length=500), nullable=True))
    op.add_column("risk_states", sa.Column("de_risked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("risk_states", "de_risked_at")
    op.drop_column("risk_states", "de_risk_reason")
    op.drop_column("risk_states", "de_risk_multiplier")
    op.drop_column("risk_states", "de_risked")
