"""Request/response models for the Insights news tab
(`GET /insights/news`, `GET /insights/news/feeds`)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NewsFeedResponse(BaseModel):
    id: str
    name: str


class NewsArticleResponse(BaseModel):
    title: str
    url: str
    source_id: str
    source_name: str
    summary: str
    published_at: datetime
    impact: str
    tags: list[str]
    symbols: list[str]
