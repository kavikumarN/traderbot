"""The set of public RSS feeds the Insights news tab aggregates. Static and
in-code rather than DB-configurable — swapping/adding a feed is a code
change, which is fine for a fixed, curated list of major crypto news
outlets (none of these need credentials, unlike a paid news API)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NewsFeedInfo:
    id: str
    name: str
    url: str


NEWS_FEEDS: tuple[NewsFeedInfo, ...] = (
    NewsFeedInfo(id="coindesk", name="CoinDesk", url="https://www.coindesk.com/arc/outboundfeeds/rss/"),
    NewsFeedInfo(id="cointelegraph", name="Cointelegraph", url="https://cointelegraph.com/rss"),
    NewsFeedInfo(id="decrypt", name="Decrypt", url="https://decrypt.co/feed"),
    NewsFeedInfo(id="bitcoinmagazine", name="Bitcoin Magazine", url="https://bitcoinmagazine.com/feed"),
    NewsFeedInfo(id="theblock", name="The Block", url="https://www.theblock.co/rss.xml"),
)


def get_feed(feed_id: str) -> NewsFeedInfo | None:
    return next((feed for feed in NEWS_FEEDS if feed.id == feed_id), None)
