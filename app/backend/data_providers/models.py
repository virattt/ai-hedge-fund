"""Data models for the provider abstraction layer."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class DataAvailability(Enum):
    """Describes why data is missing."""
    AVAILABLE = "available"
    UNSUPPORTED_TICKER = "unsupported_ticker"
    PROVIDER_ERROR = "provider_error"
    NO_DATA = "no_data"
    RATE_LIMITED = "rate_limited"


@dataclass
class PriceBar:
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class FundamentalData:
    """Normalised fundamental metrics from any provider."""
    ticker: str
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None
    profit_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    roe: Optional[float] = None
    debt_to_equity: Optional[float] = None
    dividend_yield: Optional[float] = None
    market_cap: Optional[float] = None
    source: str = "unknown"


@dataclass
class NewsItem:
    """A single news article/headline."""
    title: str
    source: str
    published: Optional[datetime] = None
    url: Optional[str] = None
    sentiment: Optional[str] = None  # "positive", "negative", "neutral"
    relevance_score: Optional[float] = None


@dataclass
class SentimentResult:
    """Aggregated sentiment for a ticker."""
    ticker: str
    overall_sentiment: str  # "bullish", "bearish", "neutral"
    confidence: float  # 0.0 to 1.0
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    total_articles: int = 0
    themes: list[str] = field(default_factory=list)
    headlines: list[str] = field(default_factory=list)
    source: str = "unknown"


@dataclass
class ProviderResult:
    """Wrapper around any provider response with availability metadata."""
    availability: DataAvailability
    data: object = None
    provider_name: str = "unknown"
    error_message: Optional[str] = None
