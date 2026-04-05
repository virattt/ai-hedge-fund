"""Tests for openinsider_service.py: fetch worker and async cache entry point.

Covers:
- _fetch_openinsider_data: happy path, retry-once on failure, both-fail raises, User-Agent, Cloudflare raise
- get_openinsider_screener: cache hit (cached=True), cache miss (cached=False), TTL expiry
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

_CLOUDFLARE_HTML = """
<html>
<head><title>Just a moment...</title></head>
<body>Checking your browser before accessing the site.</body>
</html>
"""


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
            with patch("time.sleep"):
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
