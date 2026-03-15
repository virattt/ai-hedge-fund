"""NewsNow data source for free news aggregation."""
import logging
import time
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
        "xueqiu": "雪球",
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

        This is a placeholder that will be implemented in next task.
        """
        return []
