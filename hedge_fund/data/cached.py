"""Disk-cached DataClient wrapper.

Wraps any DataClient with a JSON file cache under ~/.hedge-fund/cache/data/. A warm
cache reuses completed historical responses. Daily prices are reusable only
when fetched after the requested end date has ended in New York; anything
else asked about a day that has not ended (today's headlines, today's
minute bars) is reused for ten minutes, the news feed's own refresh, and
fetched again after. `live=True` gives the date-less "latest" answers
(earnings, company facts) the same ten minutes, for a process that stays
up all day and would otherwise never see a new filing.

    fd = CachedDataClient(FDClient())
    prices = fd.get_prices("AAPL", "2024-01-01", "2024-12-31")  # API call
    prices = fd.get_prices("AAPL", "2024-01-01", "2024-12-31")  # disk, ~0ms

Failure semantics are inherited: only successful responses are cached, and
errors from the wrapped client propagate (fail-loud preserved). Pass
refresh=True to ignore existing entries (they are rewritten on fetch).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Callable

from hedge_fund.data.models import (
    CompanyFacts,
    CompanyNews,
    Earnings,
    EarningsRecord,
    FinancialMetrics,
    InsiderTrade,
    Price,
)
from hedge_fund.data.protocol import DataClient
from hedge_fund.data.sessions import NEW_YORK
from hedge_fund.paths import CACHE_DIR

DEFAULT_CACHE_DIR = CACHE_DIR / "data"
SAME_DAY_TTL = 600  # seconds an answer about an unfinished day stays fresh


class CachedDataClient:
    """DataClient that memoizes another DataClient's responses on disk."""

    def __init__(
        self,
        client: DataClient,
        cache_dir: Path | str = DEFAULT_CACHE_DIR,
        refresh: bool = False,
        live: bool = False,
    ) -> None:
        self._client = client
        self._dir = Path(cache_dir)
        self._refresh = refresh
        self._live = live

    # ------------------------------------------------------------------
    # DataClient protocol
    # ------------------------------------------------------------------

    def get_prices(self, ticker, start_date, end_date, interval="day", interval_multiplier=1):
        return self._cached_list(
            "get_prices", Price,
            {"ticker": ticker, "start_date": start_date, "end_date": end_date,
             "interval": interval, "interval_multiplier": interval_multiplier},
            lambda: self._client.get_prices(
                ticker, start_date, end_date, interval, interval_multiplier),
        )

    def get_snapshot(self, ticker):
        # A quote is stale the moment it arrives; never served from disk.
        return self._client.get_snapshot(ticker)

    def get_financial_metrics(self, ticker, end_date, period="ttm", limit=10):
        return self._cached_list(
            "get_financial_metrics", FinancialMetrics,
            {"ticker": ticker, "end_date": end_date, "period": period, "limit": limit},
            lambda: self._client.get_financial_metrics(ticker, end_date, period, limit),
        )

    def get_news(self, ticker, end_date, start_date=None, limit=1000):
        return self._cached_list(
            "get_news", CompanyNews,
            {"ticker": ticker, "end_date": end_date, "start_date": start_date, "limit": limit},
            lambda: self._client.get_news(ticker, end_date, start_date, limit),
        )

    def get_insider_trades(self, ticker, end_date, start_date=None, limit=1000):
        return self._cached_list(
            "get_insider_trades", InsiderTrade,
            {"ticker": ticker, "end_date": end_date, "start_date": start_date, "limit": limit},
            lambda: self._client.get_insider_trades(ticker, end_date, start_date, limit),
        )

    def get_earnings_history(self, ticker, limit=12):
        return self._cached_list(
            "get_earnings_history", EarningsRecord,
            {"ticker": ticker, "limit": limit},
            lambda: self._client.get_earnings_history(ticker, limit),
        )

    def get_company_facts(self, ticker):
        return self._cached_item(
            "get_company_facts", CompanyFacts, {"ticker": ticker},
            lambda: self._client.get_company_facts(ticker),
        )

    def get_earnings(self, ticker):
        return self._cached_item(
            "get_earnings", Earnings, {"ticker": ticker},
            lambda: self._client.get_earnings(ticker),
        )

    def get_market_cap(self, ticker, end_date):
        return self._cached_scalar(
            "get_market_cap", {"ticker": ticker, "end_date": end_date},
            lambda: self._client.get_market_cap(ticker, end_date),
        )

    # ------------------------------------------------------------------
    # Cache mechanics
    # ------------------------------------------------------------------

    def _key(self, method: str, params: dict) -> str:
        canonical = json.dumps(params, sort_keys=True)
        return hashlib.sha256(f"{method}|{canonical}".encode()).hexdigest()[:24]

    def _read(self, key: str) -> dict | None:
        if self._refresh:
            return None
        path = self._dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None  # corrupt entry -> miss; rewritten on fetch

    def _write(self, key: str, payload: dict) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / f"{key}.json").write_text(json.dumps(payload))

    def _fresh(self, hit: dict, method: str, params: dict) -> bool:
        """Whether a cached answer can still be served.

        Answers about a day that had ended when they were fetched are
        final. Answers about an unfinished day are not: a daily bar for it
        is never reused (the close is not in yet); anything else is reused
        for SAME_DAY_TTL and then asked for again. Date-less "latest"
        answers are final unless the client is live. Entries written before
        fetch times were recorded are trusted, except the daily bar, which
        was never trusted without one.
        """
        daily_bar = method == "get_prices" and params.get("interval") == "day"
        end = params.get("end_date")
        try:
            fetched = datetime.fromisoformat(hit["fetched_at"])
            if fetched.tzinfo is None:
                raise ValueError("naive fetch time")
        except (KeyError, TypeError, ValueError):
            return not daily_bar
        if method == "get_earnings_history":
            today = datetime.now(NEW_YORK).date().isoformat()
            return fetched.astimezone(NEW_YORK).date().isoformat() >= today
        if end is None:
            if not self._live:
                return True
        elif fetched.astimezone(NEW_YORK).date().isoformat() > end:
            return True
        elif daily_bar:
            return False
        return (datetime.now(NEW_YORK) - fetched).total_seconds() < SAME_DAY_TTL

    def _cached_list(self, method: str, model_cls, params: dict, fetch: Callable) -> list:
        key = self._key(method, params)
        hit = self._read(key)
        if hit is not None and self._fresh(hit, method, params):
            return [model_cls(**row) for row in hit["data"]]
        fetched_at = datetime.now(NEW_YORK).isoformat()
        result = fetch()
        self._write(key, {"data": [r.model_dump() for r in result], "fetched_at": fetched_at})
        return result

    def _cached_item(self, method: str, model_cls, params: dict, fetch: Callable):
        key = self._key(method, params)
        hit = self._read(key)
        if hit is not None and self._fresh(hit, method, params):
            return model_cls(**hit["data"]) if hit["data"] is not None else None
        fetched_at = datetime.now(NEW_YORK).isoformat()
        result = fetch()
        self._write(key, {"data": result.model_dump() if result is not None else None,
                          "fetched_at": fetched_at})
        return result

    def _cached_scalar(self, method: str, params: dict, fetch: Callable):
        key = self._key(method, params)
        hit = self._read(key)
        if hit is not None and self._fresh(hit, method, params):
            return hit["data"]
        fetched_at = datetime.now(NEW_YORK).isoformat()
        result = fetch()
        self._write(key, {"data": result, "fetched_at": fetched_at})
        return result
