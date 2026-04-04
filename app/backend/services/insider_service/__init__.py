"""Insider trading service package.

The cache state (_insider_cache, _CACHE_TTL_SECONDS, _CACHE_MAX_SIZE) and
cache helpers (_cache_get, _cache_put) are defined directly in this __init__
so that existing tests using patch.object(insider_service, "_CACHE_TTL_SECONDS")
continue to work: the patched name and the running code share the same module
globals.

get_ownership_changes and get_insider_grants are defined here so that tests
patching insider_service._fetch_ownership_changes and
insider_service._grants._fetch_grants intercept the calls correctly.

All other logic lives in sub-modules (_summary, _detail, _ownership, _grants,
_helpers) and is imported here for backwards-compatible access.
"""
import asyncio
import time
from collections import OrderedDict

from app.backend.models.insider_schemas import GrantsResponse, OwnershipChangesResponse
from app.backend.services.insider_service._detail import _fetch_detail, _parse_trade_rows, get_insider_detail
from app.backend.services.insider_service._grants import _fetch_grants
from app.backend.services.insider_service._helpers import (
    InitialOwnershipSummaryProtocol,
    TransactionSummaryProtocol,
    _classify_transaction_type,
    _coerce_float,
    _coerce_int,
    _ensure_identity,
    _iter_parsed_filings,
)
from app.backend.services.insider_service._ownership import _fetch_ownership_changes
from app.backend.services.insider_service._summary import (
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
    cache_key = f"ownership:{ticker.upper()}:{form_type}"
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
    cache_key = f"grants:{ticker.upper()}:{form_type}"
    cached = _cache_get(cache_key)
    if isinstance(cached, GrantsResponse):
        return cached
    result = await asyncio.to_thread(_grants._fetch_grants, ticker, form_type, limit, offset)
    _cache_put(cache_key, result)
    return result
