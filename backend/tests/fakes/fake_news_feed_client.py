"""Scriptable fake `INewsFeedClient` — set `.responses[url]` to the raw XML
a fetch should return, or add a url to `.raise_for` to simulate a dead feed.
"""

from __future__ import annotations

from app.application.ports.news_feed_client import INewsFeedClient


class FakeNewsFeedClient(INewsFeedClient):
    def __init__(self) -> None:
        self.responses: dict[str, str] = {}
        self.fetch_calls: list[str] = []
        self.raise_for: set[str] = set()

    async def fetch(self, url: str) -> str:
        self.fetch_calls.append(url)
        if url in self.raise_for:
            raise ConnectionError("feed unreachable")
        return self.responses.get(url, "")
