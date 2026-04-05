"""OpenInsider scraping service with LRU+TTL cache, retry, parsing, and Cloudflare detection.

Scrapes openinsider.com screener tables using httpx + BeautifulSoup (html.parser).
Three preset screener configurations are provided, plus custom parameter support.
All responses are cached for 1 hour (configurable) in an OrderedDict-based LRU+TTL cache.

Design notes:
- Uses synchronous httpx.get wrapped in asyncio.to_thread to match the project pattern.
- Retry sleep is 1 second (not 2) to minimize thread blocking in the executor pool.
- Uses stdlib html.parser to avoid the lxml external C dependency.
- Cloudflare challenge detection checks both HTML title and cf-mitigated response header.
"""
import asyncio
import logging
import time
from collections import OrderedDict
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from app.backend.models.openinsider_schemas import OpenInsiderRecord, OpenInsiderResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

_BASE_URL: str = "http://openinsider.com/screener"

_CACHE_TTL_SECONDS: float = 3600.0  # 1 hour
_CACHE_MAX_SIZE: int = 20

_USER_AGENT: str = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# OpenInsider screener URL format
# ---------------------------------------------------------------------------
# openinsider.com requires a full form-submission URL with ALL parameters
# present (even empty ones). The base template contains every form field
# with empty defaults. Presets and custom mode override specific fields.

_BASE_PARAMS: dict[str, str] = {
    "s": "",       # ticker symbol
    "o": "",       # owner type
    "pl": "",      # price low
    "ph": "",      # price high
    "ll": "",      # market cap low
    "lh": "",      # market cap high
    "fd": "0",     # filing date range (days: 0=all, 1,2,3,7,14,30,60,90,180,360)
    "td": "0",     # trade date range
    "tdr": "",     # trade date range type
    "fdlyl": "",   # delta own % low
    "fdlyh": "",   # delta own % high
    "dtefrom": "", # date from
    "dteto": "",   # date to
    "xp": "",      # checkbox: P - Purchase (1=checked)
    "xs": "",      # checkbox: S - Sale (1=checked)
    "vl": "",      # value low
    "vh": "",      # value high
    "ocl": "",     # ownership change % low
    "och": "",     # ownership change % high
    "session": "", # session
    "isc": "1",    # insider count minimum
    "cnt": "100",  # results count
    "sortcol": "0",
    "sortdir": "1",
}

# ---------------------------------------------------------------------------
# Preset configurations (overrides on top of _BASE_PARAMS)
# ---------------------------------------------------------------------------

PRESET_CONFIGS: dict[str, dict[str, str]] = {
    # CEO/CFO Conviction: buys + sells > $100k, last 30 days
    "ceo_cfo_conviction": {
        "fd": "30",
        "xp": "1", "xs": "1",  # purchases + sales
        "vl": "100",
        "cnt": "100",
    },
    # Cluster Buy: purchases > $25k, last 90 days, 3+ insiders
    "cluster_buy": {
        "fd": "90",
        "xp": "1",  # purchases only
        "vl": "25",
        "isc": "3",
        "cnt": "100",
    },
    # Cluster Sell: sales > $25k, last 90 days, 3+ insiders
    "cluster_sell": {
        "fd": "90",
        "xs": "1",  # sales only
        "vl": "25",
        "isc": "3",
        "cnt": "100",
    },
    # Significant Increase: purchases, >20% ownership change, last 90 days
    "significant_increase": {
        "fd": "90",
        "xp": "1",  # purchases only
        "ocl": "20",
        "cnt": "100",
    },
    # Screener: all trades (buys + sells), last 30 days
    "screener": {
        "fd": "30",
        "xp": "1", "xs": "1",  # purchases + sales
        "cnt": "100",
    },
}

# ---------------------------------------------------------------------------
# Parameter name mapping: API keys → openinsider.com URL parameter names
# ---------------------------------------------------------------------------

_API_TO_OI_PARAMS: dict[str, str] = {
    "ticker": "s",
    "min_value": "vl",
    "filing_days": "fd",
    "min_delta_own": "ocl",
    "min_insiders": "isc",
}

# transaction_type maps to xp/xs checkbox params
_TRANSACTION_TYPE_MAP: dict[str, dict[str, str]] = {
    "purchase": {"xp": "1"},
    "sale": {"xs": "1"},
    "all": {"xp": "1", "xs": "1"},
}


