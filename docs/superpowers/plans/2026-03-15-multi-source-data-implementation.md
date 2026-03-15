# Multi-Source Data Architecture Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three free data sources (NewsNow, Sina Finance, Eastmoney) to eliminate rate limiting and reduce paid API dependency by 90%+.

**Architecture:** Extend existing `src/markets/sources/` architecture with new free sources, update market adapters to use multi-source fallback chains (free sources first, Financial Datasets API as fallback).

**Tech Stack:** Python 3.10+, requests, pandas, existing cache layer (memory + MySQL)

**Spec Document:** `docs/superpowers/specs/2026-03-15-comprehensive-multi-source-data-architecture.md`

---

## File Structure Overview

### New Files to Create
```
src/markets/sources/
├── newsnow_source.py          # Free news aggregation (财联社/华尔街见闻/雪球)
├── sina_finance_source.py     # Free prices/quotes (CN/HK/US)
└── eastmoney_source.py        # Free CN market data

tests/markets/sources/
├── test_newsnow_source.py
├── test_sina_finance_source.py
└── test_eastmoney_source.py
```

### Files to Modify
```
src/markets/
├── us_stock.py                # Add NewsNow to news_sources
├── cn_stock.py                # Add Eastmoney, Sina to sources
└── hk_stock.py                # Add Sina to sources
```

### Files to Reference
```
src/markets/sources/base.py    # DataSource interface
src/markets/sources/yfinance_source.py  # Reference implementation
src/data/models.py             # CompanyNews, Price, FinancialMetrics
```

---

## Chunk 1: Phase 1 - NewsNowSource Implementation

### Task 1.1: Create NewsNowSource Base Structure

**Files:**
- Create: `src/markets/sources/newsnow_source.py`
- Test: `tests/markets/sources/test_newsnow_source.py`

- [x] **Step 1: Write failing test for NewsNowSource initialization**

Create test file:

```python
# tests/markets/sources/test_newsnow_source.py
"""Tests for NewsNowSource."""
import pytest
from src.markets.sources.newsnow_source import NewsNowSource


class TestNewsNowSourceInit:
    def test_initialization(self):
        """Test NewsNowSource initializes correctly."""
        source = NewsNowSource()

        assert source.name == "NewsNow"
        assert source.supports_market("US")
        assert source.supports_market("CN")
        assert source.supports_market("HK")
```

- [x] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/markets/sources/test_newsnow_source.py::TestNewsNowSourceInit::test_initialization -v
```

Expected: `ModuleNotFoundError: No module named 'src.markets.sources.newsnow_source'`

- [x] **Step 3: Create NewsNowSource with minimal implementation**

```python
# src/markets/sources/newsnow_source.py
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
```

- [x] **Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/markets/sources/test_newsnow_source.py::TestNewsNowSourceInit::test_initialization -v
```

Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/markets/sources/newsnow_source.py tests/markets/sources/test_newsnow_source.py
git commit -m "feat: add NewsNowSource base structure

- Create NewsNowSource class implementing DataSource interface
- Support all markets (US/CN/HK)
- Add basic test for initialization

Part of Phase 1: NewsNow implementation"
```

---

### Task 1.2: Implement NewsNow News Fetching

**Files:**
- Modify: `src/markets/sources/newsnow_source.py`
- Modify: `tests/markets/sources/test_newsnow_source.py`

- [x] **Step 1: Write failing test for news fetching**

```python
# tests/markets/sources/test_newsnow_source.py
import requests_mock


