"""PEAD alpha model — Post-Earnings Announcement Drift.

Forms a view based on earnings surprises: bullish after a BEAT, bearish
after a MISS, on the theory that the market underreacts and the stock
keeps drifting in the surprise direction for days/weeks.

This is the quant counterpart to an LLM investor agent — same AlphaModel
interface, pure Python math. It only forms a *view* (conviction); the
backtest harness / portfolio construction decides timing and sizing.
"""

from __future__ import annotations

from datetime import datetime

from hedge_fund.data.protocol import DataClient
from hedge_fund.data.models import EarningsRecord
from hedge_fund.models import Signal
from hedge_fund.signals.base import QuantModel

_RETROSPECTIVE_CUTOFF_DAYS = 45   # drop filings whose data is stale vs report period
_SOURCE_PRIORITY = {"8-K": 0, "10-Q": 1, "10-K": 2, "20-F": 3}  # 8-K = earliest announcement


class PEADModel(QuantModel):
    """Long after an EPS BEAT, short after a MISS.

    `predict(ticker, date)` returns ±1.0 conviction if a qualifying earnings
    surprise was filed within `signal_window_days` of `date`, else 0.0 (no view).
    Conviction magnitude is fixed ±1 for v0 — scaling by surprise size is a
    future enhancement.

    By default only 8-K rows qualify. A 10-Q/10-K filing date is the
    statutory filing, not the announcement, so treating it as a fresh
    surprise fires days to weeks after the market already priced the
    beat or miss. Set ``announcement_only=False`` to restore the old
    10-Q/K fallback.
    """

    investment_approach = "long_short"

    def __init__(
        self,
        *,
        earnings_limit: int = 8,
        signal_window_days: int = 4,
        announcement_only: bool = True,
    ) -> None:
        self._earnings_limit = earnings_limit
        self._signal_window_days = signal_window_days
        self._announcement_only = announcement_only
        # Cache earnings history per ticker — predict is called once per
        # trading day during a backtest, so we fetch each ticker only once.
        self._cache: dict[str, list[EarningsRecord]] = {}

    @property
    def name(self) -> str:
        return "pead"

    def predict(self, ticker: str, date: str, data_client: DataClient) -> Signal:
        as_of = _parse_date(date)
        events = self._qualifying_events(ticker, data_client)

        # Point-in-time: only consider filings on or before `date` (no lookahead)
        past = [e for e in events if _parse_date(e["filing_date"]) <= as_of]
        if not past:
            return self._neutral(ticker, date)

        # Most recent qualifying event as of `date`
        event = max(past, key=lambda e: e["filing_date"])
        filed = _parse_date(event["filing_date"])

        # Only fire if the event is fresh (we just learned about it)
        if (as_of - filed).days > self._signal_window_days:
            return self._neutral(ticker, date)

        surprise = event["surprise"]
        value = 1.0 if surprise == "BEAT" else -1.0
        return Signal(
            model_name=self.name,
            ticker=ticker,
            date=date,
            value=value,
            reasoning=(
                f"{surprise} on {event['report_period']} earnings "
                f"(filed {event['filing_date']}, {event['source_type']})"
            ),
            metadata={
                "eps_surprise": surprise,
                "source_type": event["source_type"],
                "report_period": event["report_period"],
                "filing_date": event["filing_date"],
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _neutral(self, ticker: str, date: str) -> Signal:
        return Signal(model_name=self.name, ticker=ticker, date=date, value=0.0)

    def _qualifying_events(self, ticker: str, data_client: DataClient) -> list[dict]:
        """Return BEAT/MISS events for a ticker, deduped + retrospective-filtered.

        One event per report_period. Default is 8-K only: a 10-Q/10-K
        filing date is not the announcement date, so using it as the
        event date fires after the market has already priced the
        surprise. With ``announcement_only=False``, 10-Q/K rows are
        kept as a fallback and 8-K still wins when both exist.

        Duplicate 8-Ks for the same period keep the earliest filing
        date. Retrospective rows whose filing date is far after the
        report period are dropped (the extractor sometimes parses
        prior-quarter comparison data from a current 8-K).
        """
        if ticker in self._cache:
            records = self._cache[ticker]
        else:
            records = data_client.get_earnings_history(ticker, limit=self._earnings_limit)
            self._cache[ticker] = records

        best: dict[str, tuple[int, str, EarningsRecord]] = {}
        for r in records:
            if not r.filing_date or not r.quarterly:
                continue
            surprise = r.quarterly.eps_surprise
            if surprise not in ("BEAT", "MISS"):
                continue
            if self._announcement_only and r.source_type != "8-K":
                continue

            # 45-day retrospective filter
            lag = (_parse_date(r.filing_date) - _parse_date(r.report_period)).days
            if lag >= _RETROSPECTIVE_CUTOFF_DAYS:
                continue

            # Highest-priority filing per period (8-K wins); earliest date
            # breaks ties so a later 8-K for the same quarter is ignored.
            priority = _SOURCE_PRIORITY.get(r.source_type, 99)
            key = (priority, r.filing_date)
            if r.report_period not in best or key < best[r.report_period][:2]:
                best[r.report_period] = (priority, r.filing_date, r)

        return [
            {
                "filing_date": r.filing_date,
                "report_period": r.report_period,
                "source_type": r.source_type,
                "surprise": r.quarterly.eps_surprise,
            }
            for _, _, r in best.values()
        ]


def _parse_date(s: str):
    return datetime.strptime(s[:10], "%Y-%m-%d").date()
