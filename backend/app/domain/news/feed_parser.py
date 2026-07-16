"""RSS 2.0 / Atom feed parsing, hand-rolled on top of the stdlib's
`xml.etree.ElementTree` rather than pulling in a feed-parsing dependency —
both formats reduce to "a flat list of items with a title/link/summary/
published date" once XML namespaces are stripped, which is all a news tab
needs.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from app.domain.news.entities import NewsArticle
from app.domain.news.impact_scoring import score_article

_TAG_RE = re.compile(r"<[^>]+>")
_SUMMARY_MAX_LENGTH = 320


def parse_feed(xml_text: str, *, source_id: str, source_name: str) -> list[NewsArticle]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    _strip_namespaces(root)

    if root.find("channel") is not None:
        return _parse_rss(root, source_id=source_id, source_name=source_name)
    return _parse_atom(root, source_id=source_id, source_name=source_name)


def _strip_namespaces(root: ET.Element) -> None:
    for elem in root.iter():
        if "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]


def _parse_rss(root: ET.Element, *, source_id: str, source_name: str) -> list[NewsArticle]:
    channel = root.find("channel")
    if channel is None:
        return []

    articles: list[NewsArticle] = []
    for item in channel.findall("item"):
        title = _clean_text(item.findtext("title"))
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        summary = _clean_text(item.findtext("description") or item.findtext("summary"))
        published_at = _parse_date(item.findtext("pubDate"))
        article = _build_article(title, link, summary, published_at, source_id=source_id, source_name=source_name)
        articles.append(article)
    return articles


def _parse_atom(root: ET.Element, *, source_id: str, source_name: str) -> list[NewsArticle]:
    articles: list[NewsArticle] = []
    for entry in root.findall("entry"):
        title = _clean_text(entry.findtext("title"))
        link_elem = entry.find("link")
        link = (link_elem.get("href") if link_elem is not None else "") or ""
        link = link.strip()
        if not title or not link:
            continue
        summary = _clean_text(entry.findtext("summary") or entry.findtext("content"))
        published_at = _parse_date(entry.findtext("published") or entry.findtext("updated"))
        article = _build_article(title, link, summary, published_at, source_id=source_id, source_name=source_name)
        articles.append(article)
    return articles


def _build_article(
    title: str, link: str, summary: str, published_at: datetime, *, source_id: str, source_name: str
) -> NewsArticle:
    impact, tags, symbols = score_article(title, summary)
    return NewsArticle(
        title=title,
        url=link,
        source_id=source_id,
        source_name=source_name,
        summary=summary[:_SUMMARY_MAX_LENGTH],
        published_at=published_at,
        impact=impact,
        tags=tags,
        symbols=symbols,
    )


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return _TAG_RE.sub("", value).strip()


def _parse_date(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    value = value.strip()
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)