class TestNewsNowSourceNewsFetching:
    def test_get_company_news_success(self):
        """Test successful news fetching."""
        source = NewsNowSource()

        # Mock response
        with requests_mock.Mocker() as m:
            m.get(
                "https://newsnow.busiyi.world/api/s?id=cls",
                json={
                    "items": [
                        {
                            "id": "1",
                            "title": "Apple AAPL reports Q1 earnings",
                            "url": "https://example.com/1",
                            "publish_time": "2024-03-15T10:00:00Z"
                        },
                        {
                            "id": "2",
                            "title": "Market update for today",
                            "url": "https://example.com/2",
                            "publish_time": "2024-03-15T09:00:00Z"
                        }
                    ]
                }
            )
            m.get("https://newsnow.busiyi.world/api/s?id=wallstreetcn", json={"items": []})
            m.get("https://newsnow.busiyi.world/api/s?id=xueqiu", json={"items": []})

            news = source.get_company_news("AAPL", "2024-03-15", limit=10)

        # Should filter to only AAPL-related news
        assert len(news) == 1
        assert "AAPL" in news[0]["title"]
        assert news[0]["ticker"] == "AAPL"
        assert "date" in news[0]
        assert "title" in news[0]
        assert "url" in news[0]
        assert "source" in news[0]

    def test_get_company_news_no_matches(self):
        """Test when no news matches ticker."""
        source = NewsNowSource()

        with requests_mock.Mocker() as m:
            m.get(
                "https://newsnow.busiyi.world/api/s?id=cls",
                json={
                    "items": [
                        {"id": "1", "title": "Unrelated news", "url": "https://example.com/1"}
                    ]
                }
            )
            m.get("https://newsnow.busiyi.world/api/s?id=wallstreetcn", json={"items": []})
            m.get("https://newsnow.busiyi.world/api/s?id=xueqiu", json={"items": []})

            news = source.get_company_news("AAPL", "2024-03-15", limit=10)

        assert len(news) == 0

    def test_cache_mechanism(self):
        """Test that results are cached."""
        source = NewsNowSource()

        with requests_mock.Mocker() as m:
            m.get(
                "https://newsnow.busiyi.world/api/s?id=cls",
                json={"items": [{"id": "1", "title": "AAPL news", "url": "https://example.com/1"}]}
            )
            m.get("https://newsnow.busiyi.world/api/s?id=wallstreetcn", json={"items": []})
            m.get("https://newsnow.busiyi.world/api/s?id=xueqiu", json={"items": []})

            # First call
            news1 = source.get_company_news("AAPL", "2024-03-15", limit=10)

            # Second call should use cache (no new requests)
            news2 = source.get_company_news("AAPL", "2024-03-15", limit=10)

        assert news1 == news2
        # Verify only 3 requests were made (one per source)
        assert m.call_count == 3
```

- [x] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/markets/sources/test_newsnow_source.py::TestNewsNowSourceNewsFetching -v
```

Expected: FAIL - methods not implemented

- [x] **Step 3: Implement news fetching logic**

```python
# src/markets/sources/newsnow_source.py
import requests


class NewsNowSource(DataSource):
    # ... existing code ...

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
        for source_id in ["cls", "wallstreetcn", "xueqiu"]:
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
```

- [x] **Step 4: Add requests-mock to dependencies**

```bash
poetry add --group dev requests-mock
```

- [x] **Step 5: Run tests to verify they pass**

```bash
poetry run pytest tests/markets/sources/test_newsnow_source.py -v
```

Expected: All tests PASS

- [x] **Step 6: Commit**

```bash
git add src/markets/sources/newsnow_source.py tests/markets/sources/test_newsnow_source.py pyproject.toml poetry.lock
git commit -m "feat: implement NewsNow news fetching with caching

- Add news fetching from 3 sources (财联社/华尔街见闻/雪球)
- Implement keyword filtering by ticker
- Add 5-minute cache to reduce API calls
- Add comprehensive tests with mocking

Part of Phase 1: NewsNow implementation"
```

---

### Task 1.3: Integrate NewsNow into USStockAdapter

**Files:**
- Modify: `src/markets/us_stock.py`
- Test: `tests/markets/test_us_stock_adapter.py`

- [x] **Step 1: Write failing test for NewsNow integration**

