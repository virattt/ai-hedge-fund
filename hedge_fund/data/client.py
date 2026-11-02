"""Financial Datasets API client."""

from __future__ import annotations

import base64
import json
import logging
import os
import time

import requests

from hedge_fund.data.models import (
    CompanyFacts,
    CompanyNews,
    Earnings,
    EarningsRecord,
    FinancialMetrics,
    InsiderTrade,
    Price,
    PriceSnapshot,
)
from hedge_fund.data.wallet import payment_session, WALLET_KEY_ENV

logger = logging.getLogger(__name__)

NEWS_PAGE = 10  # the most /news/ returns per request
API_KEY_ENV = "FINANCIAL_DATASETS_API_KEY"
# x402 answers only this far back; older dates get a 403 with the window start.
X402_HISTORY_DAYS = 365


def payment_error(resp: requests.Response) -> str:
    """Why a paid retry still came back 402. The body carries only the
    generic "Payment required"; the reason (no USDC, a rejected signature,
    a blocked payer) is the ``error`` field of the base64 JSON in the
    PAYMENT-REQUIRED header."""
    header = resp.headers.get("PAYMENT-REQUIRED", "")
    try:
        terms = json.loads(base64.b64decode(header + "=" * (-len(header) % 4)))
    except (ValueError, UnicodeDecodeError):
        return "no payment terms in the response"
    return str(terms.get("error") or "no reason given")[:300]


def has_data_credential() -> bool:
    """True when the environment holds something a request can be billed to:
    an API key, or a wallet to pay per call with x402. The one place that
    decides it, so the TUI gates and the client cannot disagree."""
    return bool(os.environ.get(API_KEY_ENV) or os.environ.get(WALLET_KEY_ENV))


