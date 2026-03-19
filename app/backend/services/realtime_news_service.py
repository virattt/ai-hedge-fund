"""Service for fetching real-time financial news from finvizfinance (and yfinance when available)."""
import asyncio
import logging
from datetime import datetime

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class RealtimeNewsItem(BaseModel):
    """A single real-time news item."""
    title: str
    link: str
    source: str
    date: str
    category: str  # "news" or "blog"
    provider: str  # "finviz" or "yfinance"


async def fetch_finviz_news() -> list[RealtimeNewsItem]:
    """Fetch latest news from finvizfinance."""
    def _fetch() -> list[RealtimeNewsItem]:
        from finvizfinance.news import News
        n = News()
        all_news = n.get_news()
        items: list[RealtimeNewsItem] = []

        for category in ("news", "blogs"):
            df = all_news.get(category)
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                items.append(RealtimeNewsItem(
                    title=str(row.get("Title", "")),
                    link=str(row.get("Link", "")),
                    source=str(row.get("Source", "")),
                    date=str(row.get("Date", "")),
                    category=category,
                    provider="finviz",
                ))

        return items

    return await asyncio.to_thread(_fetch)


def _parse_yfinance_article(article: dict) -> tuple[str, str, str, str] | None:
    """Extract (title, link, source, date) from a yfinance news article.

    yfinance >=1.2 returns Yahoo XHR stream format:
      {"content": {"title": "...", "pubDate": "...", "canonicalUrl": {"url": "..."}, "provider": {"displayName": "..."}}}

    Older versions returned flat dicts:
      {"title": "...", "link": "...", "publisher": "...", "providerPublishTime": 1234567890}
    """
    # New format (v1.2+): nested under "content"
    content = article.get("content")
    if isinstance(content, dict):
        title = content.get("title", "")
        canonical = content.get("canonicalUrl")
        link = canonical.get("url", "") if isinstance(canonical, dict) else ""
        provider = content.get("provider")
        source = provider.get("displayName", "Yahoo Finance") if isinstance(provider, dict) else "Yahoo Finance"
        date_str = content.get("pubDate", "")
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                pass
        if title and link:
            return (title, link, source, date_str)

    # Old format: flat keys
    title = article.get("title", "")
    link = article.get("link", "")
    source = article.get("publisher", "Yahoo Finance")
    publish_time = article.get("providerPublishTime", 0)
    date_str = datetime.fromtimestamp(publish_time).strftime("%Y-%m-%d %H:%M") if publish_time else ""
    if title and link:
        return (title, link, source, date_str)

    return None


async def fetch_yfinance_news(tickers: list[str] | None = None) -> list[RealtimeNewsItem]:
    """Fetch latest news from yfinance for given tickers."""
    if not tickers:
        tickers = ["SPY", "QQQ", "DIA"]

    def _fetch() -> list[RealtimeNewsItem]:
        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not installed, skipping yfinance news")
            return []

        items: list[RealtimeNewsItem] = []
        seen_links: set[str] = set()

        for ticker_symbol in tickers:
            try:
                ticker = yf.Ticker(ticker_symbol)
                news_list = ticker.news or []
                for article in news_list:
                    parsed = _parse_yfinance_article(article)
                    if parsed is None:
                        continue
                    title, link, source, date_str = parsed
                    if link in seen_links:
                        continue
                    seen_links.add(link)
                    items.append(RealtimeNewsItem(
                        title=title,
                        link=link,
                        source=source,
                        date=date_str,
                        category="news",
                        provider="yfinance",
                    ))
            except Exception as exc:
                logger.warning("Failed to fetch yfinance news for %s: %s", ticker_symbol, exc)

        return items

    return await asyncio.to_thread(_fetch)


async def fetch_all_realtime_news() -> list[RealtimeNewsItem]:
    """Fetch news from all available sources, merged and deduplicated."""
    results: list[RealtimeNewsItem] = []

    # Try finviz first
    try:
        finviz_items = await fetch_finviz_news()
        results.extend(finviz_items)
    except Exception as exc:
        logger.warning("Failed to fetch finviz news: %s", exc)

    # Try yfinance (gracefully skips if not installed)
    try:
        yf_items = await fetch_yfinance_news()
        # Deduplicate by link
        existing_links = {item.link for item in results}
        for item in yf_items:
            if item.link not in existing_links:
                results.append(item)
                existing_links.add(item.link)
    except Exception as exc:
        logger.warning("Failed to fetch yfinance news: %s", exc)

    return results