```python
# tests/markets/test_us_stock_adapter.py
import pytest
from src.markets.us_stock import USStockAdapter


class TestUSStockNewsNowIntegration:
    def test_get_company_news_uses_newsnow_first(self, requests_mock):
        """Test that NewsNow is used as primary news source."""
        adapter = USStockAdapter()

        # Mock NewsNow API
        requests_mock.get(
            "https://newsnow.busiyi.world/api/s?id=cls",
            json={
                "items": [
                    {
                        "id": "1",
                        "title": "AAPL reports earnings",
                        "url": "https://example.com/1",
                        "publish_time": "2024-03-15T10:00:00Z"
                    }
                ]
            }
        )
        requests_mock.get("https://newsnow.busiyi.world/api/s?id=wallstreetcn", json={"items": []})
        requests_mock.get("https://newsnow.busiyi.world/api/s?id=xueqiu", json={"items": []})

        news = adapter.get_company_news("AAPL", "2024-03-15", limit=10)

        # Should get news from NewsNow
        assert len(news) > 0
        assert news[0]["source"] == "NewsNow"
```

- [x] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/markets/test_us_stock_adapter.py::TestUSStockNewsNowIntegration -v
```

Expected: FAIL - NewsNow not integrated yet

- [x] **Step 3: Update USStockAdapter to use NewsNow**

```python
# src/markets/us_stock.py
from src.markets.sources.newsnow_source import NewsNowSource


class USStockAdapter(MarketAdapter):
    def __init__(self, validator: Optional[DataValidator] = None):
        """
        Initialize US stock adapter.

        Args:
            validator: Data validator instance (optional)
        """
        super().__init__(
            market="US",
            data_sources=[],
            validator=validator,
        )

        # Initialize news sources with fallback chain
        self.news_sources = [
            NewsNowSource(),  # Free, primary source
            # Financial Datasets API handled by api.py as fallback
        ]

    def get_company_news(self, ticker: str, end_date: str, limit: int) -> List[Dict]:
        """
        Get company news with fallback chain.

        Fallback order:
        1. NewsNow (free, no rate limit)
        2. Financial Datasets API (via api.py, paid, has rate limit)

        Args:
            ticker: Stock ticker
            end_date: End date (YYYY-MM-DD)
            limit: Maximum number of news items

        Returns:
            List of news dictionaries
        """
        # Try free sources first
        for source in self.news_sources:
            try:
                news = source.get_company_news(ticker, end_date, limit=limit)
                if news:
                    logger.info(f"[USStock] ✓ Got {len(news)} news from {source.name}")
                    return news
                else:
                    logger.info(f"[USStock] ⚠ {source.name} returned no data")
            except Exception as e:
                logger.warning(f"[USStock] ✗ {source.name} failed: {e}")
                continue

        # All free sources failed, fallback to Financial API via api.py
        logger.warning(f"[USStock] All free news sources failed, using Financial API fallback")
        try:
            news = api.get_company_news(ticker, end_date, limit=limit)
            return [n.model_dump() for n in news]
        except Exception as e:
            logger.error(f"[USStock] Financial API also failed: {e}")
            return []
```

- [x] **Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/markets/test_us_stock_adapter.py::TestUSStockNewsNowIntegration -v
```

Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/markets/us_stock.py tests/markets/test_us_stock_adapter.py
git commit -m "feat: integrate NewsNow into USStockAdapter

- Add NewsNow as primary news source for US stocks
- Implement fallback to Financial API
- Add integration test

Part of Phase 1: NewsNow implementation"
```

---

### Task 1.4: Integrate NewsNow into CNStockAdapter

**Files:**
- Modify: `src/markets/cn_stock.py`
- Test: `tests/markets/test_cn_stock_adapter.py`

- [x] **Step 1: Read current CNStockAdapter implementation**

```bash
cat src/markets/cn_stock.py
```

- [x] **Step 2: Write failing test for NewsNow integration**

```python
# tests/markets/test_cn_stock_adapter.py
import pytest
from src.markets.cn_stock import CNStockAdapter


