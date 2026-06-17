"""Provider manager — orchestrates data fetching across multiple providers.

Tries providers in priority order, falls back automatically, normalises
results, and provides clear availability reporting.
"""

import logging
from typing import Optional

from app.backend.data_providers.base import DataProvider
from app.backend.data_providers.models import (
    DataAvailability,
    FundamentalData,
    NewsItem,
    PriceBar,
    ProviderResult,
    SentimentResult,
)

logger = logging.getLogger(__name__)


class ProviderManager:
    """Manages multiple data providers with fallback logic."""

    def __init__(self, api_keys: Optional[dict[str, str]] = None):
        from app.backend.data_providers.financial_datasets import FinancialDatasetsProvider
        from app.backend.data_providers.yahoo_finance import YahooFinanceProvider

        fd_key = (api_keys or {}).get("FINANCIAL_DATASETS_API_KEY")
        self._providers: list[DataProvider] = [
            FinancialDatasetsProvider(api_key=fd_key),
            YahooFinanceProvider(),
        ]

    def get_prices(
        self, ticker: str, start_date: str, end_date: str
    ) -> ProviderResult:
        """Fetch prices from the first provider that returns data."""
        for provider in self._providers:
            if not provider.supports_ticker(ticker):
                continue
            result = provider.get_prices(ticker, start_date, end_date)
            if result.availability == DataAvailability.AVAILABLE and result.data:
                return result
            logger.debug(
                "Provider %s returned %s for prices of %s",
                provider.name, result.availability.value, ticker,
            )

        return ProviderResult(
            availability=DataAvailability.NO_DATA,
            provider_name="all",
            error_message=f"No provider returned price data for {ticker}",
        )

    def get_fundamentals(self, ticker: str) -> ProviderResult:
        """Fetch fundamentals from the first provider that returns data."""
        for provider in self._providers:
            if not provider.supports_ticker(ticker):
                continue
            result = provider.get_fundamentals(ticker)
            if result.availability == DataAvailability.AVAILABLE and result.data:
                return result

        return ProviderResult(
            availability=DataAvailability.NO_DATA,
            provider_name="all",
            error_message=f"No provider returned fundamental data for {ticker}",
        )

    def get_news(self, ticker: str, limit: int = 20) -> ProviderResult:
        """Fetch news from all providers that support the ticker, merged."""
        all_articles: list[NewsItem] = []
        any_success = False

        for provider in self._providers:
            if not provider.supports_ticker(ticker):
                continue
            result = provider.get_news(ticker, limit=limit)
            if result.availability == DataAvailability.AVAILABLE and result.data:
                all_articles.extend(result.data)
                any_success = True

        if not any_success:
            return ProviderResult(
                availability=DataAvailability.NO_DATA,
                provider_name="all",
                error_message=f"No news found for {ticker}",
            )

        # Deduplicate by title similarity
        seen_titles: set[str] = set()
        unique_articles: list[NewsItem] = []
        for article in all_articles:
            key = article.title.lower().strip()[:60]
            if key not in seen_titles:
                seen_titles.add(key)
                unique_articles.append(article)

        # Sort by date (most recent first)
        unique_articles.sort(
            key=lambda a: a.published or __import__("datetime").datetime.min,
            reverse=True,
        )

        return ProviderResult(
            availability=DataAvailability.AVAILABLE,
            data=unique_articles[:limit],
            provider_name="merged",
        )

    def get_sentiment(self, ticker: str, limit: int = 20) -> ProviderResult:
        """Fetch news and compute aggregated sentiment."""
        news_result = self.get_news(ticker, limit=limit)

        if news_result.availability != DataAvailability.AVAILABLE or not news_result.data:
            return ProviderResult(
                availability=news_result.availability,
                provider_name=news_result.provider_name,
                error_message=news_result.error_message,
            )

        articles: list[NewsItem] = news_result.data
        sentiment_result = _aggregate_sentiment(ticker, articles)

        return ProviderResult(
            availability=DataAvailability.AVAILABLE,
            data=sentiment_result,
            provider_name="aggregated",
        )


