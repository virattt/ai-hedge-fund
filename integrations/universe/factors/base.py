"""Factor interface and the per-ticker context factors compute from.

A factor turns one candidate's data into a single oriented raw value where
HIGHER IS ALWAYS BETTER (the scoring engine z-scores raw values across the
pool and combines them by weight). Returning ``None`` means "cannot compute
for this ticker" and scores neutral.

Adding a factor: subclass ``Factor``, implement ``compute``, register it in
``integrations/universe/factors/__init__.py`` and give it a weight in
``UniverseConfig.factor_weights``. Removing one: weight it 0 or drop the
registry entry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from integrations.universe.config import UniverseConfig


@dataclass
class FactorContext:
    """Everything known about one candidate at scoring time (point-in-time)."""

    ticker: str
    as_of: str
    config: UniverseConfig
    prices: pd.DataFrame  # daily bars (open/high/low/close/volume), <= as_of
    shortable: bool = False
    easy_to_borrow: bool = False
    sector: str | None = None
    fundamentals: dict[str, Any] | None = None
    earnings_events: list[dict[str, Any]] = field(default_factory=list)
    news_count_30d: int | None = None
    learnability: Any | None = None  # LearnabilityResult, set in Stage 2

    @property
    def returns(self) -> pd.Series:
        return self.prices["close"].pct_change().dropna()

    @property
    def dollar_volume(self) -> pd.Series:
        return self.prices["close"] * self.prices["volume"]


class Factor(ABC):
    """One scoring dimension. ``compute`` returns an oriented raw value."""

    #: unique registry/weight key
    name: str = ""

    @abstractmethod
    def compute(self, ctx: FactorContext) -> float | None:
        """Return the raw value (higher = better) or None if not computable."""
        ...