class TestCNStockNewsNowIntegration:
    def test_get_company_news_uses_newsnow_first(self, requests_mock):
        """Test that NewsNow is used as primary news source."""
        adapter = CNStockAdapter()

        # Mock NewsNow API (财联社 for CN stocks)
        requests_mock.get(
            "https://newsnow.busiyi.world/api/s?id=cls",
            json={
                "items": [
                    {
                        "id": "1",
                        "title": "贵州茅台 600519 发布财报",
                        "url": "https://example.com/1",
                        "publish_time": "2024-03-15T10:00:00Z"
                    }
                ]
            }
        )
        requests_mock.get("https://newsnow.busiyi.world/api/s?id=wallstreetcn", json={"items": []})
        requests_mock.get("https://newsnow.busiyi.world/api/s?id=xueqiu", json={"items": []})

        news = adapter.get_company_news("600519.SH", "2024-03-15", limit=10)

        # Should get news from NewsNow
        assert len(news) > 0
        assert news[0]["source"] == "NewsNow"
```

- [x] **Step 3: Run test to verify it fails**

```bash
poetry run pytest tests/markets/test_cn_stock_adapter.py::TestCNStockNewsNowIntegration -v
```

Expected: FAIL

- [x] **Step 4: Update CNStockAdapter to use NewsNow**

Add NewsNow to news sources in `src/markets/cn_stock.py`:

```python
from src.markets.sources.newsnow_source import NewsNowSource

class CNStockAdapter(MarketAdapter):
    def __init__(self, validator: Optional[DataValidator] = None):
        # ... existing initialization ...

        # Add NewsNow as primary news source
        self.news_sources = [
            NewsNowSource(),  # Free, primary
            # Existing sources as fallback
        ]
```

- [x] **Step 5: Run test to verify it passes**

```bash
poetry run pytest tests/markets/test_cn_stock_adapter.py::TestCNStockNewsNowIntegration -v
```

Expected: PASS

- [x] **Step 6: Commit**

```bash
git add src/markets/cn_stock.py tests/markets/test_cn_stock_adapter.py
git commit -m "feat: integrate NewsNow into CNStockAdapter

- Add NewsNow as primary news source for CN stocks
- Prioritize 财联社 for Chinese market news

Part of Phase 1: NewsNow implementation"
```

---

### Task 1.5: Integrate NewsNow into HKStockAdapter

**Files:**
- Modify: `src/markets/hk_stock.py`
- Test: `tests/markets/test_hk_stock_adapter.py`

- [x] **Step 1: Write failing test**

```python
# tests/markets/test_hk_stock_adapter.py
import pytest
from src.markets.hk_stock import HKStockAdapter


class TestHKStockNewsNowIntegration:
    def test_get_company_news_uses_newsnow_first(self, requests_mock):
        """Test that NewsNow is used as primary news source."""
        adapter = HKStockAdapter()

        # Mock NewsNow API
        requests_mock.get(
            "https://newsnow.busiyi.world/api/s?id=wallstreetcn",
            json={
                "items": [
                    {
                        "id": "1",
                        "title": "腾讯 0700 股价上涨",
                        "url": "https://example.com/1",
                        "publish_time": "2024-03-15T10:00:00Z"
                    }
                ]
            }
        )
        requests_mock.get("https://newsnow.busiyi.world/api/s?id=cls", json={"items": []})
        requests_mock.get("https://newsnow.busiyi.world/api/s?id=xueqiu", json={"items": []})

        news = adapter.get_company_news("0700.HK", "2024-03-15", limit=10)

        assert len(news) > 0
        assert news[0]["source"] == "NewsNow"
```

- [x] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/markets/test_hk_stock_adapter.py::TestHKStockNewsNowIntegration -v
```

