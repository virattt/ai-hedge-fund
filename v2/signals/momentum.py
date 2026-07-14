"""Momentum alpha model — time-series (12-1) price momentum.

Go long stocks that have risen over roughly the past year and short those
that have fallen, while **skipping the most recent month** to sidestep the
well-documented short-term reversal effect. This "12-1" window (twelve months
of history, excluding the last one) is the canonical momentum specification
from Jegadeesh & Titman (1993) and Asness, Moskowitz & Pedersen (2013).

Momentum is the trend counterpart to a mean-reversion model and complements
the event-driven PEAD signal: PEAD reacts to a discrete earnings surprise,
momentum rides the persistent drift in the price itself.

Pure Python math over prices — same AlphaModel interface as every other
signal. It only forms a *view* (conviction in [-1, +1]); the backtest harness
and portfolio construction decide timing and sizing.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from v2.data.protocol import DataClient
from v2.models import Signal
from v2.signals.base import QuantModel

_TRADING_DAYS_PER_MONTH = 21


class MomentumModel(QuantModel):
    """Time-series (12-1) momentum: trailing return excluding the last month.

    ``predict(ticker, date)`` measures the return from ``lookback_months`` ago
    up to ``skip_months`` ago and maps it to a conviction in [-1, +1] via a
    scaled ``tanh``. Returns 0.0 (no view) when there is not enough
    point-in-time price history to form the window.
    """

    def __init__(
        self,
        *,
        lookback_months: int = 12,
        skip_months: int = 1,
        scale: float = 3.0,
    ) -> None:
        if lookback_months <= 0:
            raise ValueError(f"lookback_months must be positive, got {lookback_months}")
        if skip_months < 0:
            raise ValueError(f"skip_months must be >= 0, got {skip_months}")
        if skip_months >= lookback_months:
            raise ValueError(f"skip_months ({skip_months}) must be < lookback_months ({lookback_months})")
        self._lookback_months = lookback_months
        self._skip_months = skip_months
        self._scale = scale

    @property
    def name(self) -> str:
        return "momentum"

    def predict(self, ticker: str, date: str, data_client: DataClient) -> Signal:
        # Point-in-time: fetch only prices up to `date` (end_date=date, no
        # lookahead). Pad the start generously so calendar-vs-trading-day gaps
        # (weekends, holidays) still leave enough bars for the lookback window.
        start = (_parse_date(date) - timedelta(days=self._lookback_months * 31 + 45)).isoformat()
        prices = data_client.get_prices(ticker, start, date)

        # Sort defensively — providers do not all return bars in order — and
        # drop non-positive closes (bad ticks) before indexing.
        closes = [p.close for p in sorted(prices, key=lambda p: p.time) if p.close > 0]

        skip = self._skip_months * _TRADING_DAYS_PER_MONTH
        lookback = self._lookback_months * _TRADING_DAYS_PER_MONTH
        if len(closes) <= lookback:
            return self._neutral(ticker, date)

        # 12-1 window: price `skip` bars ago relative to price `lookback` bars ago.
        start_price = closes[-lookback - 1]
        end_price = closes[-1] if skip == 0 else closes[-skip - 1]
        if start_price <= 0:
            return self._neutral(ticker, date)

        trailing_return = end_price / start_price - 1.0
        value = self._sigmoid(trailing_return, scale=self._scale)

        return Signal(
            model_name=self.name,
            ticker=ticker,
            date=date,
            value=value,
            reasoning=f"{self._lookback_months}-{self._skip_months} momentum = {trailing_return:+.1%} -> conviction {value:+.2f}",
            components={"trailing_return": trailing_return},
            metadata={
                "lookback_months": self._lookback_months,
                "skip_months": self._skip_months,
                "n_bars": len(closes),
            },
        )

    def _neutral(self, ticker: str, date: str) -> Signal:
        return Signal(model_name=self.name, ticker=ticker, date=date, value=0.0)


def _parse_date(s: str) -> date:
    return datetime.strptime(s[:10], "%Y-%m-%d").date()
