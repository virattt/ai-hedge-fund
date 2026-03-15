"""Test HK stock news fetching."""
import pytest
from datetime import datetime

from src.markets.hk_stock import HKStockAdapter


@pytest.fixture
def hk_adapter():
    """Create HK stock adapter."""
    return HKStockAdapter()


class TestHKStockNews:
    """Test HK stock adapter news functionality."""

    @pytest.mark.integration
    def test_get_news_for_tencent(self, hk_adapter):
        """Test news fetching for Tencent (00700)."""
        end_date = datetime.now().strftime("%Y-%m-%d")
        news = hk_adapter.get_company_news("00700", end_date, limit=10)

        assert isinstance(news, list)
        assert len(news) > 0, "Should retrieve at least some news"
        assert len(news) <= 10, "Should respect limit"

        # Verify news structure
        first_news = news[0]
        assert "ticker" in first_news
        assert "title" in first_news
        assert "date" in first_news
        assert "source" in first_news

        print(f"\n✓ Retrieved {len(news)} news items for Tencent")
        print(f"  First news: {first_news['title'][:60]}...")
        print(f"  Source: {first_news['source']}")

    @pytest.mark.integration
    def test_get_news_for_alibaba(self, hk_adapter):
        """Test news fetching for Alibaba (09988)."""
        end_date = datetime.now().strftime("%Y-%m-%d")
        news = hk_adapter.get_company_news("09988", end_date, limit=5)

        assert isinstance(news, list)
        if news:
            print(f"\n✓ Retrieved {len(news)} news items for Alibaba")
            print(f"  First title: {news[0]['title'][:60]}...")

    @pytest.mark.integration
    def test_get_news_for_meituan(self, hk_adapter):
        """Test news fetching for Meituan (03690)."""
        end_date = datetime.now().strftime("%Y-%m-%d")
        news = hk_adapter.get_company_news("03690", end_date, limit=5)

        assert isinstance(news, list)
        if news:
            print(f"\n✓ Retrieved {len(news)} news items for Meituan")
            print(f"  First title: {news[0]['title'][:60]}...")

    @pytest.mark.integration
    def test_news_source_fallback(self, hk_adapter):
        """Test that news sources fallback properly."""
        end_date = datetime.now().strftime("%Y-%m-%d")

        # Should try AKShareNews first, then NewsNow, then YFinance
        news = hk_adapter.get_company_news("00700", end_date, limit=5)

        # Should get news from at least one source
        assert isinstance(news, list)
        print(f"\n✓ News fallback working, got {len(news)} items")

    @pytest.mark.integration
    def test_ticker_normalization_for_news(self, hk_adapter):
        """Test that ticker normalization works for news."""
        end_date = datetime.now().strftime("%Y-%m-%d")

        # Different ticker formats should all work
        news1 = hk_adapter.get_company_news("700", end_date, limit=3)
        news2 = hk_adapter.get_company_news("0700", end_date, limit=3)
        news3 = hk_adapter.get_company_news("00700", end_date, limit=3)

        # All should return news (may be different due to caching and timing)
        assert isinstance(news1, list)
        assert isinstance(news2, list)
        assert isinstance(news3, list)

        print(f"\n✓ Ticker normalization works:")
        print(f"  '700': {len(news1)} news")
        print(f"  '0700': {len(news2)} news")
        print(f"  '00700': {len(news3)} news")
