"""v2 Pydantic models — single source of truth for all data structures in the pipeline."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Quantitative Signal Models
# ---------------------------------------------------------------------------

class SignalResult(BaseModel):
    """Output of a single quantitative signal."""

    signal_name: str = Field(description="e.g. 'momentum', 'earnings_surprise'")
    value: float = Field(description="Signal strength from -1.0 (bearish) to +1.0 (bullish)")
    z_score: float | None = None
    percentile: float | None = None  # 0-100
    components: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuantSignals(BaseModel):
    """All signals for a single ticker on a single date."""

    ticker: str
    date: str
    signals: dict[str, SignalResult] = Field(default_factory=dict)
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