- [x] **Step 3: Update HKStockAdapter**

Similar to CN/US adapters, add NewsNow to `src/markets/hk_stock.py`

- [x] **Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/markets/test_hk_stock_adapter.py::TestHKStockNewsNowIntegration -v
```

- [x] **Step 5: Commit**

```bash
git add src/markets/hk_stock.py tests/markets/test_hk_stock_adapter.py
git commit -m "feat: integrate NewsNow into HKStockAdapter

- Add NewsNow as primary news source for HK stocks
- Complete Phase 1: NewsNow integration across all markets"
```

---

### Task 1.6: End-to-End Testing for Phase 1

**Files:**
- Test: `tests/integration/test_newsnow_e2e.py`

- [x] **Step 1: Write end-to-end test**

```python
# tests/integration/test_newsnow_e2e.py
"""End-to-end tests for NewsNow integration."""
import pytest
from src.tools import api


class TestNewsNowE2E:
    @pytest.mark.integration
    def test_get_news_no_rate_limit(self):
        """Test that getting news doesn't trigger rate limits."""
        # Simulate multiple analyst requests
        tickers = ["AAPL", "MSFT", "GOOGL"]

        for ticker in tickers:
            news = api.get_company_news(ticker, "2024-03-15", limit=5)
            # Should succeed without 429 errors
            assert isinstance(news, list)

    @pytest.mark.integration
    def test_cache_effectiveness(self):
        """Test that cache reduces API calls."""
        from src.data.cache import get_cache
        cache = get_cache()

        # Clear cache
        cache.clear()

        # First call
        news1 = api.get_company_news("AAPL", "2024-03-15", limit=5)

        # Second call should hit cache
        news2 = api.get_company_news("AAPL", "2024-03-15", limit=5)

        stats = cache.get_stats()
        assert stats['hits'] > 0
```

- [x] **Step 2: Run integration tests**

```bash
poetry run pytest tests/integration/test_newsnow_e2e.py -v -m integration
```

- [x] **Step 3: Verify no rate limit errors in logs**

Check that no 429 errors appear

- [x] **Step 4: Commit**

```bash
git add tests/integration/test_newsnow_e2e.py
git commit -m "test: add end-to-end tests for NewsNow integration

- Test multiple requests don't trigger rate limits
- Verify cache effectiveness
- Complete Phase 1 testing"
```

---

## Chunk 2: Phase 2 - SinaFinanceSource Implementation

### Task 2.1: Create SinaFinanceSource Base Structure

**Files:**
- Create: `src/markets/sources/sina_finance_source.py`
- Test: `tests/markets/sources/test_sina_finance_source.py`

- [x] **Step 1: Write failing test for initialization**

```python
# tests/markets/sources/test_sina_finance_source.py
"""Tests for SinaFinanceSource."""
import pytest
from src.markets.sources.sina_finance_source import SinaFinanceSource


class TestSinaFinanceSourceInit:
    def test_initialization(self):
        """Test SinaFinanceSource initializes correctly."""
        source = SinaFinanceSource()

        assert source.name == "SinaFinance"
        assert source.supports_market("US")
        assert source.supports_market("CN")
        assert source.supports_market("HK")

    def test_ticker_format_conversion(self):
        """Test ticker format conversion."""
        source = SinaFinanceSource()

        # CN market
        assert source._to_sina_symbol("600000.SH", "CN") == "sh600000"
        assert source._to_sina_symbol("000001.SZ", "CN") == "sz000001"

        # HK market
        assert source._to_sina_symbol("0700.HK", "HK") == "hk00700"

        # US market
        assert source._to_sina_symbol("AAPL", "US") == "gb_aapl"
```

- [x] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/markets/sources/test_sina_finance_source.py::TestSinaFinanceSourceInit -v
```

- [x] **Step 3: Create SinaFinanceSource with ticker conversion**

