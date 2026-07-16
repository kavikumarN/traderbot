"""Read-only market insights: the AI-detected-pattern chart lives under
`/strategies/ai-builder/analyze` (it's strategy-shaped — a symbol + a
suggested plugin config). This router is everything else in the Insights
tab that isn't: right now, the market-moving news feed.

Requires an authenticated session but no specific permission, same
reasoning as `v1/market.py` — there's no meaningful way to restrict "can
read the news" independent of "can use the platform at all".
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.application.use_cases.news.list_news import ListNewsCommand, ListNewsUseCase
from app.interface.api.deps import get_current_access_token_payload, get_list_news_use_case
from app.interface.api.news_mappers import news_article_to_response, news_feed_to_response
from app.interface.api.schemas.news import NewsArticleResponse, NewsFeedResponse

router = APIRouter(
    prefix="/insights",
    tags=["insights"],
    dependencies=[Depends(get_current_access_token_payload)],
)


@router.get("/news/feeds", response_model=list[NewsFeedResponse], summary="List available news feeds")
async def list_news_feeds(
    use_case: ListNewsUseCase = Depends(get_list_news_use_case),
) -> list[NewsFeedResponse]:
    return [news_feed_to_response(feed) for feed in use_case.list_feeds()]


@router.get("/news", response_model=list[NewsArticleResponse], summary="Market news, aggregated or per-feed")
async def list_news(
    feed: str | None = Query(default=None, description="A feed id from /insights/news/feeds, or omit for all"),
    limit: int = Query(default=40, ge=1, le=100),
    use_case: ListNewsUseCase = Depends(get_list_news_use_case),
) -> list[NewsArticleResponse]:
    articles = await use_case.execute(ListNewsCommand(feed_id=feed, limit=limit))
    return [news_article_to_response(article) for article in articles]
