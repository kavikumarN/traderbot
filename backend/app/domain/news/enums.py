from __future__ import annotations

from enum import StrEnum


class ImpactLevel(StrEnum):
    """A rough "how much should a trader care" read on a headline, derived
    from keyword matching in `app.domain.news.impact_scoring` — not a
    substitute for real sentiment analysis, but enough to separate routine
    coverage from headlines that plausibly move a market."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
