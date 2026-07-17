"""Risk bounded context. Mirrors `app.domain.risk.entities.RiskRule` and
`app.domain.risk.entities.RiskState`."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.risk.enums import CircuitBreakerState, RiskRuleType
from app.infrastructure.db.base import Base
from app.infrastructure.db.types import portable_enum


class RiskRuleModel(Base):
    __tablename__ = "risk_rules"
    __table_args__ = (
        Index("ix_risk_rules_user_id_is_active", "user_id", "is_active"),
        Index("ix_risk_rules_strategy_id_is_active", "strategy_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("strategies.id", ondelete="CASCADE"), nullable=True
    )
    rule_type: Mapped[RiskRuleType] = mapped_column(portable_enum(RiskRuleType), nullable=False)
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(36, 18), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RiskStateModel(Base):
    __tablename__ = "risk_states"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    circuit_breaker: Mapped[CircuitBreakerState] = mapped_column(
        portable_enum(CircuitBreakerState), nullable=False, default=CircuitBreakerState.CLOSED
    )
    circuit_breaker_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    circuit_breaker_tripped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    circuit_breaker_resume_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    emergency_stop: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    emergency_stop_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    emergency_stop_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_loss: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False, default=Decimal(0))
    daily_loss_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    equity_peak: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False, default=Decimal(0))
    de_risked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    de_risk_multiplier: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False, default=Decimal(1))
    de_risk_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    de_risked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
