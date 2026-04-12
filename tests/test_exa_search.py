import os
import pytest
from unittest.mock import Mock, patch

from src.tools.exa_search import search_exa
from src.data.models import ExaSearchResult


class TestSearchExa:
    """Test suite for the Exa search tool."""

    def _make_mock_result(self, title="Test Article", url="https://example.com",
                          highlights=None, summary=None, text=None,
                          published_date=None, author=None):
        """Helper to create a mock Exa result object."""
        result = Mock()
        result.title = title
        result.url = url
        result.highlights = highlights
        result.summary = summary
        result.text = text
        result.published_date = published_date
        result.author = author
        return result

    def test_returns_empty_when_no_api_key(self):
        """Test that search returns empty list when EXA_API_KEY is not set."""
        with patch.dict(os.environ, {}, clear=True):
            results = search_exa("test query")
            assert results == []

    @patch("src.tools.exa_search.Exa", None)
    def test_returns_empty_when_exa_not_installed(self):
        """Test that search returns empty list when exa-py is not installed."""
        results = search_exa("test query", api_key="test-key")
        assert results == []

    @patch("src.tools.exa_search.Exa")
    def test_successful_search_with_highlights(self, mock_exa_cls):
        """Test successful search returns parsed results using highlights."""
        mock_client = Mock()
        mock_client.headers = {}
        mock_exa_cls.return_value = mock_client

        mock_response = Mock()
        mock_response.results = [
            self._make_mock_result(
                title="AAPL Earnings Beat",
                url="https://news.com/aapl",
                highlights=["Apple reported record Q4 earnings.", "Revenue up 15% YoY."],
                summary="Apple had a strong quarter.",
                published_date="2024-03-15",
                author="John Doe",
            )
        ]
        mock_client.search.return_value = mock_response

        results = search_exa("AAPL stock news", api_key="test-key")

        assert len(results) == 1
        assert isinstance(results[0], ExaSearchResult)
        assert results[0].title == "AAPL Earnings Beat"
        assert results[0].url == "https://news.com/aapl"
        assert "Apple reported record Q4 earnings." in results[0].snippet
        assert "Revenue up 15% YoY." in results[0].snippet
        assert results[0].published_date == "2024-03-15"
        assert results[0].author == "John Doe"

    @patch("src.tools.exa_search.Exa")
    def test_fallback_to_summary_when_no_highlights(self, mock_exa_cls):
        """Test that snippet falls back to summary when highlights are empty."""
        mock_client = Mock()
        mock_client.headers = {}
        mock_exa_cls.return_value = mock_client

        mock_response = Mock()
        mock_response.results = [
            self._make_mock_result(
                title="Market Update",
                url="https://news.com/market",
                highlights=[],
                summary="Markets rallied on strong jobs data.",
            )
        ]
        mock_client.search.return_value = mock_response

        results = search_exa("market news", api_key="test-key")

        assert len(results) == 1
        assert results[0].snippet == "Markets rallied on strong jobs data."

    @patch("src.tools.exa_search.Exa")
    def test_fallback_to_text_when_no_highlights_or_summary(self, mock_exa_cls):
        """Test that snippet falls back to text when both highlights and summary are missing."""
        mock_client = Mock()
        mock_client.headers = {}
        mock_exa_cls.return_value = mock_client

        mock_response = Mock()
        mock_response.results = [
            self._make_mock_result(
                title="Analysis",
                url="https://blog.com/analysis",
                highlights=None,
                summary=None,
                text="Full article text here about stock performance.",
            )
        ]
        mock_client.search.return_value = mock_response

        results = search_exa("stock analysis", api_key="test-key")

        assert len(results) == 1
        assert results[0].snippet == "Full article text here about stock performance."

    @patch("src.tools.exa_search.Exa")
    def test_empty_snippet_when_no_content(self, mock_exa_cls):
        """Test that snippet is empty when no content fields are available."""
        mock_client = Mock()
        mock_client.headers = {}
        mock_exa_cls.return_value = mock_client

        mock_response = Mock()
        mock_response.results = [
            self._make_mock_result(
                title="Minimal Result",
                url="https://example.com",
            )
        ]
        mock_client.search.return_value = mock_response

        results = search_exa("query", api_key="test-key")

        assert len(results) == 1
        assert results[0].snippet == ""

    @patch("src.tools.exa_search.Exa")
    def test_passes_search_parameters_correctly(self, mock_exa_cls):
        """Test that all search parameters are passed to the Exa client."""
        mock_client = Mock()
        mock_client.headers = {}
        mock_exa_cls.return_value = mock_client

        mock_response = Mock()
        mock_response.results = []
        mock_client.search.return_value = mock_response

        search_exa(
            query="TSLA stock",
            num_results=5,
            search_type="neural",
            category="news",
            include_domains=["reuters.com"],
            exclude_domains=["reddit.com"],
            include_text=["Tesla"],
            exclude_text=["crypto"],
            start_published_date="2024-01-01T00:00:00.000Z",
            end_published_date="2024-03-01T00:00:00.000Z",
            api_key="test-key",
        )

        mock_client.search.assert_called_once()
        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs["query"] == "TSLA stock"
        assert call_kwargs["num_results"] == 5
        assert call_kwargs["type"] == "neural"
        assert call_kwargs["category"] == "news"
        assert call_kwargs["include_domains"] == ["reuters.com"]
        assert call_kwargs["exclude_domains"] == ["reddit.com"]
        assert call_kwargs["include_text"] == ["Tesla"]
        assert call_kwargs["exclude_text"] == ["crypto"]
        assert call_kwargs["start_published_date"] == "2024-01-01T00:00:00.000Z"
        assert call_kwargs["end_published_date"] == "2024-03-01T00:00:00.000Z"

    @patch("src.tools.exa_search.Exa")
    def test_requests_highlights_and_summary_content(self, mock_exa_cls):
        """Test that search requests both highlights and summary content types."""
        mock_client = Mock()
        mock_client.headers = {}
        mock_exa_cls.return_value = mock_client

        mock_response = Mock()
        mock_response.results = []
        mock_client.search.return_value = mock_response

        search_exa("test", api_key="test-key")

        call_kwargs = mock_client.search.call_args[1]
        assert "contents" in call_kwargs
        assert "highlights" in call_kwargs["contents"]
        assert "summary" in call_kwargs["contents"]
        assert call_kwargs["contents"]["highlights"]["max_characters"] == 4000
        assert call_kwargs["contents"]["summary"] is True

    @patch("src.tools.exa_search.Exa")
    def test_sets_integration_tracking_header(self, mock_exa_cls):
        """Test that the x-exa-integration header is set on the client."""
        mock_client = Mock()
        mock_client.headers = {}
        mock_exa_cls.return_value = mock_client

        mock_response = Mock()
        mock_response.results = []
        mock_client.search.return_value = mock_response

        search_exa("test", api_key="test-key")

        assert mock_client.headers["x-exa-integration"] == "ai-hedge-fund"

    @patch("src.tools.exa_search.Exa")
    def test_handles_api_error_gracefully(self, mock_exa_cls):
        """Test that API errors are caught and return empty list."""
        mock_client = Mock()
        mock_client.headers = {}
        mock_exa_cls.return_value = mock_client
        mock_client.search.side_effect = Exception("API Error: rate limit exceeded")

        results = search_exa("test query", api_key="test-key")

        assert results == []

    @patch("src.tools.exa_search.Exa")
    def test_multiple_results_parsed(self, mock_exa_cls):
        """Test that multiple search results are all parsed correctly."""
        mock_client = Mock()
        mock_client.headers = {}
        mock_exa_cls.return_value = mock_client

        mock_response = Mock()
        mock_response.results = [
            self._make_mock_result(title="Article 1", url="https://a.com", highlights=["Content 1"]),
            self._make_mock_result(title="Article 2", url="https://b.com", summary="Summary 2"),
            self._make_mock_result(title="Article 3", url="https://c.com", text="Text 3"),
        ]
        mock_client.search.return_value = mock_response

        results = search_exa("multi query", api_key="test-key")

        assert len(results) == 3
        assert results[0].title == "Article 1"
        assert results[0].snippet == "Content 1"
        assert results[1].title == "Article 2"
        assert results[1].snippet == "Summary 2"
        assert results[2].title == "Article 3"
        assert results[2].snippet == "Text 3"

    @patch("src.tools.exa_search.Exa")
    def test_handles_none_fields_gracefully(self, mock_exa_cls):
        """Test that None values in result fields don't cause errors."""
        mock_client = Mock()
        mock_client.headers = {}
        mock_exa_cls.return_value = mock_client

        result = Mock()
        result.title = None
        result.url = None
        result.highlights = None
        result.summary = None
        result.text = None
        result.published_date = None
        result.author = None

        mock_response = Mock()
        mock_response.results = [result]
        mock_client.search.return_value = mock_response

        results = search_exa("test", api_key="test-key")

        assert len(results) == 1
        assert results[0].title == ""
        assert results[0].url == ""
        assert results[0].snippet == ""
        assert results[0].published_date is None
        assert results[0].author is None

    @patch("src.tools.exa_search.Exa")
    def test_optional_params_not_sent_when_none(self, mock_exa_cls):
        """Test that optional parameters are omitted when not provided."""
        mock_client = Mock()
        mock_client.headers = {}
        mock_exa_cls.return_value = mock_client

        mock_response = Mock()
        mock_response.results = []
        mock_client.search.return_value = mock_response

        search_exa("simple query", api_key="test-key")

        call_kwargs = mock_client.search.call_args[1]
        assert "category" not in call_kwargs
        assert "include_domains" not in call_kwargs
        assert "exclude_domains" not in call_kwargs
        assert "include_text" not in call_kwargs
        assert "exclude_text" not in call_kwargs
        assert "start_published_date" not in call_kwargs
        assert "end_published_date" not in call_kwargs


class TestExaSearchResultModel:
    """Test the ExaSearchResult Pydantic model."""

    def test_creates_valid_result(self):
        result = ExaSearchResult(
            title="Test",
            url="https://example.com",
            snippet="Content here",
            published_date="2024-01-01",
            author="Author",
        )
        assert result.title == "Test"
        assert result.url == "https://example.com"

    def test_optional_fields_default_to_none(self):
        result = ExaSearchResult(
            title="Test",
            url="https://example.com",
            snippet="Content",
        )
        assert result.published_date is None
        assert result.author is None


if __name__ == "__main__":
    pytest.main([__file__])
