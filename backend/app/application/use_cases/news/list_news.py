"""Lists market-moving news, either from one configured feed or aggregated
across all of them. Caches each feed's parsed articles in-process for
`_CACHE_TTL_SECONDS` — RSS feeds don't change fast enough to justify a
live fetch on every request, and the backend already runs as a single
long-lived process (see `DEPLOYMENT.md`'s note on why it's capped at one
replica), so an in-memory cache needs no coordination with any other
instance.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from app.application.ports.news_feed_client import INewsFeedClient
from app.application.services.news_feed_registry import NEWS_FEEDS, NewsFeedInfo, get_feed
from app.domain.exceptions import EntityNotFoundError
from app.domain.news.entities import NewsArticle
from app.domain.news.feed_parser import parse_feed

_CACHE_TTL_SECONDS = 300
_DEFAULT_LIMIT = 40


@dataclass(frozen=True, slots=True)
class ListNewsCommand:
    feed_id: str | None  # None = aggregate every configured feed
    limit: int = _DEFAULT_LIMIT


class ListNewsUseCase:
    """A process-wide singleton (see `deps.get_list_news_use_case`) — the
    cache lives on the instance itself, not per-request."""

    def __init__(self, feed_client: INewsFeedClient) -> None:
        self._feed_client = feed_client
        self._cache: dict[str, tuple[float, list[NewsArticle]]] = {}
        self._locks: dict[str, asyncio.Lock] = {feed.id: asyncio.Lock() for feed in NEWS_FEEDS}

    def list_feeds(self) -> tuple[NewsFeedInfo, ...]:
        return NEWS_FEEDS

    async def execute(self, command: ListNewsCommand) -> list[NewsArticle]:
        if command.feed_id is None:
            results = await asyncio.gather(*(self._get_feed_articles(feed) for feed in NEWS_FEEDS))
            articles = [article for feed_articles in results for article in feed_articles]
        else:
            feed = get_feed(command.feed_id)
            if feed is None:
                raise EntityNotFoundError("NewsFeed", command.feed_id)
            articles = await self._get_feed_articles(feed)

        articles.sort(key=lambda a: a.published_at, reverse=True)
        return articles[: command.limit]

    async def _get_feed_articles(self, feed: NewsFeedInfo) -> list[NewsArticle]:
        cached = self._cache.get(feed.id)
        if cached is not None and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]

        async with self._locks[feed.id]:
            # Re-check after acquiring the lock — a concurrent request may
            # have already refreshed this feed while this one waited on it.
            cached = self._cache.get(feed.id)
            if cached is not None and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
                return cached[1]

            try:
                xml_text = await self._feed_client.fetch(feed.url)
                articles = parse_feed(xml_text, source_id=feed.id, source_name=feed.name)
            except Exception:
                # A single dead/renamed/unreachable feed shouldn't break the
                # whole aggregated view — fall back to whatever was last
                # cached (even if stale), or an empty list on a cold cache.
                articles = cached[1] if cached is not None else []

            self._cache[feed.id] = (time.monotonic(), articles)
            return articles
