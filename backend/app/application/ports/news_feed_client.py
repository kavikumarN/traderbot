from __future__ import annotations

from abc import ABC, abstractmethod


class INewsFeedClient(ABC):
    """Fetches a feed's raw body over HTTP. Narrow on purpose — parsing
    lives in `app.domain.news.feed_parser`, this only ever needs to know
    how to make an HTTP GET request."""

    @abstractmethod
    async def fetch(self, url: str) -> str: ...
