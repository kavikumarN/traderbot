from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.notification.enums import NotificationChannel, NotificationSeverity


@dataclass(slots=True)
class Notification:
    id: uuid.UUID
    user_id: uuid.UUID
    channel: NotificationChannel
    severity: NotificationSeverity
    title: str
    message: str
    is_read: bool
    created_at: datetime
    read_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark_read(self, now: datetime) -> None:
        self.is_read = True
        self.read_at = now
