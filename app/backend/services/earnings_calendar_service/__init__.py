"""Earnings calendar service — fetches upcoming earnings dates from Finnhub.

Finnhub `/api/v1/calendar/earnings?from=YYYY-MM-DD&to=YYYY-MM-DD&token=...` returns
all companies reporting in the date range. Cached 4h since calendar data
changes infrequently. Tickers normalized uppercase.

Free tier: 60 requests/min, includes earnings calendar. Sign up at finnhub.io.

Used both by the Calendar page UI and the watchlist batch (smart-skip:
only re-analyze tickers that have earnings in the next N days).
"""

import asyncio
import logging
import os
import time
from collections import OrderedDict
from datetime import date, timedelta

import httpx

from app.backend.models.calendar_schemas import EarningsCalendarItem, EarningsCalendarResponse

logger = logging.getLogger(__name__)

_FINNHUB_BASE = "https://finnhub.io/api/v1"
_CACHE_TTL_SECONDS: float = 4 * 3600.0  # 4 hours
_CACHE_MAX_SIZE: int = 30
_PLACEHOLDER_PREFIXES = ("your-", "placeholder", "change-me", "sk-xxx")
_cache: OrderedDict[str, tuple[object, float]] = OrderedDict()


def _cache_get(key: str) -> object | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    response, ts = entry
    if time.monotonic() - ts > _CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return response


def _cache_put(key: str, response: object) -> None:
    _cache[key] = (response, time.monotonic())
    while len(_cache) > _CACHE_MAX_SIZE:
        _cache.popitem(last=False)


def _real_finnhub_key() -> str | None:
    key = os.environ.get("FINNHUB_API_KEY", "").strip()
    if not key:
        return None
    if any(key.lower().startswith(p) for p in _PLACEHOLDER_PREFIXES):
        return None
    return key


def _fetch_finnhub_calendar(date_from: str, date_to: str) -> list[EarningsCalendarItem]:
    """Sync Finnhub fetch. Returns empty list on any failure."""
    key = _real_finnhub_key()
    if not key:
        logger.info("FINNHUB_API_KEY not configured — earnings calendar disabled")
        return []

    url = f"{_FINNHUB_BASE}/calendar/earnings"
    params = {"from": date_from, "to": date_to, "token": key}

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Finnhub earnings calendar fetch failed: %s", exc)
        return []

    raw_list = data.get("earningsCalendar") if isinstance(data, dict) else None
    if not isinstance(raw_list, list):
        logger.warning("Finnhub earnings calendar returned unexpected payload: %s", type(data))
        return []

    items: list[EarningsCalendarItem] = []
    for raw in raw_list:
        try:
            ticker = str(raw.get("symbol") or "").strip().upper()
            if not ticker:
                continue
            items.append(EarningsCalendarItem(
                date=str(raw.get("date") or "")[:10],
                ticker=ticker,
                company=ticker,  # Finnhub doesn't return name in this endpoint; UI shows ticker
                eps_estimate=raw.get("epsEstimate"),
                eps_actual=raw.get("epsActual"),
                revenue_estimate=raw.get("revenueEstimate"),
                revenue_actual=raw.get("revenueActual"),
                hour=raw.get("hour"),  # "bmo" / "amc" / "dmh"
                quarter=raw.get("quarter"),
                fiscal_year=raw.get("year"),
            ))
        except Exception as exc:
            logger.debug("Skipping malformed Finnhub calendar entry: %s", exc)
            continue
    return items


async def get_calendar(date_from: str, date_to: str) -> EarningsCalendarResponse:
    cache_key = f"calendar:{date_from}:{date_to}"
    cached = _cache_get(cache_key)
    if cached is not None and isinstance(cached, EarningsCalendarResponse):
        return EarningsCalendarResponse(
            items=cached.items,
            date_from=cached.date_from,
            date_to=cached.date_to,
            total=cached.total,
            cached=True,
        )
    items = await asyncio.to_thread(_fetch_finnhub_calendar, date_from, date_to)
    response = EarningsCalendarResponse(
        items=items,
        date_from=date_from,
        date_to=date_to,
        total=len(items),
        cached=False,
    )
    _cache_put(cache_key, response)
    return response


async def get_tickers_reporting_soon(tickers: list[str], days: int = 7) -> set[str]:
    """Return the subset of tickers that have earnings in the next `days` days.

    Returns empty set if FINNHUB_API_KEY is missing or fetch fails — callers
    should treat that as "unknown, don't filter."
    """
    if not tickers:
        return set()
    today = date.today()
    end = today + timedelta(days=days)
    response = await get_calendar(today.isoformat(), end.isoformat())
    if response.total == 0:
        return set()
    upcoming = {item.ticker.upper() for item in response.items}
    requested = {t.upper() for t in tickers}
    return upcoming & requested


def is_calendar_available() -> bool:
    """True if FINNHUB_API_KEY is set to a real-looking value."""
    return _real_finnhub_key() is not None


__all__ = ["get_calendar", "get_tickers_reporting_soon", "is_calendar_available"]
