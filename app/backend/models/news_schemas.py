"""Pydantic schemas for the news summarization feature."""
from datetime import datetime

from pydantic import BaseModel


class NewsArticle(BaseModel):
    """LLM-generated summary of a scraped article."""

    title: str
    summary: str
    market_insight: str
    sentiment: str  # bullish / bearish / neutral
    tickers_mentioned: list[str]


class NewsArticleResponse(BaseModel):
    """Response model for a single news article card."""

    id: int  # scrape_result.id
    title: str
    summary: str
    market_insight: str
    sentiment: str
    tickers_mentioned: list[str]
    source_url: str
    source_name: str
    scraped_at: datetime
    website_id: int


class NewsSummarizeRequest(BaseModel):
    """Request body for the POST /news/summarize endpoint."""

    model_name: str
    model_provider: str
    result_ids: list[int] | None = None
    website_ids: list[int] | None = None
    limit: int = 20


# ---------------------------------------------------------------------------
# Rank relevance (titles-only LLM call)
# ---------------------------------------------------------------------------


class RankRelevanceRequest(BaseModel):
    titles: list[str]
    model_name: str
    model_provider: str


class RankedNewsItem(BaseModel):
    index: int
    relevance_score: float
    reason: str


class RankRelevanceResponse(BaseModel):
    """LLM structured output for ranking news by market relevance."""
    ranked_items: list[RankedNewsItem]


# ---------------------------------------------------------------------------
# Article crawl + analysis
# ---------------------------------------------------------------------------


class AnalyzeArticleInput(BaseModel):
    url: str
    title: str
    source: str


class AnalyzeArticlesRequest(BaseModel):
    articles: list[AnalyzeArticleInput]
    model_name: str
    model_provider: str


class AnalyzedArticleResponse(BaseModel):
    url: str
    title: str
    summary: str
    market_insight: str
    sentiment: str
    tickers_mentioned: list[str]
    source_name: str
    analyzed_at: datetime


# ---------------------------------------------------------------------------
# Market Pulse
# ---------------------------------------------------------------------------


class MarketIndex(BaseModel):
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float


class MarketPulseResponse(BaseModel):
    indices: list[MarketIndex]
    news: list  # list of RealtimeNewsItem dicts