```python
# src/markets/sources/sina_finance_source.py
"""Sina Finance data source for CN/HK/US markets."""
import logging
import re
import time
import random
from typing import Dict, List, Optional
from datetime import datetime

import requests

from src.markets.sources.base import DataSource

logger = logging.getLogger(__name__)


class SinaFinanceSource(DataSource):
    """
    Sina Finance data source.

    Features:
    - Supports CN/HK/US three markets
    - Real-time quotes with <1 minute delay
    - High stability, rare rate limiting
    - Direct HTTP calls, no SDK required
    """

    QUOTE_API = "https://hq.sinajs.cn/list={symbol}"
    KLINE_API_CN = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"
    KLINE_API_HK = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

    def __init__(self):
        super().__init__("SinaFinance")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn/'
        })

    def supports_market(self, market: str) -> bool:
        """Sina Finance supports CN/HK/US markets."""
        return market.upper() in ["US", "CN", "HK"]

    def _detect_market(self, ticker: str) -> str:
        """
        Detect market from ticker format.

        Args:
            ticker: Stock ticker

        Returns:
            Market code: "CN", "HK", or "US"
        """
        ticker_upper = ticker.upper()
        if '.SH' in ticker_upper or '.SZ' in ticker_upper:
            return "CN"
        elif '.HK' in ticker_upper:
            return "HK"
        else:
            return "US"

    def _to_sina_symbol(self, ticker: str, market: str) -> str:
        """
        Convert ticker to Sina Finance format.

        Rules:
        - CN: 600000.SH → sh600000, 000001.SZ → sz000001
        - HK: 0700.HK → hk00700
        - US: AAPL → gb_aapl

        Args:
            ticker: Original ticker
            market: Market code

        Returns:
            Sina format ticker
        """
        code = ticker.split('.')[0]

        if market == "CN":
            prefix = "sh" if ".SH" in ticker.upper() else "sz"
            return f"{prefix}{code}"
        elif market == "HK":
            return f"hk{code.zfill(5)}"
        else:  # US
            return f"gb_{code.lower()}"

    def get_prices(
        self, ticker: str, start_date: str, end_date: str
    ) -> List[Dict]:
        """
        Get price data from Sina Finance.

        This is a placeholder that will be implemented in next task.
        """
        return []

    def get_financial_metrics(
        self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10
    ) -> Optional[Dict]:
        """
        Get basic financial metrics from Sina Finance.

        Note: Sina only provides basic metrics (PE, PB, market cap).
        """
        return None

    def get_company_news(
        self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """Sina Finance does not provide news data."""
        return []
```

- [x] **Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/markets/sources/test_sina_finance_source.py::TestSinaFinanceSourceInit -v
```

- [x] **Step 5: Commit**

```bash
git add src/markets/sources/sina_finance_source.py tests/markets/sources/test_sina_finance_source.py
git commit -m "feat: add SinaFinanceSource base structure

- Create SinaFinanceSource class supporting CN/HK/US markets
- Implement ticker format conversion
- Add tests for initialization and format conversion

Part of Phase 2: Sina Finance implementation"
```

---

### Task 2.2: Implement Sina Finance Price Fetching for CN Market

**Files:**
- Modify: `src/markets/sources/sina_finance_source.py`
- Modify: `tests/markets/sources/test_sina_finance_source.py`

- [x] **Step 1: Write failing test for CN price fetching**

```python
# tests/markets/sources/test_sina_finance_source.py
class TestSinaFinancePricesCN:
    def test_get_prices_cn_stock(self, requests_mock):
        """Test fetching CN stock prices."""
        source = SinaFinanceSource()

        # Mock Sina CN K-line API
        requests_mock.get(
            re.compile(r'https://quotes\.sina\.cn/cn/api/json_v2\.php.*'),
            json=[
                {
                    'day': '2024-01-01',
                    'open': '100.00',
                    'close': '105.00',
                    'high': '106.00',
                    'low': '99.00',
                    'volume': '1000000'
                },
                {
                    'day': '2024-01-02',
                    'open': '105.00',
                    'close': '107.00',
                    'high': '108.00',
                    'low': '104.00',
                    'volume': '1200000'
                }
            ]
        )

        prices = source.get_prices("600000.SH", "2024-01-01", "2024-01-02")

        assert len(prices) == 2
        assert prices[0]["open"] == 100.0
        assert prices[0]["close"] == 105.0
        assert "time" in prices[0]
