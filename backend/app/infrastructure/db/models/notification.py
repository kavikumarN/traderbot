"""Notification bounded context. Mirrors `app.domain.notification.entities`."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.notification.enums import NotificationChannel, NotificationSeverity
from app.infrastructure.db.base import Base
from app.infrastructure.db.types import portable_enum


class NotificationModel(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id_is_read_created_at", "user_id", "is_read", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[NotificationChannel] = mapped_column(portable_enum(NotificationChannel), nullable=False)
    severity: Mapped[NotificationSeverity] = mapped_column(portable_enum(NotificationSeverity), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Mapped as `metadata_` because `metadata` is reserved on every
    # Declarative model (`Base.metadata`); the DB column itself is still
    # named `metadata`.
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
