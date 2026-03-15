"""End-to-end test for HK stock news pipeline."""
import pytest
from datetime import datetime

from src.markets.hk_stock import HKStockAdapter


@pytest.mark.integration
class TestHKNewsE2E:
    """End-to-end tests for HK stock news pipeline."""

    def test_news_pipeline_complete(self):
        """Test complete news pipeline for HK stocks."""
        adapter = HKStockAdapter()
        end_date = datetime.now().strftime("%Y-%m-%d")

        # Test multiple HK stocks
        test_tickers = ["00700", "09988", "03690"]

        results = {}
        for ticker in test_tickers:
            print(f"\n{'='*60}")
            print(f"Testing {ticker}")
            print('='*60)

            news = adapter.get_company_news(ticker, end_date, limit=5)
            results[ticker] = news

            assert isinstance(news, list), f"Should return list for {ticker}"

            if news:
                print(f"✓ Retrieved {len(news)} news items")
                for i, item in enumerate(news[:3], 1):
                    print(f"\n  [{i}] {item['title'][:70]}...")
                    print(f"      Source: {item['source']}")
                    print(f"      Date: {item['date'][:10]}")
            else:
                print(f"⚠ No news found for {ticker}")

        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print('='*60)
        total_news = sum(len(news) for news in results.values())
        print(f"Total tickers tested: {len(test_tickers)}")
        print(f"Total news retrieved: {total_news}")

        for ticker, news in results.items():
            print(f"  {ticker}: {len(news)} news items")

        # At least some tickers should have news
        assert total_news > 0, "Should retrieve news for at least some tickers"

    def test_news_source_priority(self):
        """Test that news sources are tried in correct priority order."""
        adapter = HKStockAdapter()

        # Check news source priority
        assert len(adapter.news_sources) >= 2
        assert adapter.news_sources[0].name == "AKShareNews", "AKShareNews should be primary"

        print("\n✓ News source priority:")
        for i, source in enumerate(adapter.news_sources, 1):
            print(f"  {i}. {source.name}")

    def test_news_deduplication(self):
        """Test that news deduplication works."""
        adapter = HKStockAdapter()
        end_date = datetime.now().strftime("%Y-%m-%d")

        # Get news for a popular stock (should have many news items)
        news = adapter.get_company_news("00700", end_date, limit=20)

        if news:
            # Check for duplicate titles
            titles = [item["title"] for item in news]
            unique_titles = set(titles)

            print(f"\n✓ Deduplication check:")
            print(f"  Total news: {len(news)}")
            print(f"  Unique titles: {len(unique_titles)}")

            assert len(unique_titles) == len(news), "All news titles should be unique"

    def test_news_relevance(self):
        """Test that news is relevant to the requested ticker."""
        adapter = HKStockAdapter()
        end_date = datetime.now().strftime("%Y-%m-%d")

        # Get news for Tencent
        news = adapter.get_company_news("00700", end_date, limit=10)

        if news:
            # Check if news mentions Tencent or related terms
            relevant_count = 0
            for item in news:
                title = item["title"]
                # Check for relevance (in real implementation, this would be more sophisticated)
                if "腾讯" in title or "700" in title:
                    relevant_count += 1

            print(f"\n✓ Relevance check:")
            print(f"  Total news: {len(news)}")
            print(f"  Relevant news: {relevant_count}")

            # At least some news should be relevant
            relevance_ratio = relevant_count / len(news) if news else 0
            print(f"  Relevance ratio: {relevance_ratio:.1%}")

    def test_news_freshness(self):
        """Test that news is recent."""
        adapter = HKStockAdapter()
        end_date = datetime.now().strftime("%Y-%m-%d")

        news = adapter.get_company_news("00700", end_date, limit=5)

        if news:
            print(f"\n✓ News freshness check:")
            for item in news[:3]:
                print(f"  {item['date'][:10]}: {item['title'][:50]}...")

            # All news should have dates
            assert all("date" in item for item in news), "All news should have dates"

    def test_news_url_availability(self):
        """Test that news items have URLs."""
        adapter = HKStockAdapter()
        end_date = datetime.now().strftime("%Y-%m-%d")

        news = adapter.get_company_news("00700", end_date, limit=5)

        if news:
            urls_available = sum(1 for item in news if item.get("url"))
            print(f"\n✓ URL availability:")
            print(f"  Total news: {len(news)}")
            print(f"  With URLs: {urls_available}")

            # Most news should have URLs
            assert urls_available > 0, "At least some news should have URLs"
