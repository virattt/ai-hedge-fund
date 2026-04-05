"""Tests for openinsider_service.py: URL construction, parameter translation, HTML parsing, and Cloudflare detection.

Covers:
- build_screener_url: all 3 presets + custom params with API-key-to-OI-key translation
- _translate_custom_params: key and value mapping (transaction_type values, officer_filter exclusion)
- parse_openinsider_table: valid table, missing table, malformed numerics
- _detect_cloudflare_challenge: positive/negative detection
"""
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
# build_screener_url: preset modes
# ---------------------------------------------------------------------------


class TestBuildScreenerUrlPresets:
    """Tests for preset URL construction."""

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

    def test_build_url_preset_ignores_custom_params(self) -> None:
        """Non-custom preset mode ignores any custom_params dict passed in."""
        from app.backend.services.openinsider_service import build_screener_url

        url = build_screener_url("cluster_buy", {"vl": "999999", "s": "ZZZZ"})

        assert "vl=25000" in url
        assert "isc=3" in url
        assert "vl=999999" not in url
        assert "s=ZZZZ" not in url


# ---------------------------------------------------------------------------
# build_screener_url: custom mode with API-key translation
# ---------------------------------------------------------------------------


class TestBuildScreenerUrlCustom:
    """Tests for custom URL construction with API-to-OI parameter translation."""

    def test_build_url_custom_translates_api_keys_to_oi_keys(self) -> None:
        """API-level keys (min_value, filing_days, ticker) are translated to OI keys (vl, fd, s)."""
        from app.backend.services.openinsider_service import build_screener_url

        url = build_screener_url("custom", {"ticker": "AAPL", "min_value": "50000", "filing_days": "60"})

        # API keys must NOT appear in URL
        assert "min_value=" not in url
        assert "filing_days=" not in url
        assert "ticker=" not in url
        # OI-translated keys must appear
        assert "s=AAPL" in url
        assert "vl=50000" in url
        assert "fd=60" in url

    def test_build_url_custom_translates_all_supported_api_keys(self) -> None:
        """All API-level keys are translated to their openinsider.com counterparts."""
        from app.backend.services.openinsider_service import build_screener_url

        url = build_screener_url(
            "custom",
            {
                "ticker": "MSFT",
                "min_value": "100000",
                "filing_days": "30",
                "min_delta_own": "10",
                "min_insiders": "3",
                "transaction_type": "purchase",
            },
        )

        assert "s=MSFT" in url
        assert "vl=100000" in url
        assert "fd=30" in url
        assert "fdlyl=10" in url
        assert "isc=3" in url
        assert "xp=1" in url

    def test_build_url_custom_transaction_type_sale_maps_to_xp_2(self) -> None:
        """transaction_type=sale translates to xp=2 in the URL."""
        from app.backend.services.openinsider_service import build_screener_url

        url = build_screener_url("custom", {"transaction_type": "sale"})

        assert "xp=2" in url

    def test_build_url_custom_transaction_type_all_omitted_from_url(self) -> None:
        """transaction_type=all produces no xp param in the URL (no filter)."""
        from app.backend.services.openinsider_service import build_screener_url

        url = build_screener_url("custom", {"transaction_type": "all"})

        assert "xp=" not in url

    def test_build_url_custom_officer_filter_not_in_url(self) -> None:
        """officer_filter has no direct OI URL param and is excluded from the URL."""
        from app.backend.services.openinsider_service import build_screener_url

        url = build_screener_url("custom", {"officer_filter": "ceo_cfo", "min_value": "50000"})

        assert "officer_filter=" not in url
        assert "vl=50000" in url

    def test_build_url_custom_empty_params_returns_base_url(self) -> None:
        """Custom mode with empty dict returns the base URL."""
        from app.backend.services.openinsider_service import _BASE_URL, build_screener_url

        url = build_screener_url("custom", {})

        assert url.startswith(_BASE_URL)


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

        assert records[0].price == pytest.approx(175.50)
        assert records[0].value == pytest.approx(1755000.0)
        assert records[0].qty == 10000
