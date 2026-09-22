"""Mean-reversion alpha model — fade a z-score stretch.

Forms a view from how far the latest close sits from its trailing
window mean, in units of that window's standard deviation. A high
positive z-score is overextended (bearish); a deep negative z-score
is oversold (bullish).

Configurable via constructor kwargs (``window``, ``z_scale``) so a
strategy YAML can staff a sleeve with its own horizon and mapping.
"""

from __future__ import annotations

import numpy as np

from hedge_fund.data.protocol import DataClient
from hedge_fund.models import Signal
from hedge_fund.signals.base import QuantModel

_DEFAULT_WINDOW = 20
_DEFAULT_Z_SCALE = 2.0


class MeanReversionModel(QuantModel):
    """Fade stretches away from a trailing price mean.

    ``predict(ticker, date)`` returns a Signal in [-1, +1] from
    ``-tanh(z / z_scale)``, or 0.0 when history is too short or the
    window has no volatility (zero standard deviation).
    """

    def __init__(
        self,
        *,
        window: int = _DEFAULT_WINDOW,
        z_scale: float = _DEFAULT_Z_SCALE,
    ) -> None:
        if window < 2:
            raise ValueError(f"window must be >= 2, got {window}")
        if z_scale <= 0.0:
            raise ValueError(f"z_scale must be > 0, got {z_scale}")
        self._window = int(window)
        self._z_scale = float(z_scale)

    @property
    def name(self) -> str:
        return "mean_reversion"

    def predict(self, ticker: str, date: str, data_client: DataClient) -> Signal:
        closes = self._closes_as_of(
            data_client, ticker, date, min_bars=self._window,
        )
        if len(closes) < self._window:
            return self._abstain(
                ticker,
                date,
                reason="short_history",
                thesis=(
                    f"short history: {len(closes)} bars, "
                    f"need {self._window} for the z-score window"
                ),
                metadata={"bars": len(closes), "needed": self._window},
            )

        window = np.asarray(closes[-self._window:], dtype=float)
        mean = float(np.mean(window))
        std = float(np.std(window, ddof=0))
        if std == 0.0 or not np.isfinite(std):
            return self._abstain(
                ticker,
                date,
                reason="zero_vol",
                thesis=(
                    f"flat {self._window}-bar window "
                    f"(mean {mean:.4g}, σ=0); no z-score"
                ),
                metadata={"mean": mean, "std": 0.0},
            )

        price = float(window[-1])
        z = (price - mean) / std
        value = self._normalize_to_signal(
            self._sigmoid(-z, scale=1.0 / self._z_scale)
        )
        return Signal(
            model_name=self.name,
            ticker=ticker,
            date=date,
            value=value,
            reasoning=(
                f"{self._window}-bar z-score {z:+.2f}: "
                f"price {price:.4g} vs mean {mean:.4g} (σ={std:.4g}); "
                "fade the stretch"
            ),
            components={"z_score": z, "mean": mean, "std": std},
            metadata={
                "window": self._window,
                "z_scale": self._z_scale,
                "z_score": z,
                "mean": mean,
                "std": std,
                "price": price,
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
