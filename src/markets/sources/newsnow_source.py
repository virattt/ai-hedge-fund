"""NewsNow data source for free news aggregation."""
import logging
import time
import requests
from typing import Dict, List, Optional
from datetime import datetime

from src.markets.sources.base import DataSource

logger = logging.getLogger(__name__)


class NewsNowSource(DataSource):
    """
    NewsNow free news aggregation source.

    Features:
    - Completely free, no API key required
    - No rate limiting
    - Aggregates from multiple financial news sources

    Sources:
    - cls: 财联社 (professional financial news)
    - wallstreetcn: 华尔街见闻 (international finance)
    - xueqiu: 雪球 (investment community)
    """

    BASE_URL = "https://newsnow.busiyi.world/api/s"

    SOURCES = {
        "cls": "财联社",
        "wallstreetcn": "华尔街见闻",
        # "xueqiu": "雪球",  # 403 Forbidden，已禁用
    }

    def __init__(self):
        super().__init__("NewsNow")
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        self._cache_time = {}

    def supports_market(self, market: str) -> bool:
        """NewsNow supports all markets."""
        return market.upper() in ["US", "CN", "HK"]

    def get_prices(
        self, ticker: str, start_date: str, end_date: str
    ) -> List[Dict]:
        """NewsNow does not provide price data."""
        return []

    def get_financial_metrics(
        self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10
    ) -> Optional[Dict]:
        """NewsNow does not provide financial metrics."""
        return None

    def get_company_news(
        self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """
        Get company news from NewsNow.

        Args:
            ticker: Stock ticker
            end_date: End date (YYYY-MM-DD)
            start_date: Start date (optional, not used by NewsNow)
            limit: Maximum number of news items

        Returns:
            List of news dictionaries
        """
        # Check cache
        cache_key = f"{ticker}_{end_date}"
        if self._is_cache_valid(cache_key):
            self.logger.info(f"⚡ Using cached news for {ticker}")
            return self._cache[cache_key]

        # Fetch from all sources
        all_news = []
        for source_id in ["cls", "wallstreetcn"]:
            try:
                news = self._fetch_from_source(source_id, limit=50)
                all_news.extend(news)
                time.sleep(0.2)  # Avoid request bursts
            except Exception as e:
                self.logger.warning(f"Failed to fetch from {source_id}: {e}")
                continue

        # Filter by ticker
        filtered = self._filter_by_ticker(all_news, ticker)

        # Convert to standard format
        result = self._convert_to_company_news(filtered, ticker)[:limit]

        # Cache results
        self._cache[cache_key] = result
        self._cache_time[cache_key] = time.time()

        self.logger.info(f"✓ Retrieved {len(result)} news for {ticker}")
        return result

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid."""
        if cache_key not in self._cache:
            return False

        age = time.time() - self._cache_time.get(cache_key, 0)
        return age < self._cache_ttl

    def _fetch_from_source(self, source_id: str, limit: int = 50) -> List[Dict]:
        """
        Fetch news from a specific NewsNow source.

        Args:
            source_id: Source identifier (cls, wallstreetcn, xueqiu)
            limit: Maximum items to fetch

        Returns:
            List of raw news items
        """
        url = f"{self.BASE_URL}?id={source_id}"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            items = data.get("items", [])[:limit]

            self.logger.debug(f"Fetched {len(items)} items from {source_id}")
            return items

        except Exception as e:
            self.logger.error(f"Error fetching from {source_id}: {e}")
            return []

    def _filter_by_ticker(self, news_list: List[Dict], ticker: str) -> List[Dict]:
        """
        Filter news by ticker keyword.

        Args:
            news_list: List of news items
            ticker: Stock ticker to filter by

        Returns:
            Filtered news list
        """
        keywords = [ticker.upper()]

        # Phase 1: Basic ticker matching
        # Phase 4 TODO: Add company name mapping for better recall

        filtered = []
        for news in news_list:
            title = news.get("title", "").upper()
            if any(kw in title for kw in keywords):
                filtered.append(news)

        return filtered

    def _convert_to_company_news(self, news_list: List[Dict], ticker: str) -> List[Dict]:
        """
        Convert NewsNow format to standard CompanyNews format.

        Args:
            news_list: List of NewsNow news items
            ticker: Stock ticker

        Returns:
            List of standardized news dictionaries
        """
        result = []

        for news in news_list:
            try:
                # Parse date
                date_str = news.get("publish_time", datetime.now().isoformat())
                if not date_str:
                    date_str = datetime.now().isoformat()

                result.append({
                    "ticker": ticker,
                    "title": news.get("title", ""),
                    "author": "",  # NewsNow doesn't provide author
                    "source": "NewsNow",
                    "date": date_str,
                    "url": news.get("url", ""),
                    "sentiment": None,  # No sentiment analysis
                })
            except Exception as e:
                self.logger.warning(f"Failed to convert news item: {e}")
                continue

        return result
