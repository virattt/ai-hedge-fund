import os
import pytest
import requests
from unittest.mock import Mock, patch

from src.tools.web import CACHE_TTL_SECONDS, DEFAULT_MAX_CHARS, REQUEST_TIMEOUT_SECONDS, SCRAPE_TIMEOUT_MS, _article_cache, scrape_article_text


class TestScrapeArticleText:
    """Test suite for Firecrawl-backed article scraping."""

    @pytest.fixture(autouse=True)
    def clear_scrape_cache(self):
        """Scrapes are cached across calls, so each test starts from a clean cache."""
        _article_cache.clear()
        yield
        _article_cache.clear()

    @patch('src.tools.web.Firecrawl')
    def test_returns_article_markdown(self, mock_firecrawl):
        """Test that a successful scrape returns the article markdown."""
        mock_firecrawl.return_value.scrape.return_value = Mock(markdown="# Apple beats earnings")

        result = scrape_article_text("https://example.com/apple", api_key="test-key")

        assert result == "# Apple beats earnings"
        mock_firecrawl.assert_called_once_with(api_key="test-key", timeout=REQUEST_TIMEOUT_SECONDS)
        mock_firecrawl.return_value.scrape.assert_called_once_with("https://example.com/apple", formats=["markdown"], timeout=SCRAPE_TIMEOUT_MS)

    @patch('src.tools.web.Firecrawl')
    def test_truncates_long_articles(self, mock_firecrawl):
        """Test that article text is truncated to keep LLM prompts small."""
        mock_firecrawl.return_value.scrape.return_value = Mock(markdown="a" * (DEFAULT_MAX_CHARS + 100))

        result = scrape_article_text("https://example.com/long", api_key="test-key")

        assert len(result) == DEFAULT_MAX_CHARS

    @patch('src.tools.web.Firecrawl')
    def test_falls_back_to_environment_api_key(self, mock_firecrawl):
        """Test that the API key is read from the environment when not passed in."""
        mock_firecrawl.return_value.scrape.return_value = Mock(markdown="Article text")

        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": "env-key"}):
            result = scrape_article_text("https://example.com/apple")

        assert result == "Article text"
        mock_firecrawl.assert_called_once_with(api_key="env-key", timeout=REQUEST_TIMEOUT_SECONDS)

    @patch('src.tools.web.Firecrawl')
    def test_returns_none_without_api_key(self, mock_firecrawl):
        """Test that no API key means no scrape attempt, so callers can fall back."""
        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": ""}):
            result = scrape_article_text("https://example.com/apple")

        assert result is None
        mock_firecrawl.assert_not_called()

    @patch('src.tools.web.Firecrawl')
    def test_returns_none_when_scrape_fails(self, mock_firecrawl):
        """Test that a failing scrape degrades gracefully instead of raising."""
        mock_firecrawl.return_value.scrape.side_effect = Exception("scrape failed")

        result = scrape_article_text("https://example.com/apple", api_key="test-key")

        assert result is None

    @patch('src.tools.web.Firecrawl')
    def test_returns_none_when_scrape_times_out(self, mock_firecrawl):
        """Test that a timed out scrape falls back instead of blocking the agent."""
        mock_firecrawl.return_value.scrape.side_effect = requests.exceptions.Timeout("timed out")

        result = scrape_article_text("https://example.com/slow", api_key="test-key")

        assert result is None

    @patch('src.tools.web.Firecrawl')
    def test_retries_after_a_failed_scrape(self, mock_firecrawl):
        """Test that a transient failure is not cached, so the URL can be scraped again."""
        mock_firecrawl.return_value.scrape.side_effect = [
            requests.exceptions.Timeout("timed out"),
            Mock(markdown="Article text"),
        ]

        assert scrape_article_text("https://example.com/apple", api_key="test-key") is None
        assert scrape_article_text("https://example.com/apple", api_key="test-key") == "Article text"

    @patch('src.tools.web.Firecrawl')
    def test_caches_repeated_scrapes(self, mock_firecrawl):
        """Test that the same URL is only scraped once."""
        mock_firecrawl.return_value.scrape.return_value = Mock(markdown="Article text")

        scrape_article_text("https://example.com/apple", api_key="test-key")
        scrape_article_text("https://example.com/apple", api_key="test-key")

        assert mock_firecrawl.return_value.scrape.call_count == 1

    @patch('src.tools.web.Firecrawl')
    def test_rescrapes_stale_cache_entries(self, mock_firecrawl):
        """Test that a cached article expires, so corrected articles are picked up."""
        mock_firecrawl.return_value.scrape.return_value = Mock(markdown="Article text")
        now = [0.0]

        with patch('src.tools.web.time.monotonic', side_effect=lambda: now[0]):
            scrape_article_text("https://example.com/apple", api_key="test-key")
            now[0] = CACHE_TTL_SECONDS + 1
            scrape_article_text("https://example.com/apple", api_key="test-key")

        assert mock_firecrawl.return_value.scrape.call_count == 2

    @patch('src.tools.web.CACHE_MAX_ENTRIES', 2)
    @patch('src.tools.web.Firecrawl')
    def test_evicts_least_recently_used_articles(self, mock_firecrawl):
        """Test that the cache stays bounded rather than growing for the process lifetime."""
        mock_firecrawl.return_value.scrape.return_value = Mock(markdown="Article text")

        for url in ("https://example.com/1", "https://example.com/2", "https://example.com/3"):
            scrape_article_text(url, api_key="test-key")

        assert len(_article_cache) == 2
        assert "https://example.com/1" not in _article_cache
