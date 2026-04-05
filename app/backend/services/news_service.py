"""Service for summarizing scraped content into news articles using LLMs."""
import asyncio
import json
import logging
from collections import OrderedDict
from datetime import datetime, timezone

import re

from crawl4ai import AsyncWebCrawler
from crawl4ai.models import CrawlResult, MarkdownGenerationResult
from langchain_core.messages import HumanMessage, SystemMessage

from app.backend.models.news_schemas import (
    AnalyzedArticleResponse,
    NewsArticle,
    RankedNewsItem,
    RankRelevanceResponse,
)
from src.llm.models import ModelProvider, get_model, get_model_info

logger = logging.getLogger(__name__)

_MAX_CONTENT_CHARS = 8000

# ---------------------------------------------------------------------------
# Article analysis cache (URL + model -> result)
# ---------------------------------------------------------------------------
_article_cache: OrderedDict[tuple[str, str], AnalyzedArticleResponse] = OrderedDict()
_ARTICLE_CACHE_MAX = 100


def _article_cache_get(url: str, model_name: str) -> AnalyzedArticleResponse | None:
    return _article_cache.get((url, model_name))


def _article_cache_put(url: str, model_name: str, result: AnalyzedArticleResponse) -> None:
    _article_cache[(url, model_name)] = result
    while len(_article_cache) > _ARTICLE_CACHE_MAX:
        _article_cache.popitem(last=False)


# ---------------------------------------------------------------------------
# Summarize (existing)
# ---------------------------------------------------------------------------

_SUMMARIZE_PROMPT = """You are a financial analyst. Given raw scraped web content, produce a structured JSON summary.

Extract exactly these fields:
- title: A concise, compelling headline (max 15 words)
- summary: 2-3 sentence summary of the article content
- market_insight: One sentence on how this could affect the stock market or specific sectors
- sentiment: Exactly one of "bullish", "bearish", or "neutral"
- tickers_mentioned: Array of stock ticker symbols mentioned or strongly implied (e.g. ["AAPL", "MSFT"]). Empty array if none.

Respond ONLY with valid JSON matching this schema. No markdown, no extra text."""


async def summarize_scrape_result(
    content: str,
    model_name: str,
    model_provider: str,
    api_keys: dict[str, str] | None = None,
) -> NewsArticle:
    """Summarize a single scrape result into a NewsArticle using the configured LLM."""
    truncated = content[:_MAX_CONTENT_CHARS]

    provider_enum = ModelProvider(model_provider)
    llm = get_model(model_name, provider_enum, api_keys)

    model_info = get_model_info(model_name, model_provider)
    has_json = model_info and model_info.has_json_mode()

    messages = [
        SystemMessage(content=_SUMMARIZE_PROMPT),
        HumanMessage(content=f"Summarize this content:\n\n{truncated}"),
    ]

    if has_json:
        structured_llm = llm.with_structured_output(NewsArticle, method="json_mode")
        result = await asyncio.to_thread(structured_llm.invoke, messages)
        return result

    result = await asyncio.to_thread(llm.invoke, messages)
    text: str = result.content
    return _parse_news_article(text)


def _parse_news_article(text: str) -> NewsArticle:
    """Parse a NewsArticle from raw LLM text output."""
    try:
        return NewsArticle(**json.loads(text))
    except Exception:
        pass

    for marker in ("```json", "```"):
        start = text.find(marker)
        if start != -1:
            json_text = text[start + len(marker):]
            end = json_text.find("```")
            if end != -1:
                json_text = json_text[:end].strip()
                try:
                    return NewsArticle(**json.loads(json_text))
                except Exception:
                    pass

    logger.warning("Failed to parse LLM response into NewsArticle: %s", text[:200])
    return NewsArticle(
        title="Could not parse article",
        summary=text[:200],
        market_insight="Unable to determine market impact.",
        sentiment="neutral",
        tickers_mentioned=[],
    )


# ---------------------------------------------------------------------------
# Rank relevance (titles-only LLM call)
# ---------------------------------------------------------------------------

_RANK_PROMPT = """You are a financial analyst. Given a numbered list of news headlines, identify the 10 most impactful for stock markets and investors.

You MUST respond with ONLY a JSON object and nothing else. No explanations, no markdown, no text before or after the JSON.

The JSON object must have this exact structure:
{"ranked_items": [{"index": 0, "relevance_score": 0.95, "reason": "explanation"}, ...]}

Each item in ranked_items must have:
- "index": the 0-based position of the headline in the input list (integer)
- "relevance_score": a float from 0.0 to 1.0 indicating market impact
- "reason": one sentence explaining why this headline matters for markets

Order by relevance_score descending. Return exactly 10 items (or fewer if the input has fewer than 10 headlines).

IMPORTANT: Your entire response must be valid JSON. Do not include any text outside the JSON object."""


