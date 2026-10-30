"""v2 Pydantic models — single source of truth for all data structures in the pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_serializer


# ---------------------------------------------------------------------------
# Quantitative Signal Models
# ---------------------------------------------------------------------------

class Signal(BaseModel):
    """A view from an alpha model — conviction on a ticker at a point in time.

    This is the output of any AlphaModel (quant or LLM agent). The
    generator is the AlphaModel; the thing it generates is a Signal.
    """

    model_name: str = Field(description="which alpha model produced it, e.g. 'pead', 'buffett'")
    ticker: str
    date: str = Field(description="as-of date the view was formed (YYYY-MM-DD)")
    value: float = Field(
        ge=-1.0,
        le=1.0,
        allow_inf_nan=False,
        description="conviction from -1.0 (bearish) to +1.0 (bullish)",
    )
    reasoning: str | None = None  # human-readable rationale — central for LLM agents
    components: dict[str, float] = Field(default_factory=dict)  # quant decomposition
    metadata: dict[str, Any] = Field(default_factory=dict)
    horizon_days: int | None = Field(
        default=None, gt=0,
        description="trading days the view is expected to play out over; the scorecard grades it there",
    )

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        """A view with no horizon serializes exactly as every view did before
        the field existed: each one sits inside a hash-chained ledger record."""
        data = handler(self)
        if self.horizon_days is None:
            data.pop("horizon_days", None)
        return data


class QuantSignals(BaseModel):
    """All signals for a single ticker on a single date."""

    ticker: str
    date: str
    signals: dict[str, Signal] = Field(default_factory=dict)
    composite_score: float | None = None
