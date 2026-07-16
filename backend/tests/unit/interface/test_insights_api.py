from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.application.services.news_feed_registry import NEWS_FEEDS
from tests.fakes.fake_news_feed_client import FakeNewsFeedClient

pytestmark = pytest.mark.asyncio

_RSS_XML = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Exchange hacked overnight</title>
      <link>https://example.com/hack</link>
      <description>Bitcoin exchange suffers major breach.</description>
      <pubDate>Wed, 01 Jan 2025 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


async def _auth_headers(client: AsyncClient) -> dict[str, str]:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "insights@example.com", "password": "correcthorse1", "first_name": "A", "last_name": "B"},
    )
    response = await client.post(
        "/api/v1/auth/login", json={"email": "insights@example.com", "password": "correcthorse1"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_list_news_feeds_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/insights/news/feeds")
    assert response.status_code == 401


async def test_list_news_feeds_returns_the_registry(client: AsyncClient) -> None:
    headers = await _auth_headers(client)
    response = await client.get("/api/v1/insights/news/feeds", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert {f["id"] for f in body} == {f.id for f in NEWS_FEEDS}


async def test_list_news_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/insights/news")
    assert response.status_code == 401


async def test_list_news_returns_scored_articles_from_one_feed(
    client: AsyncClient, fake_news_feed_client: FakeNewsFeedClient
) -> None:
    headers = await _auth_headers(client)
    feed = NEWS_FEEDS[0]
    fake_news_feed_client.responses[feed.url] = _RSS_XML

    response = await client.get(f"/api/v1/insights/news?feed={feed.id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Exchange hacked overnight"
    assert body[0]["impact"] == "HIGH"
    assert "BTC" in body[0]["symbols"]
    assert body[0]["source_id"] == feed.id


async def test_list_news_unknown_feed_returns_404(client: AsyncClient) -> None:
    headers = await _auth_headers(client)
    response = await client.get("/api/v1/insights/news?feed=not-a-real-feed", headers=headers)
    assert response.status_code == 404


async def test_list_news_aggregates_all_feeds_by_default(
    client: AsyncClient, fake_news_feed_client: FakeNewsFeedClient
) -> None:
    headers = await _auth_headers(client)
    for feed in NEWS_FEEDS:
        fake_news_feed_client.responses[feed.url] = _RSS_XML

    response = await client.get("/api/v1/insights/news", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == len(NEWS_FEEDS)
