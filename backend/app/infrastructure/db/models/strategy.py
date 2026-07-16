"""Strategy bounded context: strategies, their generated signals, and
backtest runs. Mirrors `app.domain.strategy.entities`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.exchange.enums import OrderSide
from app.domain.strategy.enums import BacktestStatus, SignalStatus, StrategyStatus
from app.infrastructure.db.base import Base
from app.infrastructure.db.types import portable_enum

_AMOUNT = Numeric(36, 18)


class StrategyModel(Base):
    __tablename__ = "strategies"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[StrategyStatus] = mapped_column(
        portable_enum(StrategyStatus), nullable=False, default=StrategyStatus.DRAFT, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SignalModel(Base):
    __tablename__ = "signals"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[OrderSide] = mapped_column(portable_enum(OrderSide), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(_AMOUNT, nullable=False)
    target_price: Mapped[Decimal | None] = mapped_column(_AMOUNT, nullable=True)
    status: Mapped[SignalStatus] = mapped_column(
        portable_enum(SignalStatus), nullable=False, default=SignalStatus.PENDING, index=True
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class BacktestModel(Base):
    __tablename__ = "backtests"
    # `Base`'s naming convention already prefixes check constraints with
    # `ck_<table_name>_`; passing the full name here would double it.
    __table_args__ = (CheckConstraint("period_end > period_start", name="period_end_after_start"),)

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[BacktestStatus] = mapped_column(
        portable_enum(BacktestStatus), nullable=False, default=BacktestStatus.PENDING, index=True
    )
    initial_balance: Mapped[Decimal] = mapped_column(_AMOUNT, nullable=False)
    final_balance: Mapped[Decimal | None] = mapped_column(_AMOUNT, nullable=True)
    sharpe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    max_drawdown: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    win_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    total_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    results: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
