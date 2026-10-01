"""Interfaces for models that produce investment views, independent of sizing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Literal, TypeAlias

import numpy as np
import pandas as pd

from hedge_fund.data.protocol import DataClient
from hedge_fund.models import Signal

InvestmentApproach: TypeAlias = Literal["long_only", "long_short"]


class AlphaModel(ABC):
    """Abstract base for all alpha models. Forms a view, returns a Signal."""

    # Every concrete registered analyst declares its own approach. This is
    # permission metadata, independent of its signed opinion or LLM prompt.
    investment_approach: ClassVar[InvestmentApproach]

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

        Use only information available on or before *date*. Return conviction
        in [-1, +1]; zero is neutral. Set metadata["abstained"] to True when
        the model cannot form a view.
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
