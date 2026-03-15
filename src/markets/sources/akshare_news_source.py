"""AKShare news data source for CN and HK markets."""
import logging
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import hashlib

from src.markets.sources.base import DataSource

logger = logging.getLogger(__name__)


class AKShareNewsSource(DataSource):
    """
    AKShare news data source with multi-source aggregation and deduplication.

    Features:
    - Eastmoney (东方财富) news via stock_news_em
    - Support for both CN and HK markets
    - News deduplication by title similarity
    - Automatic ticker/company name mapping
    """

    # Ticker to company name mapping for better search results
    TICKER_TO_NAME = {
        # Major HK Tech stocks
        "00700": "腾讯",
        "09988": "阿里巴巴",
        "01024": "快手",
        "09618": "京东",
        "01810": "小米",
        "03690": "美团",
        "09999": "网易",
        "09626": "哔哩哔哩",
        "01772": "赣锋锂业",
        "06618": "京东健康",
        # Major HK Financial & Telecom
        "00388": "香港交易所",
        "00941": "中国移动",
        "00762": "中国联通",
        "00939": "建设银行",
        "01398": "工商银行",
        "03988": "中国银行",
        # Major HK Energy & Industrials
        "00857": "中国石油",
        "00386": "中国石化",
        "01211": "比亚迪",
        "02333": "长城汽车",
        "01810": "小米集团",
        # Major HK Property
        "01997": "九龙仓置业",
        "00016": "新鸿基地产",
        "00823": "领展房产基金",
    }

    def __init__(self):
        super().__init__("AKShareNews")
        self._akshare = None
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        self._cache_time = {}
        self._initialize_akshare()

    def _initialize_akshare(self):
        """Lazy initialization of akshare module."""
        try:
            import akshare as ak
            self._akshare = ak
            self.logger.debug("AKShare initialized successfully")
        except ImportError:
            self.logger.error("AKShare not installed. Install with: pip install akshare")
            self._akshare = None

    def _ensure_akshare(self):
        """Ensure akshare is available."""
        if self._akshare is None:
            self._initialize_akshare()
        if self._akshare is None:
            raise RuntimeError("AKShare is not available")

    def supports_market(self, market: str) -> bool:
        """AKShare News supports CN and HK markets."""
        return market.upper() in ["CN", "HK"]

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Dict]:
        """AKShare News does not provide price data."""
        return []

    def get_financial_metrics(
        self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10
    ) -> Optional[Dict]:
        """AKShare News does not provide financial metrics."""
        return None

    def get_company_news(
        self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """
        Get company news from AKShare Eastmoney source.

        Args:
            ticker: Stock ticker (e.g., '00700' for HK, '000001' for CN)
            end_date: End date (YYYY-MM-DD)
            start_date: Start date (optional, not used by Eastmoney)
            limit: Maximum number of news items

        Returns:
            List of news dictionaries with deduplication
        """
        self._ensure_akshare()

        # Check cache
        cache_key = f"{ticker}_{end_date}"
        if self._is_cache_valid(cache_key):
            self.logger.info(f"⚡ Using cached news for {ticker}")
            return self._cache[cache_key]

        # Collect news from multiple search terms
        all_news = []
        search_terms = self._get_search_terms(ticker)

        for term in search_terms:
            try:
                news = self._fetch_news_by_keyword(term, limit=50)
                all_news.extend(news)
                time.sleep(0.5)  # Rate limiting
            except Exception as e:
                self.logger.warning(f"Failed to fetch news for '{term}': {e}")
                continue

        # Deduplicate by title hash
        deduplicated = self._deduplicate_news(all_news)

        # Convert to standard format
        result = self._convert_to_company_news(deduplicated, ticker)[:limit]

        # Cache results
        self._cache[cache_key] = result
        self._cache_time[cache_key] = time.time()

        self.logger.info(f"✓ Retrieved {len(result)} deduplicated news for {ticker}")
        return result

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid."""
        if cache_key not in self._cache:
            return False

        age = time.time() - self._cache_time.get(cache_key, 0)
        return age < self._cache_ttl

    def _get_search_terms(self, ticker: str) -> List[str]:
        """
        Get search terms for a ticker.

        Args:
            ticker: Stock ticker (e.g., '00700', '000001')

        Returns:
            List of search terms to try
        """
        terms = []

        # Remove leading zeros for search
        clean_ticker = ticker.lstrip('0')
        if clean_ticker:
            terms.append(clean_ticker)

        # Add ticker with leading zeros
        terms.append(ticker)

        # Add company name if available
        if ticker in self.TICKER_TO_NAME:
            terms.append(self.TICKER_TO_NAME[ticker])

        return terms

    def _fetch_news_by_keyword(self, keyword: str, limit: int = 50) -> List[Dict]:
        """
        Fetch news from Eastmoney by keyword.

        Args:
            keyword: Search keyword (ticker or company name)
            limit: Maximum items to fetch

        Returns:
            List of raw news items
        """
        try:
            self.logger.info(f"[AKShareNews] 📡 Calling stock_news_em(symbol={keyword})")
            df = self._akshare.stock_news_em(symbol=keyword)

            if df is None or df.empty:
                self.logger.warning(f"No news found for keyword: {keyword}")
                return []

            news_list = []
            for _, row in df.head(limit).iterrows():
                news_item = {
                    "title": str(row.get("新闻标题", "")),
                    "content": str(row.get("新闻内容", "")),
                    "date": str(row.get("发布时间", "")),
                    "source": str(row.get("文章来源", "东方财富")),
                    "url": str(row.get("新闻链接", "")),
                    "keyword": keyword,  # Track which keyword found this
                }
                news_list.append(news_item)

            self.logger.debug(f"Fetched {len(news_list)} news for '{keyword}'")
            return news_list

        except Exception as e:
            self.logger.error(f"Error fetching news for '{keyword}': {e}")
            return []

    def _deduplicate_news(self, news_list: List[Dict]) -> List[Dict]:
        """
        Deduplicate news by title hash.

        Args:
            news_list: List of news items

        Returns:
            Deduplicated news list
        """
        seen_hashes = set()
        deduplicated = []

        for news in news_list:
            title = news.get("title", "")
            # Create hash from title
            title_hash = hashlib.md5(title.encode('utf-8')).hexdigest()

            if title_hash not in seen_hashes:
                seen_hashes.add(title_hash)
                deduplicated.append(news)

        removed = len(news_list) - len(deduplicated)
        if removed > 0:
            self.logger.debug(f"Removed {removed} duplicate news items")

        return deduplicated

    def _convert_to_company_news(self, news_list: List[Dict], ticker: str) -> List[Dict]:
        """
        Convert AKShare format to standard CompanyNews format.

        Args:
            news_list: List of AKShare news items
            ticker: Stock ticker

        Returns:
            List of standardized news dictionaries with relevance filtering
        """
        result = []

        # Get company name for relevance check
        company_name = self.TICKER_TO_NAME.get(ticker, "")
        clean_ticker = ticker.lstrip('0')

        for news in news_list:
            try:
                title = news.get("title", "")
                content = news.get("content", "")

                # Relevance check: ensure news is actually about this company
                # Priority 1: Company name is the most reliable indicator
                has_company_name = company_name and (company_name in title or company_name in content[:200])

                # Priority 2: Ticker in title (but be careful with short numbers)
                has_ticker = False
                if len(clean_ticker) >= 4:  # Only trust longer tickers
                    has_ticker = clean_ticker in title or ticker in title

                # Combined relevance check
                is_relevant = has_company_name or has_ticker

                if not is_relevant:
                    self.logger.debug(f"Skipping irrelevant news: {title[:50]}...")
                    continue

                # Parse date
                date_str = news.get("date", "")
                if not date_str:
                    date_str = datetime.now().isoformat()
                else:
                    # Convert "YYYY-MM-DD HH:MM:SS" to ISO format
                    try:
                        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        date_str = dt.isoformat()
                    except ValueError:
                        # Keep original if parsing fails
                        pass

                result.append({
                    "ticker": ticker,
                    "title": title,
                    "author": "",  # Eastmoney doesn't provide author
                    "source": news.get("source", "东方财富"),
                    "date": date_str,
                    "url": news.get("url", ""),
                    "sentiment": None,  # No sentiment analysis
                })
            except Exception as e:
                self.logger.warning(f"Failed to convert news item: {e}")
                continue

        self.logger.info(f"Filtered to {len(result)} relevant news items for {ticker}")
        return result
