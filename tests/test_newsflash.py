import pytest
from unittest.mock import Mock, patch

from src.tools.api import get_newsflash_news

SAMPLE_RESPONSE = {
    "count": 2,
    "events": [
        {
            "id": 101,
            "canonical_title": "Nvidia announces new data center GPU",
            "summary": "Nvidia unveiled its next-generation accelerator.",
            "category": "tech",
            "first_seen_at": "2026-07-23T15:00:00.000Z",
            "last_seen_at": "2026-07-23T18:00:00.000Z",
            "article_count": 4,
            "source_count": 3,
            "sources": ["reuters", "techcrunch", "theverge"],
            "corroboration": 3,
            "confidence": 1.0,
        },
        {
            "id": 102,
            "canonical_title": "Rumor: Nvidia eyeing acquisition",
            "summary": "A single outlet reports acquisition talks.",
            "category": "tech",
            "first_seen_at": "2026-07-23T16:00:00.000Z",
            "last_seen_at": "2026-07-23T16:00:00.000Z",
            "article_count": 1,
            "source_count": 1,
            "sources": ["someblog"],
            "corroboration": 1,
            "confidence": 0.3333333333333333,
        },
    ],
}


class TestGetNewsflashNews:
    """Test suite for the Newsflash news provider."""

    @patch('src.tools.api._cache')
    @patch('src.tools.api.requests.get')
    def test_maps_events_to_company_news(self, mock_get, mock_cache):
        """Events are mapped into CompanyNews with corroboration/confidence attached."""
        mock_cache.get_company_news.return_value = None

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_RESPONSE
        mock_get.return_value = mock_response

        result = get_newsflash_news("NVDA", end_date="2026-07-24")

        assert len(result) == 2
        assert result[0].ticker == "NVDA"
        assert result[0].title == "Nvidia announces new data center GPU"
        assert result[0].source == "reuters, techcrunch, theverge"
        assert result[0].date == "2026-07-23T15:00:00.000Z"
        assert result[0].url == "https://newsflash.sh/api/events/101"
        assert result[0].sentiment is None
        assert result[0].corroboration == 3
        assert result[0].confidence == 1.0

        # Request went to the Newsflash events endpoint with the expected params
        url = mock_get.call_args[0][0]
        assert url.startswith("https://newsflash.sh/api/events?q=NVDA")
        assert "&to=2026-07-24" in url
        assert "semantic" not in url

        # Unfiltered results were cached
        mock_cache.set_company_news.assert_called_once()

    @patch('src.tools.api._cache')
    @patch('src.tools.api.requests.get')
    def test_min_confidence_filters_rumors(self, mock_get, mock_cache):
        """min_confidence drops weakly-corroborated events."""
        mock_cache.get_company_news.return_value = None

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_RESPONSE
        mock_get.return_value = mock_response

        result = get_newsflash_news("NVDA", min_confidence=0.66)

        assert len(result) == 1
        assert result[0].corroboration == 3

        # The cache still receives the unfiltered list so other thresholds can reuse it
        cached = mock_cache.set_company_news.call_args[0][1]
        assert len(cached) == 2

    @patch('src.tools.api._cache')
    @patch('src.tools.api.requests.get')
    def test_cache_hit_skips_api(self, mock_get, mock_cache):
        """A cache hit returns mapped models without an HTTP call."""
        mock_cache.get_company_news.return_value = [
            {
                "ticker": "NVDA",
                "title": "Cached event",
                "author": None,
                "source": "reuters",
                "date": "2026-07-23T15:00:00.000Z",
                "url": "https://newsflash.sh/api/events/101",
                "sentiment": None,
                "corroboration": 3,
                "confidence": 1.0,
            }
        ]

        result = get_newsflash_news("NVDA")

        assert len(result) == 1
        assert result[0].title == "Cached event"
        mock_get.assert_not_called()

    @patch('src.tools.api._cache')
    @patch('src.tools.api.requests.get')
    def test_semantic_and_dates_in_url(self, mock_get, mock_cache):
        """semantic=1 and from/to are forwarded, and the query is URL-encoded."""
        mock_cache.get_company_news.return_value = None

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"count": 0, "events": []}
        mock_get.return_value = mock_response

        result = get_newsflash_news("chip export controls", start_date="2026-07-01", end_date="2026-07-24", semantic=True)

        assert result == []
        url = mock_get.call_args[0][0]
        assert "q=chip%20export%20controls" in url
        assert "&from=2026-07-01" in url
        assert "&to=2026-07-24" in url
        assert "&semantic=1" in url

    @patch('src.tools.api._cache')
    @patch('src.tools.api.requests.get')
    def test_api_error_returns_empty_list(self, mock_get, mock_cache):
        """Non-200 responses degrade to an empty list, matching other providers."""
        mock_cache.get_company_news.return_value = None

        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = get_newsflash_news("NVDA")

        assert result == []
        mock_cache.set_company_news.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__])
