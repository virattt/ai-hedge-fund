"""Insider trading service package.

The cache state (_insider_cache, _CACHE_TTL_SECONDS, _CACHE_MAX_SIZE) and
cache helpers (_cache_get, _cache_put) are defined directly in this __init__
so that existing tests using patch.object(insider_service, "_CACHE_TTL_SECONDS")
continue to work: the patched name and the running code share the same module
globals.

get_ownership_changes and get_insider_grants are defined here so that tests
patching insider_service._fetch_ownership_changes and
insider_service._grants._fetch_grants intercept the calls correctly.

The 13F-HR entry points (get_thirteenf_filings, get_compare_holdings,
get_holding_history) are also defined here so that tests can patch
insider_service._fetch_thirteenf_filings, insider_service._fetch_compare_holdings,
and insider_service._fetch_holding_history to intercept the calls correctly.

All other logic lives in sub-modules (_summary, _detail, _ownership, _grants,
_helpers, _thirteenf) and is imported here for backwards-compatible access.
"""
import asyncio
import time
from collections import OrderedDict
from datetime import date

from app.backend.models.insider_schemas import (  # noqa: F401
    CompareHoldingsResponse,
    GrantsResponse,
    HoldingHistoryResponse,
    OwnershipChangesResponse,
    ThirteenFListResponse,
)
from app.backend.services.insider_service._thirteenf import (  # noqa: F401
    _fetch_compare_holdings,
    _fetch_holding_history,
    _fetch_thirteenf_filings,
)
from app.backend.services.insider_service._detail import _fetch_detail, _parse_trade_rows, get_insider_detail  # noqa: F401
from app.backend.services.insider_service._grants import _fetch_grants  # noqa: F401
from app.backend.services.insider_service._helpers import (  # noqa: F401
    InitialOwnershipSummary,
    TransactionSummary,
    _classify_transaction_type,
    _coerce_float,
    _coerce_int,
    _ensure_identity,
    _iter_parsed_filings,
)
from app.backend.services.insider_service._ownership import _fetch_ownership_changes  # noqa: F401
from app.backend.services.insider_service._summary import (  # noqa: F401
    _build_filing_summary,
    _build_filing_summary_from_initial,
    _build_filing_summary_from_transaction,
    _compute_activity_by_date,
    _compute_aggregates,
    _fetch_summaries,
    get_insider_summary,
)
from app.backend.services.insider_service import _grants

# ---------------------------------------------------------------------------
# LRU+TTL cache — defined here so patch.object(insider_service, "_CACHE_TTL_SECONDS")
# patches the same namespace that _cache_get/_cache_put read from.
# ---------------------------------------------------------------------------

_insider_cache: OrderedDict[str, tuple[object, float]] = OrderedDict()
_CACHE_TTL_SECONDS: float = 300.0  # 5 minutes
_CACHE_MAX_SIZE: int = 50


def _cache_get(cache_key: str) -> object | None:
    """Return cached response if present and not expired, else None.

    Evicts the entry when it has expired.
    """
    import app.backend.services.insider_service as _self
    entry = _insider_cache.get(cache_key)
    if entry is None:
        return None
    response, timestamp = entry
    if time.monotonic() - timestamp > _self._CACHE_TTL_SECONDS:
        _insider_cache.pop(cache_key, None)
        return None
    return response


def _cache_put(cache_key: str, response: object) -> None:
    """Store response with current timestamp. Evicts oldest entry if over max size."""
    import app.backend.services.insider_service as _self
    _insider_cache[cache_key] = (response, time.monotonic())
    while len(_insider_cache) > _self._CACHE_MAX_SIZE:
        _insider_cache.popitem(last=False)


# ---------------------------------------------------------------------------
# Ownership changes async entry point — defined here so tests can patch
# insider_service._fetch_ownership_changes to intercept the call.
# ---------------------------------------------------------------------------


async def get_ownership_changes(ticker: str, form_type: str = "4", limit: int = 50, offset: int = 0) -> OwnershipChangesResponse:
    """Async entry point for ownership changes. Checks LRU+TTL cache first."""
    cache_key = f"ownership:{ticker.upper()}:{form_type}:{limit}:{offset}"
    cached = _cache_get(cache_key)
    if isinstance(cached, OwnershipChangesResponse):
        return cached
    result = await asyncio.to_thread(_fetch_ownership_changes, ticker, form_type, limit, offset)
    _cache_put(cache_key, result)
    return result


