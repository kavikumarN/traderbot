"""Audit bounded context — an append-only record of everything that
happened, for compliance and incident review. Deliberately has no
`update`/`delete` in its repository port (see `repositories.py`): an audit
trail that can be edited after the fact isn't one."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class AuditLog:
    id: uuid.UUID
    event_type: str
    entity_type: str
    occurred_at: datetime
    entity_id: uuid.UUID | None = None
    actor_user_id: uuid.UUID | None = None
    payload: dict[str, Any] = field(default_factory=dict)
