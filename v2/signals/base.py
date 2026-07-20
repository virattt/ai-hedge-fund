"""Alpha models — the components that form views on what to hold.

An *alpha model* (Rishi Narang's term, *Inside the Black Box*) is anything
that produces a forecast / view on an asset. It's the "edge" component of a
quant fund. In v2, both quant signals (PEAD, regime) and LLM investor agents
(Buffett, Druckenmiller) are alpha models — they all implement this interface
and produce a `Signal` (a conviction in [-1, +1] + reasoning).

    AlphaModel (ABC)
      ├─ QuantModel   — pure Python math (this file)
      └─ LLMAgent     — LLM reasons over features (added in Week 5)

The alpha model only forms a *view*. It does NOT decide position mechanics
(timing, sizing, holding period) — that's the job of portfolio construction
and execution. This separation (views vs positions) is deliberate.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from v2.data.protocol import DataClient
from v2.models import Signal


class AlphaModel(ABC):
    """Abstract base for all alpha models. Forms a view, returns a Signal."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Model identifier (e.g. 'pead', 'buffett')."""
        ...

    @abstractmethod
    def predict(
        self,
        ticker: str,
        date: str,
        data_client: DataClient,
    ) -> Signal:
        """Form a point-in-time view on *ticker* as of *date*.

        MUST be point-in-time: only use data with date <= *date* (no
        lookahead). Return a Signal with conviction in [-1, +1] — use
        0.0 to express "no view" (abstain).
        """
        ...


class QuantModel(AlphaModel):
    """Base for pure-math alpha models (no LLM).

    Houses shared numeric helpers. Subclass this for quant signals like
    PEAD or regime detection.
    """

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_float(value, default: float = 0.0) -> float:
        """Convert to float, returning *default* for NaN / None / errors."""
        if value is None:
            return default
        try:
            f = float(value)
            return default if (np.isnan(f) or np.isinf(f)) else f
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _percentile_rank(value: float, values: list[float]) -> float:
        """Return the percentile rank (0-100) of *value* within *values*."""
        if not values:
            return 50.0
        below = sum(1 for v in values if v < value)
        return (below / len(values)) * 100.0

    @staticmethod
    def _normalize_to_signal(raw: float, low: float = -1.0, high: float = 1.0) -> float:
        """Clamp *raw* into [low, high]."""
        return max(low, min(high, raw))

    @staticmethod
    def _sigmoid(x: float, scale: float = 5.0) -> float:
        """Map an unbounded value into (-1, +1) via scaled tanh."""
        return float(np.tanh(x * scale))

    @staticmethod
    def _compute_rsi(prices: pd.Series, period: int = 14) -> float:
        """Compute the latest RSI value for a price series."""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        latest = rsi.iloc[-1]
        if pd.isna(latest):
            return 50.0
        return float(latest)
