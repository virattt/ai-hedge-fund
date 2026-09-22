"""Momentum alpha model — skip-period price trend.

Forms a view from the return between two past closes: the close
``lookback`` bars before the close ``skip`` bars ago. Positive drift
is bullish; negative drift is bearish. ``skip`` drops the most recent
bars so a short-term reversal does not wash out the slower trend.

Configurable via constructor kwargs (``lookback``, ``skip``) so a
strategy YAML can staff a sleeve with its own horizon.
"""

from __future__ import annotations

from hedge_fund.data.protocol import DataClient
from hedge_fund.models import Signal
from hedge_fund.signals.base import QuantModel

_DEFAULT_LOOKBACK = 252  # ~12 months of daily bars
_DEFAULT_SKIP = 21       # ~1 month; classic 12-1 skip-period momentum


class MomentumModel(QuantModel):
    """Long recent winners, short recent losers, after a skip window.

    ``predict(ticker, date)`` returns a Signal in [-1, +1] from the
    skip-period return, or 0.0 when history is too short to form a view.
    """

    def __init__(
        self,
        *,
        lookback: int = _DEFAULT_LOOKBACK,
        skip: int = _DEFAULT_SKIP,
    ) -> None:
        if lookback < 1:
            raise ValueError(f"lookback must be >= 1, got {lookback}")
        if skip < 0:
            raise ValueError(f"skip must be >= 0, got {skip}")
        self._lookback = int(lookback)
        self._skip = int(skip)

    @property
    def name(self) -> str:
        return "momentum"

    def predict(self, ticker: str, date: str, data_client: DataClient) -> Signal:
        needed = self._lookback + self._skip + 1
        closes = self._closes_as_of(
            data_client, ticker, date, min_bars=needed,
        )
        if len(closes) < needed:
            return self._abstain(
                ticker,
                date,
                reason="short_history",
                thesis=(
                    f"short history: {len(closes)} bars, "
                    f"need {needed} (lookback {self._lookback} + skip {self._skip})"
                ),
                metadata={"bars": len(closes), "needed": needed},
            )

        window = closes[-needed:]
        start_price = window[0]
        end_price = window[self._lookback]
        if start_price <= 0.0 or end_price <= 0.0:
            return self._abstain(
                ticker,
                date,
                reason="non_positive_price",
                thesis="non-positive close in the momentum window",
            )

        raw_return = end_price / start_price - 1.0
        value = self._normalize_to_signal(self._sigmoid(raw_return))
        return Signal(
            model_name=self.name,
            ticker=ticker,
            date=date,
            value=value,
            reasoning=(
                f"{self._lookback}-bar momentum (skip {self._skip}): "
                f"{raw_return:+.2%} from {start_price:.4g} to {end_price:.4g}"
            ),
            components={"raw_return": raw_return},
            metadata={
                "lookback": self._lookback,
                "skip": self._skip,
                "start_price": start_price,
                "end_price": end_price,
                "raw_return": raw_return,
                "abstained": False,
            },
        )

    def _abstain(
        self,
        ticker: str,
        date: str,
        *,
        reason: str,
        thesis: str,
        metadata: dict | None = None,
    ) -> Signal:
        extra = metadata or {}
        return Signal(
            model_name=self.name,
            ticker=ticker,
            date=date,
            value=0.0,
            reasoning=thesis,
            metadata={"abstained": True, "reason": reason, **extra},
        )
