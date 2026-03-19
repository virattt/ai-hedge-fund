"""Service for summarizing scraped content into news articles using LLMs."""
import asyncio
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.backend.models.news_schemas import NewsArticle
from src.llm.models import ModelProvider, get_model, get_model_info

logger = logging.getLogger(__name__)

_MAX_CONTENT_CHARS = 8000

_SYSTEM_PROMPT = """You are a financial analyst. Given raw scraped web content, produce a structured JSON summary.

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
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f"Summarize this content:\n\n{truncated}"),
    ]

    if has_json:
        structured_llm = llm.with_structured_output(NewsArticle, method="json_mode")
        result = await asyncio.to_thread(structured_llm.invoke, messages)
        return result

    # Fallback: ask for JSON and parse manually
    result = await asyncio.to_thread(llm.invoke, messages)
    text: str = result.content
    return _parse_news_article(text)


def _parse_news_article(text: str) -> NewsArticle:
    """Parse a NewsArticle from raw LLM text output."""
    # Try direct JSON parse first
    try:
        return NewsArticle(**json.loads(text))
    except Exception:
        pass

    # Try extracting from markdown code block
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

    # Last resort: return a default
    logger.warning("Failed to parse LLM response into NewsArticle: %s", text[:200])
    return NewsArticle(
        title="Could not parse article",
        summary=text[:200],
        market_insight="Unable to determine market impact.",
        sentiment="neutral",
        tickers_mentioned=[],
    )
