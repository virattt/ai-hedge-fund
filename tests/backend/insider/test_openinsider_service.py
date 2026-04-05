"""Tests for openinsider_service.py: URL building, HTML parsing, Cloudflare detection, cache, and retry.

Covers:
- build_screener_url: all 3 presets + custom params
- parse_openinsider_table: valid table, missing table, malformed numerics
- _detect_cloudflare_challenge: positive/negative detection
- _fetch_openinsider_data: happy path, retry-once on failure, both-fail raises, User-Agent, Cloudflare raise
- get_openinsider_screener: cache hit (cached=True), cache miss (cached=False), TTL expiry
- Custom params ignored for preset modes
"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers: sample HTML fixtures
# ---------------------------------------------------------------------------

_VALID_TABLE_HTML = """
<html>
<body>
<table class="tinytable" id="screener-content">
<thead>
<tr>
<th>X</th><th>Filing Date</th><th>Trade Date</th><th>Ticker</th><th>Company Name</th>
<th>Insider Name</th><th>Title</th><th>Trade Type</th><th>Price</th><th>Qty</th>
<th>Owned</th><th>Delta Own</th><th>Value</th>
</tr>
</thead>
<tbody>
<tr>
<td></td>
<td>2026-04-01</td>
<td>2026-03-28</td>
<td>AAPL</td>
<td>Apple Inc.</td>
<td>Tim Cook</td>
<td>CEO</td>
<td>P - Purchase</td>
<td>$175.50</td>
<td>10,000</td>
<td>3,280,000</td>
<td>+0.3%</td>
<td>$1,755,000</td>
</tr>
<tr>
<td></td>
<td>2026-03-30</td>
<td>2026-03-27</td>
<td>MSFT</td>
<td>Microsoft Corp.</td>
<td>Satya Nadella</td>
<td>CEO</td>
<td>P - Purchase</td>
<td>$420.00</td>
<td>5,000</td>
<td>800,000</td>
<td>+0.6%</td>
<td>$2,100,000</td>
</tr>
</tbody>
</table>
</body>
</html>
"""

_NO_TABLE_HTML = """
<html><body><p>No results found.</p></body></html>
"""

_MALFORMED_NUMERIC_HTML = """
<html>
<body>
<table class="tinytable">
<thead>
<tr>
<th>X</th><th>Filing Date</th><th>Trade Date</th><th>Ticker</th><th>Company Name</th>
<th>Insider Name</th><th>Title</th><th>Trade Type</th><th>Price</th><th>Qty</th>
<th>Owned</th><th>Delta Own</th><th>Value</th>
</tr>
</thead>
<tbody>
<tr>
<td></td>
<td>2026-04-01</td>
<td>2026-03-28</td>
<td>TSLA</td>
<td>Tesla Inc.</td>
<td>Elon Musk</td>
<td>CEO</td>
<td>P - Purchase</td>
<td></td>
<td></td>
<td></td>
<td></td>
<td></td>
</tr>
</tbody>
</table>
</body>
</html>
"""

_CLOUDFLARE_HTML = """
<html>
<head><title>Just a moment...</title></head>
<body>Checking your browser before accessing the site.</body>
</html>
"""

_ATTENTION_REQUIRED_HTML = """
<html>
<head><title>Attention Required! | Cloudflare</title></head>
<body>Sorry, you have been blocked.</body>
</html>
"""


# ---------------------------------------------------------------------------
# build_screener_url
# ---------------------------------------------------------------------------


class TestBuildScreenerUrl:
    """Tests for URL construction from presets and custom params."""

    def test_build_url_ceo_cfo_preset_includes_purchase_and_min_value(self) -> None:
        """CEO/CFO conviction preset URL contains xp=1, vl=100000, fd=30."""
        from app.backend.services.openinsider_service import build_screener_url

        url = build_screener_url("ceo_cfo_conviction", None)

        assert "xp=1" in url
        assert "vl=100000" in url
        assert "fd=30" in url

    def test_build_url_cluster_buy_preset_includes_cluster_count(self) -> None:
        """Cluster buy preset URL contains isc=3, vl=25000, fd=90."""
        from app.backend.services.openinsider_service import build_screener_url

        url = build_screener_url("cluster_buy", None)

        assert "isc=3" in url
        assert "vl=25000" in url
        assert "fd=90" in url

    def test_build_url_significant_increase_preset_includes_holdings_change(self) -> None:
        """Significant increase preset URL contains fdlyl=20, fd=90."""
        from app.backend.services.openinsider_service import build_screener_url

        url = build_screener_url("significant_increase", None)

        assert "fdlyl=20" in url
        assert "fd=90" in url

    def test_build_url_custom_passes_params(self) -> None:
        """Custom mode encodes all provided custom params in the URL."""
        from app.backend.services.openinsider_service import build_screener_url

        url = build_screener_url("custom", {"s": "AAPL", "vl": "50000", "fd": "60"})

        assert "s=AAPL" in url
        assert "vl=50000" in url
        assert "fd=60" in url

    def test_build_url_custom_empty_params_returns_base_url(self) -> None:
        """Custom mode with empty dict returns the base URL."""
        from app.backend.services.openinsider_service import _BASE_URL, build_screener_url

        url = build_screener_url("custom", {})

        assert url.startswith(_BASE_URL)

    def test_build_url_preset_ignores_custom_params(self) -> None:
        """Non-custom preset mode ignores any custom_params dict passed in."""
        from app.backend.services.openinsider_service import build_screener_url

        url = build_screener_url("cluster_buy", {"vl": "999999", "s": "ZZZZ"})

        # Preset params should be used, not the custom override
        assert "vl=25000" in url
        assert "isc=3" in url
        # Custom override should not appear
        assert "vl=999999" not in url
        assert "s=ZZZZ" not in url


# ---------------------------------------------------------------------------
# _detect_cloudflare_challenge
# ---------------------------------------------------------------------------


class TestDetectCloudflareChallenge:
    """Tests for Cloudflare challenge page detection."""

    def test_detects_just_a_moment_title(self) -> None:
        """HTML with 'Just a moment' in title is identified as Cloudflare challenge."""
        from app.backend.services.openinsider_service import _detect_cloudflare_challenge

        assert _detect_cloudflare_challenge(_CLOUDFLARE_HTML, {}) is True

    def test_detects_attention_required_title(self) -> None:
        """HTML with 'Attention Required' in title is identified as Cloudflare challenge."""
        from app.backend.services.openinsider_service import _detect_cloudflare_challenge

        assert _detect_cloudflare_challenge(_ATTENTION_REQUIRED_HTML, {}) is True

    def test_detects_cf_mitigated_header(self) -> None:
        """Response header cf-mitigated triggers Cloudflare detection."""
        from app.backend.services.openinsider_service import _detect_cloudflare_challenge

        assert _detect_cloudflare_challenge("<html></html>", {"cf-mitigated": "challenge"}) is True

    def test_normal_page_not_detected(self) -> None:
        """Normal HTML with valid table is not flagged as Cloudflare challenge."""
        from app.backend.services.openinsider_service import _detect_cloudflare_challenge

        assert _detect_cloudflare_challenge(_VALID_TABLE_HTML, {}) is False


# ---------------------------------------------------------------------------
# parse_openinsider_table
# ---------------------------------------------------------------------------


class TestParseOpenInsiderTable:
    """Tests for HTML table parsing with BeautifulSoup html.parser."""

    def test_parse_extracts_records_from_valid_html(self) -> None:
        """Valid HTML with 2 data rows returns 2 OpenInsiderRecord objects."""
        from app.backend.services.openinsider_service import parse_openinsider_table

        records = parse_openinsider_table(_VALID_TABLE_HTML)

        assert len(records) == 2
        assert records[0].ticker == "AAPL"
        assert records[0].company_name == "Apple Inc."
        assert records[0].insider_name == "Tim Cook"
        assert records[0].title == "CEO"
        assert records[0].trade_type == "P - Purchase"
        assert records[0].price == pytest.approx(175.50)
        assert records[0].qty == 10000
        assert records[0].owned == 3280000
        assert records[0].delta_own == "+0.3%"
        assert records[0].value == pytest.approx(1755000.0)

    def test_parse_returns_empty_list_when_no_table(self) -> None:
        """HTML without tinytable class returns empty list (no crash)."""
        from app.backend.services.openinsider_service import parse_openinsider_table

        records = parse_openinsider_table(_NO_TABLE_HTML)

        assert records == []

    def test_parse_handles_malformed_numeric_values(self) -> None:
        """Rows with empty numeric cells parse without error; None returned for missing values."""
        from app.backend.services.openinsider_service import parse_openinsider_table

        records = parse_openinsider_table(_MALFORMED_NUMERIC_HTML)

        assert len(records) == 1
        assert records[0].ticker == "TSLA"
        assert records[0].price is None
        assert records[0].qty is None
        assert records[0].owned is None
        assert records[0].value is None

    def test_parse_strips_dollar_signs_and_commas(self) -> None:
        """Dollar signs and commas are stripped from price/value before conversion."""
        from app.backend.services.openinsider_service import parse_openinsider_table

        records = parse_openinsider_table(_VALID_TABLE_HTML)

        # $175.50 -> 175.50, $1,755,000 -> 1755000.0
        assert records[0].price == pytest.approx(175.50)
        assert records[0].value == pytest.approx(1755000.0)
        assert records[0].qty == 10000


# ---------------------------------------------------------------------------
# _fetch_openinsider_data
# ---------------------------------------------------------------------------


class TestFetchOpenInsiderData:
    """Tests for the synchronous _fetch_openinsider_data() worker."""

    def _make_response(self, html: str, headers: dict | None = None) -> MagicMock:
        """Build a mock httpx Response."""
        resp = MagicMock()
        resp.text = html
        resp.headers = headers or {}
        resp.raise_for_status.return_value = None
        return resp

    def test_fetch_returns_records_on_success(self) -> None:
        """Successful fetch returns OpenInsiderResponse with parsed records and cached=False."""
        from app.backend.services.openinsider_service import _fetch_openinsider_data

        mock_resp = self._make_response(_VALID_TABLE_HTML)
        with patch("httpx.get", return_value=mock_resp):
            result = _fetch_openinsider_data("ceo_cfo_conviction", None)

        assert result.preset == "ceo_cfo_conviction"
        assert result.cached is False
        assert result.total == 2
        assert len(result.records) == 2
        assert result.records[0].ticker == "AAPL"

    def test_fetch_retries_once_on_failure(self) -> None:
        """First httpx.get raises, second succeeds -> records returned."""
        from app.backend.services.openinsider_service import _fetch_openinsider_data

        mock_resp = self._make_response(_VALID_TABLE_HTML)
        with patch("httpx.get", side_effect=[Exception("network error"), mock_resp]):
            with patch("time.sleep"):  # Don't actually sleep in tests
                result = _fetch_openinsider_data("cluster_buy", None)

        assert result.total == 2

    def test_fetch_raises_after_both_attempts_fail(self) -> None:
        """Both httpx.get calls raise -> OpenInsiderFetchError raised."""
        from app.backend.services.openinsider_service import (
            OpenInsiderFetchError,
            _fetch_openinsider_data,
        )

        with patch("httpx.get", side_effect=Exception("connection refused")):
            with patch("time.sleep"):
                with pytest.raises(OpenInsiderFetchError):
                    _fetch_openinsider_data("ceo_cfo_conviction", None)

    def test_fetch_sends_browser_user_agent(self) -> None:
        """httpx.get is called with a User-Agent header resembling a real browser."""
        from app.backend.services.openinsider_service import _USER_AGENT, _fetch_openinsider_data

        mock_resp = self._make_response(_VALID_TABLE_HTML)
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            _fetch_openinsider_data("ceo_cfo_conviction", None)

        call_kwargs = mock_get.call_args[1]
        assert "headers" in call_kwargs
        assert call_kwargs["headers"].get("User-Agent") == _USER_AGENT

    def test_fetch_raises_on_cloudflare_challenge(self) -> None:
        """Response with Cloudflare challenge HTML raises OpenInsiderFetchError with 'Cloudflare' in message."""
        from app.backend.services.openinsider_service import (
            OpenInsiderFetchError,
            _fetch_openinsider_data,
        )

        mock_resp = self._make_response(_CLOUDFLARE_HTML)
        with patch("httpx.get", return_value=mock_resp):
            with pytest.raises(OpenInsiderFetchError, match="Cloudflare"):
                _fetch_openinsider_data("ceo_cfo_conviction", None)


# ---------------------------------------------------------------------------
# get_openinsider_screener (async entry point + cache)
# ---------------------------------------------------------------------------


class TestGetOpenInsiderScreener:
    """Tests for async get_openinsider_screener() and the LRU+TTL cache."""

    def setup_method(self) -> None:
        """Clear the openinsider cache before each test."""
        from app.backend.services.openinsider_service import _oi_cache
        _oi_cache.clear()

    @pytest.mark.asyncio
    async def test_cache_miss_calls_fetch_and_returns_cached_false(self) -> None:
        """First call hits network; cached=False on returned response."""
        from app.backend.services.openinsider_service import (
            OpenInsiderResponse,
            get_openinsider_screener,
        )

        fresh_response = OpenInsiderResponse(
            preset="ceo_cfo_conviction", records=[], total=0, cached=False
        )
        with patch(
            "app.backend.services.openinsider_service._fetch_openinsider_data",
            return_value=fresh_response,
        ):
            result = await get_openinsider_screener("ceo_cfo_conviction", None)

        assert result.cached is False

    @pytest.mark.asyncio
    async def test_cache_returns_cached_response_on_second_call(self) -> None:
        """Second call with same key is served from cache; cached=True, fetch called only once."""
        from app.backend.services.openinsider_service import (
            OpenInsiderResponse,
            get_openinsider_screener,
        )

        fresh_response = OpenInsiderResponse(
            preset="ceo_cfo_conviction", records=[], total=0, cached=False
        )
        with patch(
            "app.backend.services.openinsider_service._fetch_openinsider_data",
            return_value=fresh_response,
        ) as mock_fetch:
            first = await get_openinsider_screener("ceo_cfo_conviction", None)
            second = await get_openinsider_screener("ceo_cfo_conviction", None)

        mock_fetch.assert_called_once()
        assert first.cached is False
        assert second.cached is True

    @pytest.mark.asyncio
    async def test_cache_expires_after_ttl(self) -> None:
        """After TTL expiry, second call triggers a fresh fetch; both responses have cached=False."""
        import app.backend.services.openinsider_service as svc
        from app.backend.services.openinsider_service import (
            OpenInsiderResponse,
            get_openinsider_screener,
        )

        fresh_response = OpenInsiderResponse(
            preset="ceo_cfo_conviction", records=[], total=0, cached=False
        )
        with patch.object(svc, "_CACHE_TTL_SECONDS", 0.0):
            with patch(
                "app.backend.services.openinsider_service._fetch_openinsider_data",
                return_value=fresh_response,
            ) as mock_fetch:
                first = await get_openinsider_screener("ceo_cfo_conviction", None)
                await asyncio.sleep(0.01)
                second = await get_openinsider_screener("ceo_cfo_conviction", None)

        assert mock_fetch.call_count == 2
        assert first.cached is False
        assert second.cached is False

    @pytest.mark.asyncio
    async def test_cache_key_differs_for_different_presets(self) -> None:
        """Different presets use different cache keys; each triggers a fetch."""
        from app.backend.services.openinsider_service import (
            OpenInsiderResponse,
            get_openinsider_screener,
        )

        def _make_resp(preset: str, _params: object) -> OpenInsiderResponse:
            return OpenInsiderResponse(preset=preset, records=[], total=0, cached=False)

        with patch(
            "app.backend.services.openinsider_service._fetch_openinsider_data",
            side_effect=_make_resp,
        ) as mock_fetch:
            await get_openinsider_screener("ceo_cfo_conviction", None)
            await get_openinsider_screener("cluster_buy", None)

        assert mock_fetch.call_count == 2