def _translate_custom_params(api_params: dict[str, str]) -> dict[str, str]:
    """Translate API-level parameter names/values to openinsider.com URL parameters."""
    result: dict[str, str] = {}
    for api_key, value in api_params.items():
        if api_key == "transaction_type":
            result.update(_TRANSACTION_TYPE_MAP.get(value, {"xp": "1"}))
            continue
        oi_key = _API_TO_OI_PARAMS.get(api_key)
        if oi_key is not None:
            result[oi_key] = value
    return result


# ---------------------------------------------------------------------------
# LRU+TTL cache
# ---------------------------------------------------------------------------

_oi_cache: OrderedDict[str, tuple[object, float]] = OrderedDict()


def _oi_cache_get(cache_key: str) -> OpenInsiderResponse | None:
    """Return cached response if present and not expired, else None.

    Evicts the entry on expiry.
    """
    import app.backend.services.openinsider_service as _self

    entry = _oi_cache.get(cache_key)
    if entry is None:
        return None
    response, timestamp = entry
    if time.monotonic() - timestamp > _self._CACHE_TTL_SECONDS:
        _oi_cache.pop(cache_key, None)
        return None
    if not isinstance(response, OpenInsiderResponse):
        return None
    return response


def _oi_cache_put(cache_key: str, response: OpenInsiderResponse) -> None:
    """Store response with current timestamp. Evicts oldest entry when over max size."""
    import app.backend.services.openinsider_service as _self

    _oi_cache[cache_key] = (response, time.monotonic())
    while len(_oi_cache) > _self._CACHE_MAX_SIZE:
        _oi_cache.popitem(last=False)


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class OpenInsiderFetchError(Exception):
    """Raised when openinsider.com cannot be fetched after all retry attempts,
    or when a Cloudflare challenge page is detected."""


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------


def build_screener_url(preset: str, custom_params: dict[str, str] | None) -> str:
    """Construct the full openinsider.com screener URL with all form fields.

    Starts from _BASE_PARAMS (all fields with empty defaults), then applies
    preset overrides or translated custom params on top.
    """
    params = dict(_BASE_PARAMS)
    if preset in PRESET_CONFIGS:
        params.update(PRESET_CONFIGS[preset])
    else:
        params.update(_translate_custom_params(custom_params or {}))
    return f"{_BASE_URL}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Cloudflare detection
# ---------------------------------------------------------------------------


def _detect_cloudflare_challenge(html_content: str, response_headers: dict[str, str]) -> bool:
    """Return True if the response appears to be a Cloudflare challenge page.

    Checks for:
    - HTML <title> containing "Just a moment" or "Attention Required"
    - cf-mitigated response header being present

    Args:
        html_content: Raw HTML body of the response.
        response_headers: HTTP response headers dict (lowercased keys expected).

    Returns:
        True if a Cloudflare challenge is detected, False otherwise.
    """
    if "cf-mitigated" in response_headers:
        return True
    soup = BeautifulSoup(html_content, "html.parser")
    title_tag = soup.find("title")
    if title_tag:
        title_text = title_tag.get_text()
        if "Just a moment" in title_text or "Attention Required" in title_text:
            return True
    return False


# ---------------------------------------------------------------------------
# HTML table parsing
# ---------------------------------------------------------------------------


def _clean_numeric(raw: str) -> str:
    """Strip dollar signs and commas from a numeric string."""
    return raw.replace("$", "").replace(",", "").strip()


