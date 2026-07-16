from __future__ import annotations

from app.application.services.news_feed_registry import NewsFeedInfo
from app.domain.news.entities import NewsArticle
from app.interface.api.schemas.news import NewsArticleResponse, NewsFeedResponse


def news_feed_to_response(feed: NewsFeedInfo) -> NewsFeedResponse:
    return NewsFeedResponse(id=feed.id, name=feed.name)


def news_article_to_response(article: NewsArticle) -> NewsArticleResponse:
    return NewsArticleResponse(
        title=article.title,
        url=article.url,
        source_id=article.source_id,
        source_name=article.source_name,
        summary=article.summary,
        published_at=article.published_at,
        impact=article.impact.value,
        tags=article.tags,
        symbols=article.symbols,
    )