```

- [x] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/markets/sources/test_sina_finance_source.py::TestSinaFinancePricesCN -v
```

- [x] **Step 3: Implement CN price fetching**

```python
# src/markets/sources/sina_finance_source.py
class SinaFinanceSource(DataSource):
    # ... existing code ...

    def get_prices(
        self, ticker: str, start_date: str, end_date: str, max_retries: int = 3
    ) -> List[Dict]:
        """
        Get price data from Sina Finance.

        Args:
            ticker: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            max_retries: Maximum retry attempts

        Returns:
            List of price dictionaries
        """
        market = self._detect_market(ticker)
        sina_symbol = self._to_sina_symbol(ticker, market)

        for attempt in range(max_retries):
            try:
                # Add delay to avoid rate limiting
                if attempt > 0:
                    delay = 2 ** attempt
                    self.logger.info(f"[SinaFinance] Retry {attempt+1}, waiting {delay}s")
                    time.sleep(delay)
                else:
                    time.sleep(random.uniform(0.5, 1.5))

                # Route to market-specific implementation
                if market == "CN":
                    prices = self._get_cn_prices(sina_symbol, start_date, end_date)
                elif market == "HK":
                    prices = self._get_hk_prices(sina_symbol, start_date, end_date)
                else:  # US
                    prices = self._get_us_prices(sina_symbol, start_date, end_date)

                if prices:
                    self.logger.info(f"[SinaFinance] ✓ Retrieved {len(prices)} prices for {ticker}")
                    return prices
                else:
                    self.logger.warning(f"[SinaFinance] No price data for {ticker}")
                    return []

            except Exception as e:
                self.logger.warning(f"[SinaFinance] Attempt {attempt+1} failed: {e}")
                if attempt == max_retries - 1:
                    self.logger.error(f"[SinaFinance] All retries failed for {ticker}")
                    return []

        return []

    def _get_cn_prices(self, sina_symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Get CN stock prices.

        Args:
            sina_symbol: Sina format symbol (e.g., 'sh600000')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of price dictionaries
        """
        # Calculate number of days
        from datetime import datetime
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        days = (end_dt - start_dt).days
        datalen = min(days + 10, 500)  # Add buffer, max 500

        params = {
            'symbol': sina_symbol,
            'scale': '240',  # Daily K-line
            'ma': 'no',
            'datalen': str(datalen)
        }

        response = self.session.get(self.KLINE_API_CN, params=params, timeout=15)
        response.raise_for_status()

        data = response.json()
        if not data or not isinstance(data, list):
            return []

        prices = []
        for item in data:
            try:
                prices.append({
                    'open': float(item['open']),
                    'close': float(item['close']),
                    'high': float(item['high']),
                    'low': float(item['low']),
                    'volume': int(float(item['volume'])),
                    'time': f"{item['day']}T00:00:00Z"
                })
            except (KeyError, ValueError) as e:
                self.logger.warning(f"Failed to parse CN price data: {e}")
                continue

        return prices

    def _get_hk_prices(self, sina_symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Get HK stock prices.

        Implementation placeholder - will be added in next task.
        """
        return []

    def _get_us_prices(self, sina_symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Get US stock prices.

        Implementation placeholder - will be added in next task.
        """
        return []
```

