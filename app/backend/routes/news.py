"""FastAPI routes for LLM-powered news summarization of scraped content."""
import asyncio
import logging
from collections import OrderedDict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backend.database import get_db
from app.backend.database.models import ScrapeResult, ScrapingWebsite
from app.backend.models.news_schemas import NewsArticleResponse, NewsSummarizeRequest
from app.backend.repositories.scraping_repository import ScrapingRepository
from app.backend.services.api_key_service import ApiKeyService
from app.backend.services.news_service import summarize_scrape_result
from app.backend.services.realtime_news_service import RealtimeNewsItem, fetch_all_realtime_news

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/news", tags=["news"])

# In-memory cache: (website_id, model_name) -> NewsArticleResponse
_summary_cache: OrderedDict[tuple[int, str], NewsArticleResponse] = OrderedDict()
_CACHE_MAX = 200

_CONCURRENCY_LIMIT = 3


def _cache_get(website_id: int, model_name: str) -> NewsArticleResponse | None:
    key = (website_id, model_name)
    return _summary_cache.get(key)


def _cache_put(website_id: int, model_name: str, article: NewsArticleResponse) -> None:
    key = (website_id, model_name)
    _summary_cache[key] = article
    while len(_summary_cache) > _CACHE_MAX:
        _summary_cache.popitem(last=False)


@router.post(
    "/summarize",
    response_model=list[NewsArticleResponse],
    responses={
        400: {"description": "No scrape results found"},
        500: {"description": "Internal server error"},
    },
)
async def summarize_news(request: NewsSummarizeRequest, db: Session = Depends(get_db)) -> list[NewsArticleResponse]:
    """Summarize scraped content into news articles using the specified LLM.

    Groups all pages by website and makes one LLM call per website (not per page).
    """
    try:
        repo = ScrapingRepository(db)
        api_keys = ApiKeyService(db).get_api_keys_dict()

        # Fetch scrape results
        if request.result_ids:
            raw_results: list[ScrapeResult] = []
            for rid in request.result_ids:
                r = repo.get_result_by_id(rid)
                if r and r.status == "success" and r.content:
                    raw_results.append(r)
        else:
            query = db.query(ScrapeResult).filter(ScrapeResult.status == "success", ScrapeResult.content.isnot(None))
            if request.website_ids:
                query = query.filter(ScrapeResult.website_id.in_(request.website_ids))
            raw_results = query.order_by(ScrapeResult.scraped_at.desc()).limit(request.limit * 5).all()

        if not raw_results:
            return []

        # Group by website_id: combine all pages into one content block per website
        grouped: dict[int, list[ScrapeResult]] = {}
        for r in raw_results:
            grouped.setdefault(r.website_id, []).append(r)

        logger.info("Summarizing content from %d website(s) with model=%s", len(grouped), request.model_name)

        sem = asyncio.Semaphore(_CONCURRENCY_LIMIT)
        articles: list[NewsArticleResponse | None] = [None] * len(grouped)

        async def _process(idx: int, website_id: int, page_results: list[ScrapeResult]) -> None:
            cached = _cache_get(website_id, request.model_name)
            if cached:
                articles[idx] = cached
                return

            async with sem:
                website: ScrapingWebsite | None = repo.get_website_by_id(website_id)
                source_name = website.name if website else "Unknown"
                source_url = website.url if website else ""

                # Combine all pages into one content string
                combined_parts: list[str] = []
                for r in page_results:
                    page_label = r.page_url or source_url
                    combined_parts.append(f"--- Page: {page_label} ---\n{r.content}")
                combined_content = "\n\n".join(combined_parts)

                latest_scraped_at = max(r.scraped_at for r in page_results)

                article = await summarize_scrape_result(
                    content=combined_content,
                    model_name=request.model_name,
                    model_provider=request.model_provider,
                    api_keys=api_keys,
                )

                response = NewsArticleResponse(
                    id=page_results[0].id,
                    title=article.title,
                    summary=article.summary,
                    market_insight=article.market_insight,
                    sentiment=article.sentiment,
                    tickers_mentioned=article.tickers_mentioned,
                    source_url=source_url,
                    source_name=source_name,
                    scraped_at=latest_scraped_at,
                    website_id=website_id,
                )
                _cache_put(website_id, request.model_name, response)
                articles[idx] = response

        tasks = [_process(i, wid, pages) for i, (wid, pages) in enumerate(grouped.items())]
        await asyncio.gather(*tasks)

        return [a for a in articles if a is not None]

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to summarize news")
        raise HTTPException(status_code=500, detail=f"Failed to summarize news: {str(e)}") from e


@router.get(
    "/realtime",
    response_model=list[RealtimeNewsItem],
    responses={
        500: {"description": "Internal server error"},
    },
)
async def get_realtime_news() -> list[RealtimeNewsItem]:
    """Fetch real-time financial news from finvizfinance and yfinance."""
    try:
        return await fetch_all_realtime_news()
    except Exception as e:
        logger.exception("Failed to fetch realtime news")
        raise HTTPException(status_code=500, detail=f"Failed to fetch realtime news: {str(e)}") from e