class FDClientError(Exception):
    """An API request failed for infrastructure reasons (auth, rate limit,
    server error, network). Distinct from "no data exists" — that returns
    empty. A backtest must crash on this, not treat it as no-data.
    """

    def __init__(self, message: str, *, status_code: int | None = None, path: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.path = path


class FDClient:
    """Financial Datasets API client.

    Usage::

        with FDClient() as fd:
            prices = fd.get_prices("AAPL", "2024-01-01", "2024-12-31")
    """

    BASE_URL = "https://api.financialdatasets.ai"
    _RETRY_DELAYS = (5, 15, 30)

    def __init__(
        self,
        api_key: str | None = None,
        wallet_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """An API key bills the account; otherwise a wallet key pays each
        call with x402. Both set means the key wins, which is the API's own
        rule: a request carrying X-API-KEY is never charged to a wallet."""
        self._api_key = api_key or os.environ.get(API_KEY_ENV, "")
        self._wallet_key = wallet_key or os.environ.get(WALLET_KEY_ENV, "")
        self._timeout = timeout
        if self.pays_per_call():
            try:
                self._session = payment_session(self._wallet_key)
            except ImportError as exc:
                raise FDClientError(str(exc)) from exc
        else:
            self._session = requests.Session()
            self._session.headers["X-API-Key"] = self._api_key

    def pays_per_call(self) -> bool:
        """Whether requests go out keyless and pay with x402."""
        return not self._api_key and bool(self._wallet_key)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> FDClient:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()

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
        """Fetch OHLC price bars."""
        data = self._get("/prices/", {
            "ticker": ticker,
            "interval": interval,
            "interval_multiplier": interval_multiplier,
            "start_date": start_date,
            "end_date": end_date,
        }, response_key="prices")
        return [Price(**row) for row in data] if data else []

    def get_snapshot(self, ticker: str) -> PriceSnapshot | None:
        """Fetch the real-time quote. None if the ticker is unknown."""
        resp = self._request("GET", "/prices/snapshot/", params={"ticker": ticker})
        if resp is None:
            return None
        row = resp.json().get("snapshot")
        return PriceSnapshot(**row) if row else None

    # ------------------------------------------------------------------
    # Financial Metrics
    # ------------------------------------------------------------------

    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
    ) -> list[FinancialMetrics]:
        """Fetch financial metrics that were PUBLIC as of *end_date*.

        Point-in-time: filters on ``filing_date`` (when the SEC filing was
        accepted, ET) — not ``report_period`` (the fiscal period end, which
        precedes public availability by 3-6 weeks and would leak the future
        into a backtest). Rows without a known filing_date are excluded
        server-side, so everything returned was provably knowable on
        *end_date*.
        """
        data = self._get("/financial-metrics/", {
            "ticker": ticker,
            "filing_date_lte": end_date,
            "period": period,
            "limit": limit,
        }, response_key="financial_metrics")
        return [FinancialMetrics(**row) for row in data] if data else []

    # ------------------------------------------------------------------
    # News
    # ------------------------------------------------------------------

    def get_news(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
    ) -> list[CompanyNews]:
        """Fetch company news: the newest items first, at most *limit*.
        /news/ serves no more than NEWS_PAGE per request and rejects a
        larger ask, so the request is clamped to what it can answer."""
        params: dict = {"ticker": ticker, "end_date": end_date, "limit": min(limit, NEWS_PAGE)}
        if start_date is not None:
            params["start_date"] = start_date
        data = self._get("/news/", params, response_key="news")
        return [CompanyNews(**row) for row in data] if data else []

    # ------------------------------------------------------------------
    # Insider Trades
    # ------------------------------------------------------------------

    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
    ) -> list[InsiderTrade]:
        """Fetch insider trades."""
        params: dict = {"ticker": ticker, "filing_date_lte": end_date, "limit": limit}
        if start_date is not None:
            params["filing_date_gte"] = start_date
        data = self._get("/insider-trades/", params, response_key="insider_trades")
        return [InsiderTrade(**row) for row in data] if data else []

    # ------------------------------------------------------------------
    # Company Facts
    # ------------------------------------------------------------------

    def get_company_facts(self, ticker: str) -> CompanyFacts | None:
        """Fetch company metadata (single record)."""
        resp = self._request("GET", "/company/facts/", params={"ticker": ticker})
        if resp is None:
            return None
        facts_data = resp.json().get("company_facts")
        return CompanyFacts(**facts_data) if facts_data else None

    # ------------------------------------------------------------------
    # Earnings
    # ------------------------------------------------------------------

    def get_earnings(self, ticker: str) -> Earnings | None:
        """Fetch latest earnings for a single ticker.

        limit=1 (one report period) — only [0] is used, and without a limit
        the pagination loop in _get would walk the ticker's entire feed.
        """
        data = self._get("/earnings/", {"ticker": ticker, "limit": 1}, response_key="earnings")
        if not data:
            return None
        row = data[0] if isinstance(data, list) else data
        return Earnings(**row)

    def get_earnings_history(
        self,
        ticker: str,
        limit: int = 12,
    ) -> list[EarningsRecord]:
        """Fetch historical earnings filings as a flat list.

        Returns one record per SEC filing (8-K, 10-Q, 10-K, 20-F).
        The same ``report_period`` may appear multiple times with
        different ``source_type`` values.
        """
        data = self._get("/earnings/", {
            "ticker": ticker,
            "limit": limit,
        }, response_key="earnings")
        return [EarningsRecord(**row) for row in data] if data else []

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def get_market_cap(self, ticker: str, end_date: str) -> float | None:
        """Return market cap from company facts or financial metrics."""
        facts = self.get_company_facts(ticker)
        if facts is not None and facts.market_cap is not None:
            return facts.market_cap
        metrics = self.get_financial_metrics(ticker, end_date, limit=1)
        if metrics and metrics[0].market_cap is not None:
            return metrics[0].market_cap
        return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get(
        self,
        path: str,
        params: dict,
        response_key: str,
    ) -> list[dict] | None:
        """GET and extract *response_key*, following pagination to the end.

        The API caps every list response at a fixed page size and links the
        remainder via ``next_page_url`` (absolute, self-contained — request
        it verbatim, no params). This loop reassembles the full result the
        caller asked for, so everything above it — including the disk cache,
        which memoizes the *merged* list — never sees a truncated page.

        A mid-walk 404 ends the stream and keeps the rows accumulated so
        far; any other failure raises via _request's fail-loud contract.
        """
        resp = self._request("GET", path, params=params)
        if resp is None:
            return None
        body = resp.json()
        rows = body.get(response_key)
        next_page_url = body.get("next_page_url")
        while next_page_url and isinstance(rows, list):
            resp = self._request("GET", next_page_url)
            if resp is None:
                break
            body = resp.json()
            rows.extend(body.get(response_key) or [])
            next_page_url = body.get("next_page_url")
        return rows

    def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> requests.Response | None:
        """HTTP request with retry on 429 and 503.

        Fail-loud contract: raises FDClientError on network errors, HTTP
        errors, and exhausted retries. Returns None ONLY for 404 — "this
        data doesn't exist" is a data fact, not a failure. Silently
        returning empty on real failures poisons backtests (missing data
        reads as "no signal").

        503 is retried like 429: x402's payment facilitator answers 503 with
        Retry-After when it is briefly down, and nothing is charged for it.

        *path* may be an absolute URL (a ``next_page_url`` from a previous
        response), which is requested verbatim.
        """
        url = path if path.startswith("http") else self.BASE_URL + path
        for attempt, delay in enumerate((*self._RETRY_DELAYS, None)):
            try:
                resp = self._session.request(
                    method, url, timeout=self._timeout, **kwargs,
                )
            except requests.RequestException as exc:
                raise FDClientError(
                    f"{method} {path} failed: {exc}", path=path,
                ) from exc

            if resp.status_code in (429, 503) and delay is not None:
                logger.info(
                    "Got %d, retrying in %ds (attempt %d/%d)",
                    resp.status_code, delay, attempt + 1, len(self._RETRY_DELAYS),
                )
                time.sleep(delay)
                continue

            if resp.status_code == 404:
                return None

            if resp.status_code >= 400:
                message = f"{method} {path} returned {resp.status_code}: {resp.text[:200]}"
                if resp.status_code == 402 and self.pays_per_call():
                    message += f" (x402 payment from the wallet failed: {payment_error(resp)})"
                if resp.status_code == 403 and self.pays_per_call():
                    message += (
                        f" (x402 serves the last {X402_HISTORY_DAYS} days; move the start "
                        f"date later or set {API_KEY_ENV} for older data)"
                    )
                raise FDClientError(message, status_code=resp.status_code, path=path)

            return resp

        raise FDClientError(
            f"{method} {path} returned {resp.status_code} after {len(self._RETRY_DELAYS)} retries",
            status_code=resp.status_code, path=path,
        )
