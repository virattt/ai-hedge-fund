"""LuckymanProvider — Luckyman (https://mcp.luckyman.app) as a
DataClient for the ai-hedge-fund v2 pipeline.

Luckyman is a free US-market data API (no auth, 60 req/min/IP):
    GET /history?symbol=AAPL&range=...   daily OHLCV bars
    GET /quotes?symbols=AAPL             live quote snapshot
    GET /filings?symbol=AAPL             SEC EDGAR filings
    GET /xbrl?symbol=AAPL&concept=...    SEC XBRL concept series
    GET /health                          source status

Contract honoured (see data/protocol.py): infrastructure failures RAISE
``LuckymanError``; 404 / genuinely-empty results return empty lists / None.
Luckyman has no /news, /earnings, /insider-trades, /company-facts or
pre-computed /financial-metrics endpoints — those methods return honest
empties (None / []) rather than fabrications; get_insider_trades derives
Form-4 filings from /filings (transaction amounts unavailable in the EDGAR
index — only the filing fact itself).

Usage::

    from hedge_fund.data.luckyman import LuckymanProvider

    with LuckymanProvider() as lm:
        prices = lm.get_prices("AAPL", "2024-01-01", "2024-12-31")
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

import requests

from hedge_fund.data.models import (
    InsiderTrade,
    Price,
    PriceSnapshot,
)

logger = logging.getLogger(__name__)

__all__ = ["LuckymanError", "LuckymanProvider", "HISTORY_RANGES"]


class LuckymanError(Exception):
    """Transport/API failure — protocol contract requires raising."""


HISTORY_RANGES = {
    "1w", "1mo", "2mo", "3mo", "6mo", "1y", "2y", "3y", "5y", "ytd", "max",
}

_USER_AGENT = "LuckymanProvider/0.1 (ai-hedge-fund; +https://mcp.luckyman.app)"


def _utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class LuckymanProvider:
    """Free, keyless subset of the DataClient protocol backed by mcp.luckyman.app."""

    BASE_URL = "https://mcp.luckyman.app"
    _RETRY_DELAYS = (5, 15, 30)

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["User-Agent"] = _USER_AGENT

    # Context manager -----------------------------------------------------

    def __enter__(self) -> "LuckymanProvider":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def close(self) -> None:
        self._session.close()

    def healthy(self) -> bool:
        """Cheap source check for /health consumers."""
        resp = self._request("GET", "/health")
        if resp is None:
            return False
        try:
            return bool(resp.json().get("status") == "healthy")
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # Prices
    # ------------------------------------------------------------------

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        interval: str = "day",
        interval_multiplier: int = 1,
    ) -> list[Price]:
        """Daily OHLCV bars via /history, date-scoped to [start_date, end_date].

        Luckyman takes a range keyword, not dates — this picks the smallest
        range covering end_date, then filters rows client-side. Non-day
        intervals are unsupported upstream and raise (fail-loud).
        """
        if interval != "day" or interval_multiplier != 1:
            raise LuckymanError(
                f"Luckyman /history supports daily bars only; got interval={interval!r}, multiplier={interval_multiplier!r}"
            )

        end = end_date[:10]
        start = start_date[:10]
        end_y, end_m = int(end[:4]), int(end[5:7])
        start_y, start_m = int(start[:4]), int(start[5:7])

        months_span = (end_y - start_y) * 12 + (end_m - start_m)
        if months_span < 0:
            raise LuckymanError(f"start_date {start} after end_date {end}")

        range_ = (
            "1w" if months_span < 1
            else "1mo" if months_span <= 1
            else "2mo" if months_span <= 2
            else "3mo" if months_span <= 3
            else "6mo" if months_span <= 6
            else "max" if months_span > 60
            else "1y" if months_span <= 12
            else "2y" if months_span <= 24
            else "3y" if months_span <= 36
            else "5y"  # <=60
        )
        if months_span <= 4:
            range_ = "1w" if months_span < 1 else range_  # keep 1w granularity for one-week needles

        rows = self._get(
            "/history",
            {"symbol": ticker.upper(), "range": range_},
            response_key=None,
        )
        out = []
        for row in rows or []:
            d = str(row.get("date", ""))[:10]
            if not (start <= d <= end):
                continue
            out.append(
                Price(
                    open=float(row["open"]),
                    close=float(row["close"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    volume=int(row.get("volume") or 0),
                    time=d,
                )
            )
        out.sort(key=lambda p: p.time)
        return out

    def get_snapshot(self, ticker: str) -> PriceSnapshot | None:
        """/quotes current bar. None if the ticker is unknown."""
        rows = self._get(
            "/quotes",
            {"symbols": ticker.upper()},
            response_key=None,
        )
        if not rows:
            return None
        q = rows[0]
        price = q.get("regularMarketPrice")
        if price is None:
            return None
        return PriceSnapshot(
            ticker=ticker.upper(),
            price=float(price),
            time=_utc_date() + "T00:00:00Z",  # Luckyman quote has no intraday timestamp field
            day_change=q.get("regularMarketChange"),
            day_change_percent=q.get("regularMarketChangePercent"),
        )

    # ------------------------------------------------------------------
    # Insider trades — derived from Form-4 filings
    # ------------------------------------------------------------------

    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
    ) -> list[InsiderTrade]:
        """/filings?form=4 project to InsiderTrade.

        Honest limitation: the EDGAR submissions index does not carry
        transaction amounts — only that a Form-4 was filed, by whom and
        when. Fields that need the form body (shares, price, after/before
        holdings) are left None; strategies requiring amounts should fetch
        the form4.xml via ``documentURL`` themselves.
        """
        params = {"symbol": ticker.upper(), "form": "4"}
        rows = self._get("/filings", params, response_key=None) or []
        out = []
        start_key = (start_date or "0000-01-01")[:10]
        end_key = end_date[:10]
        for row in rows:
            filed_raw = str(row.get("filedAt", ""))
            filed = filed_raw[:10]
            if not (start_key <= filed <= end_key):
                continue
            url = row.get("documentURL") or ""
            out.append(
                InsiderTrade(
                    ticker=ticker.upper(),
                    name=row.get("reportingOwner") or row.get("issuer") or "Form-4 filing",
                    filing_date=filed,
                    issuer=row.get("issuer"),
                    title=row.get("descriptionText"),
                    security_title="Form 4",
                    transaction_date=None,
                    transaction_type=None,
                    transaction_shares=None,
                    transaction_price_per_share=None,
                    transaction_value=None,
                )
            )
            if len(out) >= limit:
                break
        return out

    # ------------------------------------------------------------------
    # Unsupported upstream — honest empties
    # ------------------------------------------------------------------

    def get_news(self, *args, **kwargs):
        "Luckyman has no /news endpoint."
        return []

    def get_financial_metrics(self, *args, **kwargs):
        "Luckyman has no pre-computed ratios endpoint; use get_xbrl for raw facts."
        return []

    def get_company_facts(self, *args, **kwargs):
        "/xbrl is per-concept (one series), not a company-facts aggregate."
        return None

    def get_earnings(self, *args, **kwargs):
        "/earnings not offered."
        return None

    def get_earnings_history(self, *args, **kwargs):
        "/earnings not offered."
        return []

    def get_market_cap(self, ticker: str, end_date: str) -> float | None:
        """/quotes marketCap is live-only — as-of history is unavailable."""
        rows = self._get("/quotes", {"symbols": ticker.upper()}, response_key=None) or []
        if rows and rows[0].get("marketCap") is not None:
            return float(rows[0]["marketCap"])
        return None

    # ------------------------------------------------------------------
    # Extras (not in DataClient, but useful)
    # ------------------------------------------------------------------

    def get_xbrl(self, ticker: str, concept: str, limit: int = 12) -> dict:
        """SEC XBRL concept series — annual/quarterly USD values.

        Aliases: revenue, net_income, eps, cash, equity, assets,
        liabilities, operating_income, free_cash_flow; raw us-gaap tags
        also pass through.
        """
        rows = self._get(
            "/xbrl",
            {"symbol": ticker.upper(), "concept": concept},
            response_key=None,
        )
        return rows or {}

    # ------------------------------------------------------------------
    # HTTP core (fail-loud contract mirrors FDClient)
    # ------------------------------------------------------------------

    def _get(
        self,
        path: str,
        params: dict,
        response_key: str | None,
    ) -> list[dict] | dict | None:
        resp = self._request("GET", path, params=params)
        if resp is None:
            return None
        body = resp.json()
        if response_key is None:
            return body if isinstance(body, (list, dict)) else None
        rows = body.get(response_key)
        return rows if isinstance(rows, list) else None

    def _request(self, method: str, path: str, **kwargs) -> requests.Response | None:
        """Fail-loud: raises LuckymanError on network/HTTP errors and 429
        exhaustion. Returns None ONLY for 404 ("no such data")."""
        url = path if path.startswith("http") else self.BASE_URL + path
        for attempt, delay in enumerate((*self._RETRY_DELAYS, None)):
            try:
                resp = self._session.request(method, url, timeout=self._timeout, **kwargs)
            except requests.RequestException as exc:
                raise LuckymanError(f"{method} {path} failed: {exc}") from exc

            if resp.status_code == 429 and delay is not None:
                logger.info("Luckyman 429, retrying in %ds (attempt %d/%d)", delay, attempt + 1, len(self._RETRY_DELAYS))
                time.sleep(delay)
                continue

            if resp.status_code == 404:
                return None

            if resp.status_code >= 400:
                raise LuckymanError(
                    f"{method} {path} returned {resp.status_code}: {resp.text[:200]}",
                )

            return resp

        raise LuckymanError(f"{method} {path} rate limited (429) after {len(self._RETRY_DELAYS)} retries")


if __name__ == "__main__":
    # quick smoke: python -m hedge_fund.data.luckyman
    logging.basicConfig(level=logging.INFO)
    with LuckymanProvider() as lm:
        assert lm.healthy(), "Luckyman unhealthy"
        print("health ✓")
        bars = lm.get_prices("AAPL", "2026-01-01", _utc_date())
        print("bars:", len(bars), "first:", bars[0].time if bars else None)
        snap = lm.get_snapshot("AAPL")
        print("snapshot:", snap.price if snap else None)
        trades = lm.get_insider_trades("AAPL", _utc_date())
        print("form-4 count:", len(trades), "first:", trades[0].filing_date if trades else None)
        series = lm.get_xbrl("AAPL", "revenue")
        print("xbrl annual:", len(series.get("annual") or []), "quarterly:", len(series.get("quarterly") or []))