# ---------------------------------------------------------------------------
# Grants async entry point — defined here so cache helpers are shared.
# ---------------------------------------------------------------------------


async def get_insider_grants(ticker: str, form_type: str = "4", limit: int = 50, offset: int = 0) -> GrantsResponse:
    """Async entry point for grants & exercises. Checks LRU+TTL cache first."""
    cache_key = f"grants:{ticker.upper()}:{form_type}:{limit}:{offset}"
    cached = _cache_get(cache_key)
    if isinstance(cached, GrantsResponse):
        return cached
    result = await asyncio.to_thread(_grants._fetch_grants, ticker, form_type, limit, offset)
    _cache_put(cache_key, result)
    return result


# ---------------------------------------------------------------------------
# 13F-HR async entry points — defined here so tests can patch
# insider_service._fetch_thirteenf_filings etc. to intercept calls.
# ---------------------------------------------------------------------------


async def get_thirteenf_filings(
    limit: int,
    offset: int,
    year: int | None,
    quarter: int | None,
) -> ThirteenFListResponse:
    """Async entry point for paginated 13F-HR filing listing. Checks LRU+TTL cache first.

    The cache key includes today's date (``date.today().isoformat()``) so that
    the listing expires daily and new SEC filings are picked up automatically.

    Args:
        limit: Maximum number of filings to return (page size).
        offset: Number of filings to skip before the current page.
        year: Optional filing year filter; forwarded to the worker when not None.
        quarter: Optional filing quarter filter (1–4); forwarded when not None.

    Returns:
        ThirteenFListResponse with filings, total count, has_more, and skipped_count.
    """
    cache_key = f"thirteenf:filings:{date.today().isoformat()}:{year}:{quarter}:{limit}:{offset}"
    cached = _cache_get(cache_key)
    if isinstance(cached, ThirteenFListResponse):
        return cached
    result = await asyncio.to_thread(_fetch_thirteenf_filings, limit, offset, year, quarter)
    _cache_put(cache_key, result)
    return result


async def get_compare_holdings(accession_no: str) -> CompareHoldingsResponse:
    """Async entry point for quarter-over-quarter holding comparison. Checks LRU+TTL cache first.

    ValueError from the worker (no comparison data, filing not found) is not
    caught here — it propagates to the route handler for 404 mapping.

    Args:
        accession_no: SEC accession number in ``NNNNNNNNNN-YY-NNNNNN`` format.

    Returns:
        CompareHoldingsResponse with records and period metadata.

    Raises:
        ValueError: Propagated from worker when comparison data is unavailable.
        RuntimeError: Propagated from worker on SEC API errors.
    """
    cache_key = f"thirteenf:compare:{accession_no}"
    cached = _cache_get(cache_key)
    if isinstance(cached, CompareHoldingsResponse):
        return cached
    result = await asyncio.to_thread(_fetch_compare_holdings, accession_no)
    _cache_put(cache_key, result)
    return result


async def get_holding_history(accession_no: str, periods: int) -> HoldingHistoryResponse:
    """Async entry point for multi-period holding history. Checks LRU+TTL cache first.

    ValueError from the worker (no history data, filing not found) is not
    caught here — it propagates to the route handler for 404 mapping.

    Args:
        accession_no: SEC accession number in ``NNNNNNNNNN-YY-NNNNNN`` format.
        periods: Number of historical periods to include.

    Returns:
        HoldingHistoryResponse with records and ordered period list.

    Raises:
        ValueError: Propagated from worker when history data is unavailable.
        RuntimeError: Propagated from worker on SEC API errors.
    """
    cache_key = f"thirteenf:history:{accession_no}:{periods}"
    cached = _cache_get(cache_key)
    if isinstance(cached, HoldingHistoryResponse):
        return cached
    result = await asyncio.to_thread(_fetch_holding_history, accession_no, periods)
    _cache_put(cache_key, result)
    return result
