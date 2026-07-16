"""Fetches a feed's raw XML body over HTTP. Most public news RSS feeds
reject requests with no `User-Agent` (treating them as bot traffic), so one
is set explicitly here — this is the one thing worth getting wrong quietly
otherwise.
"""

from __future__ import annotations

import httpx

from app.application.ports.news_feed_client import INewsFeedClient

_TIMEOUT_SECONDS = 8.0
_USER_AGENT = "traderbot-insights/1.0 (+https://github.com/)"


class HttpxNewsFeedClient(INewsFeedClient):
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def fetch(self, url: str) -> str:
        headers = {"User-Agent": _USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml"}
        if self._client is not None:
            response = await self._client.get(url, headers=headers, timeout=_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.text

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=_TIMEOUT_SECONDS, follow_redirects=True)
            response.raise_for_status()
            return response.text
