"""Political & Policy service — USA Spending contracts + House Stock Watcher trades.

Fetches government contract awards from the free USA Spending API and
congressional stock trades from the House Stock Watcher S3 bucket.
All responses are cached for 1 hour in an OrderedDict-based LRU+TTL cache,
following the finnhub_service / openinsider_service pattern.
"""

import asyncio
import logging
import time
from collections import OrderedDict
from datetime import datetime, timedelta

import httpx

from app.backend.models.political_schemas import CongressTrade, CongressTradesResponse, GovContract, GovContractsResponse

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS: float = 3600.0
_CACHE_MAX_SIZE: int = 50

_USA_SPENDING_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
_HOUSE_STOCK_WATCHER_URL = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"

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


class PoliticalFetchError(Exception):
    """Raised when political data cannot be fetched."""


def _fetch_gov_contracts(companies: list[str]) -> GovContractsResponse:
    now = datetime.now()
    two_years_ago = now - timedelta(days=730)
    time_period = [{"start_date": two_years_ago.strftime("%Y-%m-%d"), "end_date": now.strftime("%Y-%m-%d")}]

    all_contracts: list[GovContract] = []
    errors: list[str] = []

    with httpx.Client(timeout=30.0) as client:
        for i, company in enumerate(companies):
            if i > 0:
                time.sleep(0.1)
            try:
                payload = {
                    "filters": {
                        "recipient_search_text": [company],
                        "award_type_codes": ["A", "B", "C", "D"],
                        "time_period": time_period,
                    },
                    "fields": ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "Start Date", "End Date", "Description"],
                    "limit": 25,
                    "page": 1,
                    "sort": "Award Amount",
                    "order": "desc",
                }
                resp = client.post(_USA_SPENDING_URL, json=payload)
                resp.raise_for_status()
                data = resp.json()
                for row in data.get("results", []):
                    all_contracts.append(GovContract(
                        award_id=row.get("Award ID"),
                        recipient_name=row.get("Recipient Name"),
                        award_amount=row.get("Award Amount"),
                        awarding_agency=row.get("Awarding Agency"),
                        start_date=row.get("Start Date"),
                        end_date=row.get("End Date"),
                        description=row.get("Description"),
                    ))
            except Exception as exc:
                logger.warning("Failed to fetch contracts for %s: %s", company, exc)
                errors.append(company)

    if errors and len(errors) == len(companies):
        raise PoliticalFetchError(f"Failed to fetch contracts for all companies: {', '.join(errors)}")

    all_contracts.sort(key=lambda c: c.award_amount or 0, reverse=True)
    return GovContractsResponse(contracts=all_contracts, total=len(all_contracts), cached=False)


def _fetch_congress_trades(ticker: str | None) -> CongressTradesResponse:
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(_HOUSE_STOCK_WATCHER_URL)
            resp.raise_for_status()
            raw = resp.json()
    except Exception as exc:
        logger.warning("House Stock Watcher unavailable: %s", exc)
        return CongressTradesResponse(trades=[], total=0, source_available=False, cached=False)

    trades: list[CongressTrade] = []
    for row in raw:
        row_ticker = (row.get("ticker") or "").strip().upper()
        if ticker and row_ticker != ticker.strip().upper():
            continue
        trades.append(CongressTrade(
            representative=row.get("representative"),
            ticker=row_ticker or None,
            transaction_type=row.get("type"),
            amount=row.get("amount"),
            transaction_date=row.get("transaction_date"),
            disclosure_date=row.get("disclosure_date"),
            district=row.get("district"),
            ptr_link=row.get("ptr_link"),
        ))

    trades.sort(key=lambda t: t.transaction_date or "", reverse=True)
    return CongressTradesResponse(trades=trades[:500], total=len(trades), source_available=True, cached=False)


async def get_gov_contracts(companies: list[str]) -> GovContractsResponse:
    cache_key = f"political:contracts:{','.join(sorted(c.lower() for c in companies))}"
    cached = _cache_get(cache_key)
    if cached is not None and isinstance(cached, GovContractsResponse):
        return GovContractsResponse(contracts=cached.contracts, total=cached.total, cached=True)

    result = await asyncio.to_thread(_fetch_gov_contracts, companies)
    _cache_put(cache_key, result)
    return result


async def get_congress_trades(ticker: str | None = None) -> CongressTradesResponse:
    cache_key = f"political:congress:{(ticker or 'ALL').upper()}"
    cached = _cache_get(cache_key)
    if cached is not None and isinstance(cached, CongressTradesResponse):
        return CongressTradesResponse(trades=cached.trades, total=cached.total, source_available=cached.source_available, cached=True)

    result = await asyncio.to_thread(_fetch_congress_trades, ticker)
    _cache_put(cache_key, result)
    return result
