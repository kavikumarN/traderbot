from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.news.enums import ImpactLevel


@dataclass(frozen=True, slots=True)
class NewsArticle:
    title: str
    url: str
    source_id: str
    source_name: str
    summary: str
    published_at: datetime
    impact: ImpactLevel
    tags: list[str]
    symbols: list[str]
