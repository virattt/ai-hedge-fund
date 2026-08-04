"""DPX macro stability alpha model — a market-wide regime overlay.

Forms a view from DPX's Stability Oracle (https://untitledfinancial.com), a
live macro/climate/FX/geopolitical signal pipeline that gates institutional
stablecoin settlement. The oracle produces one global stability score, not a
per-ticker one — so this is a *regime overlay*: the same conviction is
returned for every ticker on a given day, meant to be combined with
ticker-specific alpha models (PEAD, Buffett, etc.) rather than used alone.

No API key required — the endpoint used here is free and unauthenticated.

Live-only caveat: the Stability Oracle exposes current conditions, not a
queryable history. `predict()` can only form a real view for the current
day; for any other `date` it abstains (conviction 0.0) rather than silently
reusing today's score as a stand-in for a past date, which would violate
the point-in-time contract this interface requires.
"""

from __future__ import annotations

from datetime import date as date_cls, datetime

import requests

from hedge_fund.data.protocol import DataClient
from hedge_fund.models import Signal
from hedge_fund.signals.base import QuantModel

_RELIABILITY_URL = "https://stability.untitledfinancial.com/reliability"
_TIMEOUT_SECONDS = 10.0


class DPXMacroStabilityModel(QuantModel):
    """Market-wide macro regime overlay from DPX's live Stability Oracle.

    `predict(ticker, date)` ignores `ticker` (the signal is market-wide) and
    returns the same conviction for every symbol on a given call. Conviction
    is derived from the oracle's 0-100 stability score: STABLE conditions
    (score >= 90) map toward a mildly bullish risk-on overlay, UNSTABLE
    conditions (score < 75) map toward bearish, CAUTION sits in between.
    """

    def __init__(self, *, timeout_seconds: float = _TIMEOUT_SECONDS) -> None:
        self._timeout_seconds = timeout_seconds
        self._cache: dict[str, dict] = {}  # keyed by date string, one lookup per day

    @property
    def name(self) -> str:
        return "dpx_macro"

    def predict(self, ticker: str, date: str, data_client: DataClient) -> Signal:
        if not _is_today(date):
            return Signal(
                model_name=self.name,
                ticker=ticker,
                date=date,
                value=0.0,
                reasoning=(
                    "DPX Stability Oracle is live-only (no historical query) — "
                    "abstaining rather than reusing today's score for a past date."
                ),
            )

        try:
            reliability = self._fetch_reliability(date)
        except (requests.RequestException, KeyError, ValueError) as exc:
            # Infrastructure failure — abstain with the error visible in
            # reasoning rather than silently returning a false neutral.
            return Signal(
                model_name=self.name,
                ticker=ticker,
                date=date,
                value=0.0,
                reasoning=f"DPX Stability Oracle unavailable: {exc}",
            )

        score = self._safe_float(reliability["stability"]["currentScore"])
        status = reliability["stability"]["latestStatus"]
        caution_threshold = self._safe_float(reliability["stability"]["threshold"]["caution"])
        stable_threshold = self._safe_float(reliability["stability"]["threshold"]["stable"])

        # Center the sigmoid on the caution/stable midpoint so STABLE trends
        # toward +1, UNSTABLE toward -1, with CAUTION near zero.
        midpoint = (caution_threshold + stable_threshold) / 2
        conviction = self._sigmoid((score - midpoint) / 10, scale=1.0)

        peg_bps = self._safe_float(reliability.get("peg", {}).get("deviationBps"))

        return Signal(
            model_name=self.name,
            ticker=ticker,
            date=date,
            value=self._normalize_to_signal(conviction),
            reasoning=(
                f"DPX Stability Oracle: {status} (score {score:.0f}/100), "
                f"peg deviation {peg_bps:.0f}bps"
            ),
            components={"stability_score": score, "peg_deviation_bps": peg_bps},
            metadata={"source": _RELIABILITY_URL, "status": status},
        )

    def _fetch_reliability(self, date: str) -> dict:
        if date in self._cache:
            return self._cache[date]
        resp = requests.get(_RELIABILITY_URL, timeout=self._timeout_seconds)
        resp.raise_for_status()
        data = resp.json()
        self._cache[date] = data
        return data


def _is_today(date_str: str) -> bool:
    try:
        requested = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return False
    return requested == date_cls.today()
