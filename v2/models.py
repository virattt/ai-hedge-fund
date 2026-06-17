"""v2 Pydantic models — single source of truth for all data structures in the pipeline."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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
    value: float = Field(description="conviction from -1.0 (bearish) to +1.0 (bullish)")
    reasoning: str | None = None  # human-readable rationale — central for LLM agents
    components: dict[str, float] = Field(default_factory=dict)  # quant decomposition
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuantSignals(BaseModel):
    """All signals for a single ticker on a single date."""

    ticker: str
    date: str
    signals: dict[str, Signal] = Field(default_factory=dict)
    composite_score: float | None = None


# ---------------------------------------------------------------------------
# Portfolio Construction Models
# ---------------------------------------------------------------------------

class PortfolioTarget(BaseModel):
    """Output of the portfolio optimizer — target weights."""

    weights: dict[str, float] = Field(
        default_factory=dict, description="ticker -> target weight (-1 to +1)"
    )
    expected_return: float | None = None
    expected_risk: float | None = None


# ---------------------------------------------------------------------------
# Execution Models
# ---------------------------------------------------------------------------

class TradeOrder(BaseModel):
    """A single trade to execute."""

    ticker: str
    action: Literal["buy", "sell", "short", "cover"]
    shares: int = 0
    price: float = 0.0
    estimated_cost: float = 0.0
    reason: str = ""


class ExecutionResult(BaseModel):
    """Output of the execution layer."""

    orders: list[TradeOrder] = Field(default_factory=list)
    total_cost: float = 0.0
