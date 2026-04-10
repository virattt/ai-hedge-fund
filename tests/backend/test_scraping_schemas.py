"""Tests for scraping Pydantic schemas, focusing on SSRF protection in WebsiteCreateRequest."""
import pytest
from pydantic import ValidationError

from app.backend.models.schemas import WebsiteCreateRequest


class TestWebsiteCreateRequestSSRFProtection:
    """Tests for SSRF protection in the URL validator."""

    @pytest.mark.parametrize("url", [
        "http://192.168.1.1/page",
        "http://10.0.0.1/data",
        "http://172.16.0.1/admin",
        "http://172.31.255.255/secret",
        "http://127.0.0.1:8080/",
        "http://169.254.169.254/latest/meta-data/",
    ])
    def test_website_create_request_rejects_private_ip(self, url: str) -> None:
        """SSRF: URLs resolving to private/reserved IP ranges must be rejected."""
        with pytest.raises(ValidationError):
            WebsiteCreateRequest(url=url, name="Test Site")

    @pytest.mark.parametrize("url", [
        "http://localhost/page",
        "http://localhost:3000/",
    ])
    def test_website_create_request_rejects_localhost(self, url: str) -> None:
        """SSRF: localhost URLs must be rejected regardless of port."""
        with pytest.raises(ValidationError):
            WebsiteCreateRequest(url=url, name="Test Site")

    @pytest.mark.parametrize("url", [
        "ftp://example.com",
        "file:///etc/passwd",
        "javascript:alert(1)",
    ])
    def test_website_create_request_rejects_non_http_schemes(self, url: str) -> None:
        """SSRF: Only http and https schemes are allowed."""
        with pytest.raises(ValidationError):
            WebsiteCreateRequest(url=url, name="Test Site")

    @pytest.mark.parametrize("url", [
        "https://example.com",
        "http://news.ycombinator.com",
        "https://finance.yahoo.com/quote/AAPL",
    ])
    def test_website_create_request_accepts_valid_urls(self, url: str) -> None:
        """Public HTTPS/HTTP URLs with valid hostnames must be accepted."""
        request = WebsiteCreateRequest(url=url, name="Test Site")
        assert request.url == url

    def test_website_create_request_requires_url_and_name(self) -> None:
        """Both url and name fields are required; empty strings must fail."""
        with pytest.raises(ValidationError):
            WebsiteCreateRequest(name="Test Site")  # missing url

        with pytest.raises(ValidationError):
            WebsiteCreateRequest(url="https://example.com")  # missing name

        with pytest.raises(ValidationError):
            WebsiteCreateRequest(url="https://example.com", name="")  # empty name