# --- Sentiment aggregation ---

_BULLISH_KEYWORDS = [
    "surge", "rally", "beat", "exceeds", "upgrade", "bullish", "growth",
    "record high", "outperform", "strong", "upside", "gain", "positive",
    "breakout", "momentum", "buy", "dividend increase",
]

_BEARISH_KEYWORDS = [
    "plunge", "crash", "miss", "downgrade", "bearish", "decline", "warning",
    "cut", "loss", "slump", "sell", "concern", "risk", "weak", "negative",
    "layoff", "recession", "default", "investigation",
]

_THEME_KEYWORDS = {
    "AI / Technology": ["ai", "artificial intelligence", "machine learning", "chip", "semiconductor", "tech"],
    "Inflation / Rates": ["inflation", "interest rate", "fed", "boe", "central bank", "rate cut", "rate hike"],
    "Commodities": ["gold", "oil", "commodity", "mining", "crude", "metal"],
    "Earnings": ["earnings", "revenue", "profit", "quarterly", "results", "guidance", "beat", "miss"],
    "Regulation": ["regulation", "sec", "fca", "compliance", "antitrust", "lawsuit", "fine"],
    "Macro / Geopolitics": ["geopolitical", "tariff", "trade war", "sanctions", "election", "gdp", "recession"],
    "ESG / Climate": ["esg", "climate", "green", "sustainability", "carbon", "renewable"],
}


def _classify_headline(title: str) -> str:
    """Classify a headline as bullish/bearish/neutral based on keywords."""
    title_lower = title.lower()
    bullish_hits = sum(1 for kw in _BULLISH_KEYWORDS if kw in title_lower)
    bearish_hits = sum(1 for kw in _BEARISH_KEYWORDS if kw in title_lower)

    if bullish_hits > bearish_hits:
        return "bullish"
    if bearish_hits > bullish_hits:
        return "bearish"
    return "neutral"


def _detect_themes(headlines: list[str]) -> list[str]:
    """Detect recurring themes across headlines."""
    theme_counts: dict[str, int] = {}
    combined = " ".join(h.lower() for h in headlines)

    for theme, keywords in _THEME_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in combined)
        if hits >= 1:
            theme_counts[theme] = hits

    return [t for t, _ in sorted(theme_counts.items(), key=lambda x: -x[1])][:4]


def _aggregate_sentiment(ticker: str, articles: list[NewsItem]) -> SentimentResult:
    """Aggregate headline sentiment into an overall score."""
    bullish = 0
    bearish = 0
    neutral = 0
    headlines: list[str] = []

    for article in articles:
        if not article.title:
            continue
        headlines.append(article.title)

        # Use pre-classified sentiment if available, otherwise classify
        if article.sentiment:
            s = article.sentiment.lower()
            if s in ("positive", "bullish"):
                bullish += 1
            elif s in ("negative", "bearish"):
                bearish += 1
            else:
                neutral += 1
        else:
            classified = _classify_headline(article.title)
            if classified == "bullish":
                bullish += 1
            elif classified == "bearish":
                bearish += 1
            else:
                neutral += 1

    total = bullish + bearish + neutral
    if total == 0:
        return SentimentResult(
            ticker=ticker,
            overall_sentiment="neutral",
            confidence=0.0,
            source="aggregated",
        )

    # Determine overall sentiment
    if bullish > bearish and bullish > neutral:
        overall = "bullish"
        confidence = bullish / total
    elif bearish > bullish and bearish > neutral:
        overall = "bearish"
        confidence = bearish / total
    else:
        overall = "neutral"
        confidence = neutral / total if neutral > 0 else 0.5

    # Moderate confidence — never claim 100%
    confidence = min(confidence, 0.85)

    themes = _detect_themes(headlines)

    return SentimentResult(
        ticker=ticker,
        overall_sentiment=overall,
        confidence=round(confidence, 2),
        bullish_count=bullish,
        bearish_count=bearish,
        neutral_count=neutral,
        total_articles=total,
        themes=themes,
        headlines=headlines[:5],
        source="aggregated",
    )