async def rank_news_relevance(
    titles: list[str],
    model_name: str,
    model_provider: str,
    api_keys: dict[str, str] | None = None,
) -> RankRelevanceResponse:
    """Rank news titles by market relevance using an LLM."""
    # Limit titles to avoid overwhelming small models
    MAX_TITLES = 50
    truncated = len(titles) > MAX_TITLES
    working_titles = titles[:MAX_TITLES]

    numbered = "\n".join(f"{i}. {t}" for i, t in enumerate(working_titles))

    provider_enum = ModelProvider(model_provider)
    llm = get_model(model_name, provider_enum, api_keys)

    model_info = get_model_info(model_name, model_provider)
    has_json = model_info and model_info.has_json_mode()

    logger.info(
        "rank_news_relevance: model=%s provider=%s model_info_found=%s has_json_mode=%s titles_count=%d (truncated=%s, sending=%d)",
        model_name, model_provider, model_info is not None, has_json, len(titles), truncated, len(working_titles),
    )

    messages = [
        SystemMessage(content=_RANK_PROMPT),
        HumanMessage(content=f"Rank these {len(working_titles)} headlines:\n\n{numbered}"),
    ]

    is_ollama = model_info and model_info.is_ollama()

    if is_ollama:
        # For Ollama: use format="json" binding and parse ourselves (more resilient than with_structured_output)
        logger.info("Using Ollama JSON format binding for ranking")
        json_llm = llm.bind(format="json")
        result = await asyncio.to_thread(json_llm.invoke, messages)
        raw_text = result.content
        logger.info("Ollama JSON response length=%d, first 300 chars: %s", len(raw_text), raw_text[:300])
        return _parse_rank_response(raw_text)

    if has_json:
        logger.info("Using structured output (json_mode) for ranking")
        try:
            structured_llm = llm.with_structured_output(RankRelevanceResponse, method="json_mode")
            result = await asyncio.to_thread(structured_llm.invoke, messages)
            logger.info("Structured output returned %d ranked items", len(result.ranked_items))
            return result
        except Exception as e:
            logger.warning("Structured output failed, falling back to raw parse: %s", e)

    logger.info("Using raw LLM output (no json_mode) for ranking")
    result = await asyncio.to_thread(llm.invoke, messages)
    raw_text = result.content
    logger.info("Raw LLM response length=%d, first 300 chars: %s", len(raw_text), raw_text[:300])
    return _parse_rank_response(raw_text)


def _parse_rank_response(text: str) -> RankRelevanceResponse:
    """Parse a RankRelevanceResponse from raw LLM text."""
    # Try direct JSON parse
    try:
        return RankRelevanceResponse(**json.loads(text))
    except Exception:
        pass

    # Try extracting from markdown code blocks
    for marker in ("```json", "```"):
        start = text.find(marker)
        if start != -1:
            json_text = text[start + len(marker):]
            end = json_text.find("```")
            if end != -1:
                json_text = json_text[:end].strip()
                try:
                    return RankRelevanceResponse(**json.loads(json_text))
                except Exception:
                    pass

    # Try finding a JSON object with "ranked_items" anywhere in the text
    match = re.search(r'\{[^{}]*"ranked_items"\s*:\s*\[.*?\]\s*\}', text, re.DOTALL)
    if match:
        try:
            return RankRelevanceResponse(**json.loads(match.group()))
        except Exception:
            pass

    # Last resort: extract individual {index, relevance_score, reason} objects
    item_pattern = re.compile(
        r'\{\s*"index"\s*:\s*(\d+)\s*,\s*"relevance_score"\s*:\s*([\d.]+)\s*,\s*"reason"\s*:\s*"([^"]+)"\s*\}'
    )
    matches = item_pattern.findall(text)
    if matches:
        items = [
            RankedNewsItem(index=int(m[0]), relevance_score=float(m[1]), reason=m[2])
            for m in matches
        ]
        logger.info("Extracted %d ranked items via regex fallback", len(items))
        return RankRelevanceResponse(ranked_items=items[:10])

    logger.warning("Failed to parse rank response: %s", text[:300])
    return RankRelevanceResponse(ranked_items=[])


# ---------------------------------------------------------------------------
# Crawl + analyze article
# ---------------------------------------------------------------------------


def _get_markdown_text(crawl_result: CrawlResult) -> str | None:
    """Extract markdown text from a CrawlResult."""
    raw = crawl_result.markdown
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    if isinstance(raw, MarkdownGenerationResult):
        return raw.raw_markdown
    return str(raw)


async def crawl_and_analyze_article(
    url: str,
    title: str,
    source: str,
    model_name: str,
    model_provider: str,
    api_keys: dict[str, str] | None = None,
    crawler: AsyncWebCrawler | None = None,
) -> AnalyzedArticleResponse:
    """Crawl a news article URL with crawl4ai and analyze with LLM.

    If a shared ``crawler`` instance is provided it will be reused (caller
    manages the async context). Otherwise a fresh one is created per call.
    """
    cached = _article_cache_get(url, model_name)
    if cached is not None:
        return cached

    now = datetime.now(timezone.utc)

    async def _crawl(c: AsyncWebCrawler) -> CrawlResult:
        return await asyncio.wait_for(c.arun(url=url), timeout=30)

    try:
        if crawler is not None:
            crawl_result = await _crawl(crawler)
        else:
            async with AsyncWebCrawler() as c:
                crawl_result = await _crawl(c)

        if not crawl_result.success:
            raise RuntimeError(f"Crawl failed: status={crawl_result.status_code}")

        markdown = _get_markdown_text(crawl_result)
        if not markdown or not markdown.strip():
            raise RuntimeError("Crawl returned empty content")

        article = await summarize_scrape_result(
            content=markdown,
            model_name=model_name,
            model_provider=model_provider,
            api_keys=api_keys,
        )

        response = AnalyzedArticleResponse(
            url=url,
            title=article.title,
            summary=article.summary,
            market_insight=article.market_insight,
            sentiment=article.sentiment,
            tickers_mentioned=article.tickers_mentioned,
            source_name=source,
            analyzed_at=now,
        )
    except Exception as exc:
        logger.warning("Failed to crawl/analyze %s: %s", url, exc)
        response = AnalyzedArticleResponse(
            url=url,
            title=title,
            summary=f"Failed to analyze: {exc}",
            market_insight="Unable to determine market impact.",
            sentiment="neutral",
            tickers_mentioned=[],
            source_name=source,
            analyzed_at=now,
        )

    _article_cache_put(url, model_name, response)
    return response
