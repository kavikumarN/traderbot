from __future__ import annotations

from app.domain.news.enums import ImpactLevel
from app.domain.news.feed_parser import parse_feed

_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Crypto News</title>
    <item>
      <title>Exchange hacked, millions stolen</title>
      <link>https://example.com/hack</link>
      <description>&lt;p&gt;A major &lt;b&gt;Bitcoin&lt;/b&gt; exchange was hacked overnight.&lt;/p&gt;</description>
      <pubDate>Wed, 01 Jan 2025 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Weekly recap</title>
      <link>https://example.com/recap</link>
      <description>A quiet week overall.</description>
      <pubDate>Tue, 31 Dec 2024 09:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Missing link is skipped</title>
      <description>No link element here.</description>
      <pubDate>Mon, 30 Dec 2024 09:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Atom Feed</title>
  <entry>
    <title>Ethereum partnership announced</title>
    <link href="https://example.com/atom-entry" />
    <summary>A new partnership was announced today.</summary>
    <updated>2025-01-01T12:00:00Z</updated>
  </entry>
</feed>
"""


class TestParseFeed:
    def test_parses_rss_items_and_skips_incomplete_ones(self) -> None:
        articles = parse_feed(_RSS_XML, source_id="example", source_name="Example")

        assert len(articles) == 2
        assert articles[0].title == "Exchange hacked, millions stolen"
        assert articles[0].url == "https://example.com/hack"
        assert articles[0].source_id == "example"
        assert articles[0].source_name == "Example"
        assert "hacked" in articles[0].summary.lower()
        assert "<b>" not in articles[0].summary
        assert articles[0].impact == ImpactLevel.HIGH
        assert "BTC" in articles[0].symbols

    def test_second_rss_item_is_low_impact(self) -> None:
        articles = parse_feed(_RSS_XML, source_id="example", source_name="Example")
        assert articles[1].title == "Weekly recap"
        assert articles[1].impact == ImpactLevel.LOW

    def test_parses_atom_entries(self) -> None:
        articles = parse_feed(_ATOM_XML, source_id="atom-example", source_name="Atom Example")

        assert len(articles) == 1
        assert articles[0].title == "Ethereum partnership announced"
        assert articles[0].url == "https://example.com/atom-entry"
        assert articles[0].impact == ImpactLevel.MEDIUM
        assert "ETH" in articles[0].symbols

    def test_malformed_xml_returns_empty_list(self) -> None:
        assert parse_feed("<rss><channel><item><title>unterminated", source_id="x", source_name="X") == []

    def test_empty_string_returns_empty_list(self) -> None:
        assert parse_feed("", source_id="x", source_name="X") == []
