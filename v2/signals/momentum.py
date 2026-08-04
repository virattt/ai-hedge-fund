"""Price-momentum alpha model.

Forms a point-in-time view from trailing close-to-close returns.  The model
deliberately skips the most recent few observations by default: medium-term
momentum is commonly measured away from the latest short-term reversal window.
It only forms a view; portfolio construction remains responsible for sizing.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from v2.data.protocol import DataClient
from v2.models import Signal
from v2.signals.base import QuantModel


class MomentumModel(QuantModel):
    """Blend trailing price returns into a bounded momentum conviction.

    ``horizons`` and ``skip_days`` are counts of available price observations,
    not calendar days.  For a 21-day horizon with a 5-day skip, for example,
    the return ends five observations before the as-of date.
    """

    def __init__(
        self,
        *,
        horizons: tuple[int, ...] | list[int] = (21, 63, 126),
        weights: tuple[float, ...] | list[float] | None = None,
        skip_days: int = 5,
        signal_scale: float = 4.0,
    ) -> None:
        self._horizons = tuple(horizons)
        if not self._horizons or any(h <= 0 for h in self._horizons):
            raise ValueError("horizons must contain positive observation counts")
        if len(set(self._horizons)) != len(self._horizons):
            raise ValueError("horizons must be unique")
        if skip_days < 0:
            raise ValueError("skip_days must be non-negative")
        if signal_scale <= 0:
            raise ValueError("signal_scale must be positive")

        chosen_weights = tuple(weights) if weights is not None else (1.0,) * len(self._horizons)
        if len(chosen_weights) != len(self._horizons):
            raise ValueError("weights must have the same length as horizons")
        if any(not math.isfinite(w) or w < 0 for w in chosen_weights):
            raise ValueError("weights must be finite and non-negative")
        if sum(chosen_weights) == 0:
            raise ValueError("at least one weight must be positive")

        self._weights = chosen_weights
        self._skip_days = skip_days
        self._signal_scale = signal_scale

    @property
    def name(self) -> str:
        return "momentum"

    def predict(self, ticker: str, date: str, data_client: DataClient) -> Signal:
        as_of = _parse_date(date)
        observations_needed = max(self._horizons) + self._skip_days + 1
        # Use a generous calendar window, then enforce the as-of boundary again
        # locally.  The second check protects the model from a permissive provider.
        start = as_of - timedelta(days=observations_needed * 2)
        bars = data_client.get_prices(
            ticker,
            start.isoformat(),
            as_of.isoformat(),
        )

        closes_by_date: dict[str, float] = {}
        for bar in bars:
            bar_date = bar.time[:10]
            close = self._safe_float(bar.close, default=float("nan"))
            if bar_date <= as_of.isoformat() and math.isfinite(close) and close > 0:
                closes_by_date[bar_date] = close

        closes = [closes_by_date[d] for d in sorted(closes_by_date)]
        if len(closes) < observations_needed:
            return self._neutral(ticker, date, len(closes), observations_needed)

        end_index = len(closes) - 1 - self._skip_days
        returns: dict[int, float] = {}
        for horizon in self._horizons:
            start_close = closes[end_index - horizon]
            end_close = closes[end_index]
            returns[horizon] = (end_close / start_close) - 1.0

        weight_total = sum(self._weights)
        blended_return = sum(returns[horizon] * weight for horizon, weight in zip(self._horizons, self._weights)) / weight_total
        value = self._sigmoid(blended_return, scale=self._signal_scale)

        components = {f"return_{horizon}d": returns[horizon] for horizon in self._horizons}
        components["blended_return"] = blended_return
        return Signal(
            model_name=self.name,
            ticker=ticker,
            date=date,
            value=value,
            reasoning=(f"Momentum across {list(self._horizons)} observation horizons " f"with a {self._skip_days}-observation skip"),
            components=components,
            metadata={
                "horizons": list(self._horizons),
                "weights": list(self._weights),
                "skip_days": self._skip_days,
                "signal_scale": self._signal_scale,
                "observations": len(closes),
            },
        )

    def _neutral(
        self,
        ticker: str,
        date: str,
        observations: int,
        required: int,
    ) -> Signal:
        return Signal(
            model_name=self.name,
            ticker=ticker,
            date=date,
            value=0.0,
            reasoning=f"Insufficient price history: {observations} observations, {required} required",
            metadata={"observations": observations, "required_observations": required},
        )


def _parse_date(value: str):
    return datetime.strptime(value[:10], "%Y-%m-%d").date()
