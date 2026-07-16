"""phase 8 risk engine schema

Revision ID: b3f1a9c7d2e5
Revises: 8f3b6a1c2d4e
Create Date: 2026-07-13 09:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3f1a9c7d2e5"
down_revision: Union[str, None] = "8f3b6a1c2d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # One row per user: the circuit-breaker/emergency-stop/daily-loss
    # runtime state `RiskEngine` reads and mutates on every order and every
    # fill (see `app.domain.risk.entities.RiskState`). `risk_rules` (the
    # static, composable rule specifications this state is evaluated
    # against) already exists as of e740ef33a2aa — this table is the
    # mutable counterpart the original Phase 4 schema deliberately left for
    # whichever phase actually built the evaluator.
    op.create_table(
        "risk_states",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "circuit_breaker",
            sa.Enum("CLOSED", "OPEN", name="circuitbreakerstate_enum", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("circuit_breaker_reason", sa.String(length=500), nullable=True),
        sa.Column("circuit_breaker_tripped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("circuit_breaker_resume_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("emergency_stop", sa.Boolean(), nullable=False),
        sa.Column("emergency_stop_reason", sa.String(length=500), nullable=True),
        sa.Column("emergency_stop_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_losses", sa.Integer(), nullable=False),
        sa.Column("daily_loss", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("daily_loss_date", sa.Date(), nullable=True),
        sa.Column("equity_peak", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_risk_states_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_states")),
        sa.UniqueConstraint("user_id", name=op.f("uq_risk_states_user_id")),
    )


def downgrade() -> None:
    op.drop_table("risk_states")
