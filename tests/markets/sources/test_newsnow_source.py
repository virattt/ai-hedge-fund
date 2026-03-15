"""Tests for NewsNowSource."""
import pytest
import requests_mock
from src.markets.sources.newsnow_source import NewsNowSource


class TestNewsNowSourceInit:
    def test_initialization(self):
        """Test NewsNowSource initializes correctly."""
        source = NewsNowSource()

        assert source.name == "NewsNow"
        assert source.supports_market("US")
        assert source.supports_market("CN")
        assert source.supports_market("HK")


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