def _parse_float(raw: str) -> float | None:
    """Convert a cleaned cell text to float; return None if empty or invalid."""
    cleaned = _clean_numeric(raw)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_int(raw: str) -> int | None:
    """Convert a cleaned cell text to int; return None if empty or invalid."""
    cleaned = _clean_numeric(raw)
    if not cleaned:
        return None
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def parse_openinsider_table(html_content: str) -> list[OpenInsiderRecord]:
    """Parse the tinytable from openinsider.com HTML into a list of records.

    Finds the first <table class="tinytable">, iterates body rows, extracts
    the 13 expected columns (skipping the leading checkbox column), and
    creates an OpenInsiderRecord per row. Skips rows with fewer than 13 cells
    or that raise during field extraction.

    Args:
        html_content: Raw HTML from openinsider.com screener response.

    Returns:
        List of OpenInsiderRecord objects; empty if no table found.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", class_="tinytable")
    if table is None:
        return []

    records: list[OpenInsiderRecord] = []
    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 13:
            continue
        try:
            # Column layout (0-indexed): 0=checkbox, 1=filing_date, 2=trade_date,
            # 3=ticker, 4=company_name, 5=insider_name, 6=title, 7=trade_type,
            # 8=price, 9=qty, 10=owned, 11=delta_own, 12=value
            record = OpenInsiderRecord(
                filing_date=cells[1].get_text(strip=True),
                trade_date=cells[2].get_text(strip=True),
                ticker=cells[3].get_text(strip=True),
                company_name=cells[4].get_text(strip=True),
                insider_name=cells[5].get_text(strip=True),
                title=cells[6].get_text(strip=True),
                trade_type=cells[7].get_text(strip=True),
                price=_parse_float(cells[8].get_text(strip=True)),
                qty=_parse_int(cells[9].get_text(strip=True)),
                owned=_parse_int(cells[10].get_text(strip=True)),
                delta_own=cells[11].get_text(strip=True) or None,
                value=_parse_float(cells[12].get_text(strip=True)),
            )
            records.append(record)
        except Exception as exc:
            logger.warning("Skipping malformed openinsider row: %s", exc)

    return records


# ---------------------------------------------------------------------------
# Synchronous fetch worker
# ---------------------------------------------------------------------------


def _fetch_openinsider_data(preset: str, custom_params: dict[str, str] | None) -> OpenInsiderResponse:
    """Synchronous worker: build URL, fetch HTML, parse table, return response.

    Retries once after a 1-second sleep on failure. Both attempts failing raises
    OpenInsiderFetchError. Cloudflare challenge detection runs before parsing
    and raises OpenInsiderFetchError immediately if triggered.

    Args:
        preset: Screener preset name or "custom".
        custom_params: Custom URL parameters for "custom" preset mode.

    Returns:
        OpenInsiderResponse with cached=False.

    Raises:
        OpenInsiderFetchError: After both fetch attempts fail, or on Cloudflare block.
    """
    url = build_screener_url(preset, custom_params)
    headers = {"User-Agent": _USER_AGENT}
    last_exc: Exception | None = None

    for attempt in range(2):
        try:
            response = httpx.get(url, headers=headers, timeout=15.0)
            response.raise_for_status()
            html = response.text
            resp_headers = dict(response.headers)
            if _detect_cloudflare_challenge(html, resp_headers):
                raise OpenInsiderFetchError(
                    "Cloudflare challenge detected -- openinsider.com may be blocking automated requests"
                )
            records = parse_openinsider_table(html)
            return OpenInsiderResponse(
                preset=preset,
                records=records,
                total=len(records),
                cached=False,
            )
        except OpenInsiderFetchError:
            raise
        except Exception as exc:
            last_exc = exc
            logger.warning("openinsider fetch attempt %d failed: %s", attempt + 1, exc)
            if attempt == 0:
                time.sleep(1)

    raise OpenInsiderFetchError(
        f"Failed to fetch openinsider.com after 2 attempts: {last_exc}"
    )


# ---------------------------------------------------------------------------
# Async entry point
# ---------------------------------------------------------------------------


async def get_openinsider_screener(
    preset: str, custom_params: dict[str, str] | None
) -> OpenInsiderResponse:
    """Async entry point for OpenInsider screener data.

    Checks the LRU+TTL cache first. On miss, delegates to the synchronous
    _fetch_openinsider_data worker via asyncio.to_thread and stores the result.
    On cache hit, returns a copy of the cached response with cached=True.

    Args:
        preset: Screener preset name ("ceo_cfo_conviction", "cluster_buy",
            "significant_increase") or "custom".
        custom_params: URL parameter dict for custom mode; ignored for presets.

    Returns:
        OpenInsiderResponse with cached=True on cache hit, cached=False on fresh fetch.

    Raises:
        OpenInsiderFetchError: Propagated from _fetch_openinsider_data on failure.
    """
    cache_key = f"openinsider:{preset}"
    if custom_params:
        sorted_params = "&".join(f"{k}={v}" for k, v in sorted(custom_params.items()))
        cache_key = f"{cache_key}:{sorted_params}"

    cached = _oi_cache_get(cache_key)
    if cached is not None:
        return OpenInsiderResponse(
            preset=cached.preset,
            records=cached.records,
            total=cached.total,
            cached=True,
        )

    result = await asyncio.to_thread(_fetch_openinsider_data, preset, custom_params)
    _oi_cache_put(cache_key, result)
    return result
