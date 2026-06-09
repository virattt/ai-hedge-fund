"""Catalyst service — surfaces SEC catalysts (Form 10/10-12B spin-offs in v1).

Cache: 1-hour TTL, 20 entries max. Form 10s appear infrequently so a long TTL
is fine. On cache miss, refresh DB from EDGAR then read paginated results.
"""

import asyncio
import logging
import time
from collections import OrderedDict

from app.backend.database import SessionLocal
from app.backend.database.models import SpinoffFiling
from app.backend.models.catalyst_schemas import SpinoffInsiderSummary, SpinoffListResponse

from ._fetch import SpinoffFetchError, fetch_recent_spinoffs, read_filings_from_db
from ._insiders import fetch_insider_purchases_by_cik

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS: float = 3600.0  # 1 hour
_CACHE_MAX_SIZE: int = 20

_cache: OrderedDict[str, tuple[object, float]] = OrderedDict()


def _cache_get(cache_key: str) -> object | None:
    entry = _cache.get(cache_key)
    if entry is None:
        return None
    response, timestamp = entry
    if time.monotonic() - timestamp > _CACHE_TTL_SECONDS:
        _cache.pop(cache_key, None)
        return None
    return response


def _cache_put(cache_key: str, response: object) -> None:
    _cache[cache_key] = (response, time.monotonic())
    while len(_cache) > _CACHE_MAX_SIZE:
        _cache.popitem(last=False)


def _build_spinoff_response(
    date_from: str | None,
    date_to: str | None,
    limit: int,
    offset: int,
    refresh: bool,
) -> SpinoffListResponse:
    if refresh:
        try:
            fetch_recent_spinoffs(days_back=90)
        except Exception as exc:
            logger.warning("Spin-off EDGAR sync failed (using cached DB rows): %s", exc)
    items, total = read_filings_from_db(date_from, date_to, limit, offset)
    return SpinoffListResponse(filings=items, total=total, cached=False)


async def get_spinoff_filings(
    date_from: str | None,
    date_to: str | None,
    limit: int,
    offset: int,
) -> SpinoffListResponse:
    cache_key = f"catalyst:spinoffs:{date_from or ''}:{date_to or ''}:{limit}:{offset}"
    cached = _cache_get(cache_key)
    if cached is not None and isinstance(cached, SpinoffListResponse):
        return SpinoffListResponse(filings=cached.filings, total=cached.total, cached=True)

    result = await asyncio.to_thread(
        _build_spinoff_response, date_from, date_to, limit, offset, True
    )
    _cache_put(cache_key, result)
    return result


def _earliest_filing_date_for_cik(cik: int) -> str | None:
    """Return the oldest spin-off filing_date for this CIK, used as the
    'since_date' floor for insider Form 4 lookups (skip pre-spin filings)."""
    db = SessionLocal()
    try:
        row = (
            db.query(SpinoffFiling.filing_date)
            .filter(SpinoffFiling.cik == cik)
            .order_by(SpinoffFiling.filing_date.asc())
            .first()
        )
        return row[0] if row else None
    finally:
        db.close()


async def get_spinoff_insiders(cik: int) -> SpinoffInsiderSummary:
    cache_key = f"catalyst:insiders:{cik}"
    cached = _cache_get(cache_key)
    if cached is not None and isinstance(cached, SpinoffInsiderSummary):
        return SpinoffInsiderSummary(
            cik=cached.cik,
            purchase_count=cached.purchase_count,
            total_value=cached.total_value,
            purchases=cached.purchases,
            cached=True,
        )
    since_date = _earliest_filing_date_for_cik(cik)
    result = await asyncio.to_thread(fetch_insider_purchases_by_cik, cik, since_date)
    _cache_put(cache_key, result)
    return result


__all__ = ["SpinoffFetchError", "get_spinoff_filings", "get_spinoff_insiders"]
