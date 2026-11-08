"""CrowdWisdom Trading ProCrowdSentimentScore model (bought per call with x402).

What it is: the ProCrowdSentimentScore, -100 (short) to +100 (long), from what pro traders say on YouTube, X,
StockTwits, Reddit, broker platforms, podcasts and newsletters, with ProTraders (how many traders stand behind
it). The signal value is the score / 100. The API is pay-per-call with x402 (USDC on Base,
$0.10 per consensus call) using the same wallet this project already uses for Financial Datasets
(X402_WALLET_PRIVATE_KEY). Plan customers can set CWT_API_KEY instead; the model then reads the
Bearer route /v1/sentiment and derives the same score. Free sample and price list:
https://api.crowdwisdomtrading.com/x402/catalog

Point-in-time: predict(ticker, date) only asks for sessions dated on or before `date`, and answers for
finished days are cached on disk per (ticker, date), so a backtest pays once per day per ticker.

No new dependency: requests + the project's own payment_session.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import date as date_type
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from hedge_fund.data.protocol import DataClient
from hedge_fund.models import Signal
from hedge_fund.paths import CACHE_DIR
from hedge_fund.signals.base import QuantModel

CWT_BASE_URL = os.getenv("CWT_BASE_URL", "https://api.crowdwisdomtrading.com")
CROWD_CACHE_DIR = CACHE_DIR / "crowdwisdom"
LIVE_TTL_S = 600


def _day(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date_type):
        return value.isoformat()
    return str(value)[:10]


def _is_past_day(day: str) -> bool:
    return day < datetime.now(timezone.utc).date().isoformat()


class CrowdWisdomModel(QuantModel):
    """ProCrowdSentimentScore / 100 (-1 short .. +1 long) as of the backtest date; abstains when stale."""

    investment_approach = "long_short"
    horizon_days = 5

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        cycle: str | None = None,
        max_staleness_days: int = 10,
        base_url: str | None = None,
    ) -> None:
        self._session = session
        self._cycle = cycle
        self._max_staleness_days = max_staleness_days
        self._base_url = (base_url or CWT_BASE_URL).rstrip("/")
        self._api_key = (os.getenv("CWT_API_KEY") or "").strip()

    @property
    def name(self) -> str:
        return "crowdwisdom"

    # ------------------------------------------------------------------ http

    def _http(self) -> requests.Session:
        if self._session is None:
            wallet = (os.getenv("X402_WALLET_PRIVATE_KEY") or "").strip()
            if wallet and not self._api_key:
                from hedge_fund.data.wallet import payment_session

                self._session = payment_session(wallet)
            else:
                self._session = requests.Session()
        return self._session

    def _cache_path(self, ticker: str, day: str) -> Path:
        mode = "key" if self._api_key else "x402"
        key = hashlib.sha256(f"consensus|{mode}|{ticker}|{day}|{self._cycle or ''}".encode()).hexdigest()[:24]
        return CROWD_CACHE_DIR / f"{key}.json"

    def _read_cache(self, path: Path, day: str) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if _is_past_day(day) or time.time() - float(entry.get("fetched_at", 0)) < LIVE_TTL_S:
            return entry.get("body")
        return None

    def _write_cache(self, path: Path, body: dict[str, Any]) -> None:
        try:
            CROWD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"fetched_at": time.time(), "body": body}), encoding="utf-8")
        except OSError:
            pass

    def _fetch_x402(self, ticker: str, day: str) -> dict[str, Any]:
        params = {"as_of": day}
        if self._cycle:
            params["cycle"] = self._cycle
        response = self._http().get(
            f"{self._base_url}/x402/consensus/{ticker}",
            params=params,
            headers={"Accept": "application/json"},
            timeout=60,
            allow_redirects=False,
        )
        response.raise_for_status()
        return response.json()

    def _fetch_key_mode(self, ticker: str, day: str) -> dict[str, Any]:
        """Plan customers: the Bearer route /v1/sentiment, score of the latest session on or before `day`."""
        response = self._http().get(
            f"{self._base_url}/v1/sentiment/{ticker}",
            headers={"Accept": "application/json", "Authorization": f"Bearer {self._api_key}"},
            timeout=60,
            allow_redirects=False,
        )
        response.raise_for_status()
        body = response.json()
        path = [p for p in body.get("path") or [] if str(p.get("date", ""))[:10] <= day]
        if self._cycle:
            path = [p for p in path if p.get("cycle") == self._cycle]
        latest = path[-1] if path else None
        score = float(latest["score"]) if latest and latest.get("score") is not None else None
        return {
            "data": {
                "ticker": ticker,
                "value": max(-1.0, min(1.0, score / 100.0)) if score is not None else None,
                "ProCrowdSentimentScore": score,
                "direction": latest.get("direction") if latest else None,
                "session": {"date": latest["date"], "cycle": latest.get("cycle")} if latest else None,
                "mentions": {},
                "sources": {},
            },
            "as_of": day,
        }

    def _fetch(self, ticker: str, day: str) -> dict[str, Any]:
        path = self._cache_path(ticker, day)
        cached = self._read_cache(path, day)
        if cached is not None:
            return cached
        body = self._fetch_key_mode(ticker, day) if self._api_key else self._fetch_x402(ticker, day)
        if (body.get("data") or {}).get("value") is not None:
            self._write_cache(path, body)
        return body

    # --------------------------------------------------------------- predict

    def predict(self, ticker: str, date: str, data_client: DataClient) -> Signal:  # noqa: A002
        day = _day(date)
        try:
            body = self._fetch(ticker.upper(), day)
            data = body.get("data") or {}
            session = data.get("session") or {}
            value = data.get("value")
            if value is None or not session.get("date"):
                return self._abstain(ticker, day, "no crowd session on or before this date")
            age = (datetime.strptime(day, "%Y-%m-%d").date() - datetime.strptime(str(session["date"]), "%Y-%m-%d").date()).days
        except Exception as exc:  # network, payment, HTTP or malformed body -> no view, never a crash
            return self._abstain(ticker, day, f"crowd data unavailable: {type(exc).__name__}")
        if age > self._max_staleness_days:
            return self._abstain(ticker, day, f"latest crowd session {session['date']} is {age} days old")
        sources = data.get("sources") or {}
        mentions = data.get("mentions") or {}
        traders = data.get("ProTraders")
        pro_traders = traders.get("total") if isinstance(traders, dict) else traders
        return Signal(
            model_name=self.name,
            ticker=ticker,
            date=day,
            value=max(-1.0, min(1.0, float(value))),
            reasoning=(f"ProCrowdSentimentScore {float(data.get('ProCrowdSentimentScore') or 0):+.0f} " f"({data.get('direction') or 'n/a'}) on {session['date']} ({session.get('cycle')}) " f"from {pro_traders if pro_traders is not None else '?'} ProTraders"),
            components={k: float(v) / 100.0 for k, v in sources.items() if v is not None},
            metadata={
                "as_of": session["date"],
                "cycle": session.get("cycle"),
                "confidence": data.get("confidence"),
                "ProCrowdSentimentScore": data.get("ProCrowdSentimentScore"),
                "ProTraders": pro_traders,
                "mentions": mentions,
            },
            horizon_days=self.horizon_days,
        )

    def _abstain(self, ticker: str, day: str, reason: str) -> Signal:
        return Signal(
            model_name=self.name,
            ticker=ticker,
            date=day,
            value=0.0,
            reasoning=reason,
            metadata={"abstained": True},
            horizon_days=self.horizon_days,
        )
