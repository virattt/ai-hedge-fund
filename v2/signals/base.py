"""Base class for all v2 quantitative signals."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from v2.models import SignalResult


class BaseSignal(ABC):
    """Abstract base for Layer 1 quantitative signals.

    Each signal fetches data from FD, computes a score in [-1, +1],
    and returns a SignalResult. No LLM calls — pure Python math.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Signal identifier (e.g. 'value', 'momentum')."""
        ...

    @abstractmethod
    def compute(
        self,
        ticker: str,
        end_date: str,
        *,
        api_key: str | None = None,
    ) -> SignalResult:
        """Compute the signal for a single ticker as-of *end_date*."""
        ...

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
