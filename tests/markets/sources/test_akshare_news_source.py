"""Tests for AKShareNewsSource."""
import pytest
from datetime import datetime, timedelta

from src.markets.sources.akshare_news_source import AKShareNewsSource


@pytest.fixture
def news_source():
    """Create AKShareNewsSource instance."""
    return AKShareNewsSource()


class TestAKShareNewsSource:
    """Test AKShareNewsSource functionality."""

    def test_supports_market(self, news_source):
        """Test market support."""
        assert news_source.supports_market("CN")
        assert news_source.supports_market("HK")
        assert not news_source.supports_market("US")

    def test_get_prices_not_supported(self, news_source):
        """Test that price data is not supported."""
        prices = news_source.get_prices("00700", "2024-01-01", "2024-01-31")
        assert prices == []

    def test_get_financial_metrics_not_supported(self, news_source):
        """Test that financial metrics are not supported."""
        metrics = news_source.get_financial_metrics("00700", "2024-01-31")
        assert metrics is None

    def test_get_search_terms(self, news_source):
        """Test search term generation."""
        # Test with known ticker
        terms = news_source._get_search_terms("00700")
        assert "700" in terms  # Clean ticker
        assert "00700" in terms  # Original ticker
        assert "腾讯" in terms  # Company name

        # Test with unknown ticker
        terms = news_source._get_search_terms("99999")
        assert "99999" in terms
        assert "腾讯" not in terms  # No company name mapping

    def test_deduplicate_news(self, news_source):
        """Test news deduplication."""
        news_list = [
            {"title": "腾讯发布财报", "content": "内容1"},
            {"title": "腾讯发布财报", "content": "内容2"},  # Duplicate
            {"title": "阿里巴巴财报", "content": "内容3"},
        ]

        deduplicated = news_source._deduplicate_news(news_list)
        assert len(deduplicated) == 2

        # Check that titles are unique
        titles = [news["title"] for news in deduplicated]
        assert len(titles) == len(set(titles))

    def test_convert_to_company_news(self, news_source):
        """Test news format conversion."""
        raw_news = [
            {
                "title": "腾讯发布财报",  # Include company name for relevance check
                "content": "测试内容包含腾讯",
                "date": "2024-01-15 10:30:00",
                "source": "东方财富",
                "url": "http://example.com/news1",
                "keyword": "腾讯",
            }
        ]

        converted = news_source._convert_to_company_news(raw_news, "00700")
        assert len(converted) == 1

        news = converted[0]
        assert news["ticker"] == "00700"
        assert news["title"] == "腾讯发布财报"
        assert news["source"] == "东方财富"
        assert news["url"] == "http://example.com/news1"
        assert "2024-01-15" in news["date"]

    @pytest.mark.integration
    def test_get_company_news_tencent(self, news_source):
        """Integration test: Get news for Tencent (00700)."""
        end_date = datetime.now().strftime("%Y-%m-%d")
        news = news_source.get_company_news("00700", end_date, limit=10)

        assert isinstance(news, list)
        if news:  # News may not always be available
            assert len(news) <= 10

            # Check first news item structure
            first_news = news[0]
            assert "ticker" in first_news
            assert "title" in first_news
            assert "date" in first_news
            assert "source" in first_news
            assert "url" in first_news

            assert first_news["ticker"] == "00700"
            print(f"\n✓ Retrieved {len(news)} news items")
            print(f"  First news: {first_news['title'][:50]}...")

    @pytest.mark.integration
    def test_get_company_news_alibaba(self, news_source):
        """Integration test: Get news for Alibaba (09988)."""
        end_date = datetime.now().strftime("%Y-%m-%d")
        news = news_source.get_company_news("09988", end_date, limit=10)

        assert isinstance(news, list)
        if news:
            assert len(news) <= 10
            print(f"\n✓ Retrieved {len(news)} news items for Alibaba")

    @pytest.mark.integration
    def test_news_caching(self, news_source):
        """Test that news caching works."""
        end_date = datetime.now().strftime("%Y-%m-%d")

        # First call - should fetch from API
        news1 = news_source.get_company_news("00700", end_date, limit=5)

        # Second call - should use cache
        news2 = news_source.get_company_news("00700", end_date, limit=5)

        # Results should be identical (from cache)
        assert news1 == news2

    @pytest.mark.integration
    def test_get_company_news_cn_stock(self, news_source):
        """Integration test: Get news for CN stock (e.g., 贵州茅台 600519)."""
        end_date = datetime.now().strftime("%Y-%m-%d")
        news = news_source.get_company_news("600519", end_date, limit=10)

        assert isinstance(news, list)
        # CN stocks should also work
        if news:
            print(f"\n✓ Retrieved {len(news)} news items for CN stock")
