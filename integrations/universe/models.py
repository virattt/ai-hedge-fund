"""Pydantic models for the universe selection pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FactorScore(BaseModel):
    """One factor's contribution to a ticker's composite score.

    ``raw`` is the oriented raw metric (higher is always better); ``zscore``
    is its cross-sectional z-score after winsorization. A missing raw value
    means the factor could not be computed for this ticker (scored neutral).
    """

    name: str
    raw: float | None = None
    zscore: float = 0.0
    weight: float = 0.0
    details: dict[str, Any] = Field(default_factory=dict)


class TickerScore(BaseModel):
    """Full scoring breakdown for one candidate ticker."""

    ticker: str
    composite: float
    rank: int | None = None
    sector: str | None = None
    factors: dict[str, FactorScore] = Field(default_factory=dict)


class UniverseSnapshot(BaseModel):
    """A versioned, point-in-time universe selection artifact."""

    as_of: str
    generated_at: str
    size: int
    tickers: list[str] = Field(default_factory=list, description="selected universe, ranked")
    scores: list[TickerScore] = Field(
        default_factory=list, description="scores for every shortlist candidate (selected + rejected)"
    )
    stage_counts: dict[str, int] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    caveats: list[str] = Field(default_factory=list)

    def selected_scores(self) -> list[TickerScore]:
        chosen = set(self.tickers)
        return [s for s in self.scores if s.ticker in chosen]
