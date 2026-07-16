from __future__ import annotations

import pytest

from app.application.services.news_feed_registry import NEWS_FEEDS
from app.application.use_cases.news.list_news import ListNewsCommand, ListNewsUseCase
from app.domain.exceptions import EntityNotFoundError
from tests.fakes.fake_news_feed_client import FakeNewsFeedClient

pytestmark = pytest.mark.asyncio

_RSS_TEMPLATE = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>{title}</title>
      <link>{link}</link>
      <description>a headline</description>
      <pubDate>{pub_date}</pubDate>
    </item>
  </channel>
</rss>
"""


def _feed_xml(title: str, pub_date: str = "Wed, 01 Jan 2025 12:00:00 GMT") -> str:
    return _RSS_TEMPLATE.format(title=title, link=f"https://example.com/{title}", pub_date=pub_date)


async def test_lists_a_single_configured_feed() -> None:
    client = FakeNewsFeedClient()
    feed = NEWS_FEEDS[0]
    client.responses[feed.url] = _feed_xml("hello")
    use_case = ListNewsUseCase(client)

    articles = await use_case.execute(ListNewsCommand(feed_id=feed.id))

    assert len(articles) == 1
    assert articles[0].source_id == feed.id
    assert client.fetch_calls == [feed.url]


async def test_unknown_feed_id_raises_not_found() -> None:
    use_case = ListNewsUseCase(FakeNewsFeedClient())
    with pytest.raises(EntityNotFoundError):
        await use_case.execute(ListNewsCommand(feed_id="not-a-real-feed"))


async def test_aggregates_every_feed_when_no_feed_id_given() -> None:
    client = FakeNewsFeedClient()
    for feed in NEWS_FEEDS:
        client.responses[feed.url] = _feed_xml(f"headline-{feed.id}")
    use_case = ListNewsUseCase(client)

    articles = await use_case.execute(ListNewsCommand(feed_id=None))

    assert len(articles) == len(NEWS_FEEDS)
    assert {a.source_id for a in articles} == {f.id for f in NEWS_FEEDS}


async def test_sorts_by_published_at_descending() -> None:
    client = FakeNewsFeedClient()
    feed = NEWS_FEEDS[0]
    client.responses[feed.url] = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><title>older</title><link>https://example.com/older</link>
    <pubDate>Mon, 30 Dec 2024 09:00:00 GMT</pubDate></item>
  <item><title>newer</title><link>https://example.com/newer</link>
    <pubDate>Wed, 01 Jan 2025 12:00:00 GMT</pubDate></item>
</channel></rss>"""
    use_case = ListNewsUseCase(client)

    articles = await use_case.execute(ListNewsCommand(feed_id=feed.id))

    assert [a.title for a in articles] == ["newer", "older"]


async def test_respects_limit() -> None:
    client = FakeNewsFeedClient()
    for feed in NEWS_FEEDS:
        client.responses[feed.url] = _feed_xml(f"headline-{feed.id}")
    use_case = ListNewsUseCase(client)

    articles = await use_case.execute(ListNewsCommand(feed_id=None, limit=2))

    assert len(articles) == 2


async def test_caches_a_feed_between_calls() -> None:
    client = FakeNewsFeedClient()
    feed = NEWS_FEEDS[0]
    client.responses[feed.url] = _feed_xml("cached-headline")
    use_case = ListNewsUseCase(client)

    await use_case.execute(ListNewsCommand(feed_id=feed.id))
    await use_case.execute(ListNewsCommand(feed_id=feed.id))

    assert client.fetch_calls == [feed.url]  # second call served from cache, no second fetch


async def test_falls_back_to_empty_list_when_feed_fetch_fails() -> None:
    client = FakeNewsFeedClient()
    feed = NEWS_FEEDS[0]
    client.raise_for = {feed.url}
    use_case = ListNewsUseCase(client)

    articles = await use_case.execute(ListNewsCommand(feed_id=feed.id))

    assert articles == []


async def test_list_feeds_returns_the_full_registry() -> None:
    use_case = ListNewsUseCase(FakeNewsFeedClient())
    assert use_case.list_feeds() == NEWS_FEEDS