- [x] **Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/markets/sources/test_sina_finance_source.py::TestSinaFinancePricesCN -v
```

- [x] **Step 5: Commit**

```bash
git add src/markets/sources/sina_finance_source.py tests/markets/sources/test_sina_finance_source.py
git commit -m "feat: implement Sina Finance CN stock price fetching

- Add CN K-line data fetching via Sina API
- Implement retry logic with exponential backoff
- Add tests for CN market

Part of Phase 2: Sina Finance implementation"
```

---

### Task 2.3: Implement Sina Finance Price Fetching for HK Market

**Files:**
- Modify: `src/markets/sources/sina_finance_source.py`
- Modify: `tests/markets/sources/test_sina_finance_source.py`

- [x] **Step 1: Write failing test for HK price fetching**

```python
# tests/markets/sources/test_sina_finance_source.py
class TestSinaFinancePricesHK:
    def test_get_prices_hk_stock(self, requests_mock):
        """Test fetching HK stock prices."""
        source = SinaFinanceSource()

        # Mock Tencent HK API (used by Sina for HK stocks)
        requests_mock.get(
            re.compile(r'https://web\.ifzq\.gtimg\.cn/appstock/app/fqkline/get.*'),
            json={
                'code': 0,
                'data': {
                    'hk00700': {
                        'day': [
                            ['2024-01-01', '100.00', '105.00', '106.00', '99.00', '1000000'],
                            ['2024-01-02', '105.00', '107.00', '108.00', '104.00', '1200000']
                        ]
                    }
                }
            }
        )

        prices = source.get_prices("0700.HK", "2024-01-01", "2024-01-02")

        assert len(prices) == 2
        assert prices[0]["open"] == 100.0
```

- [x] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/markets/sources/test_sina_finance_source.py::TestSinaFinancePricesHK -v
```

- [x] **Step 3: Implement HK price fetching**

```python
# src/markets/sources/sina_finance_source.py
import json


class SinaFinanceSource(DataSource):
    # ... existing code ...

    def _get_hk_prices(self, sina_symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Get HK stock prices.

        Uses Tencent API which Sina redirects to for HK stocks.

        Args:
            sina_symbol: Sina format symbol (e.g., 'hk00700')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of price dictionaries
        """
        # Calculate data length
        from datetime import datetime
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        days = (end_dt - start_dt).days
        datalen = min(days + 10, 500)

        params = {
            'param': f'{sina_symbol},day,,,{datalen},qfq'
        }

        response = self.session.get(self.KLINE_API_HK, params=params, timeout=15)
        response.raise_for_status()

        # Parse JSON from response (may have extra characters)
        text = response.text
        start_idx = text.find('{')
        if start_idx == -1:
            return []

        data = json.loads(text[start_idx:])

        if data.get('code') != 0:
            return []

        klines = data.get('data', {}).get(sina_symbol, {}).get('day', [])
        if not klines:
            return []

        prices = []
        for item in klines:
            if not isinstance(item, list) or len(item) < 6:
                continue

            try:
                prices.append({
                    'open': float(item[1]),
                    'close': float(item[2]),
                    'high': float(item[3]),
                    'low': float(item[4]),
                    'volume': int(float(item[5])),
                    'time': f"{item[0]}T00:00:00Z"
                })
            except (ValueError, IndexError) as e:
                self.logger.warning(f"Failed to parse HK price data: {e}")
                continue

        return prices
```

- [x] **Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/markets/sources/test_sina_finance_source.py::TestSinaFinancePricesHK -v
```

- [x] **Step 5: Commit**

```bash
git add src/markets/sources/sina_finance_source.py tests/markets/sources/test_sina_finance_source.py
git commit -m "feat: implement Sina Finance HK stock price fetching

- Add HK K-line data fetching via Tencent API
- Handle JSON parsing with extra characters
- Add tests for HK market

Part of Phase 2: Sina Finance implementation"
```

---

I'll continue with the remaining tasks, but this is getting quite long. Let me save this chunk and prepare for review.

