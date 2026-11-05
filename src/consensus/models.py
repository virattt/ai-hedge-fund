"""Pydantic models for the consensus layer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from typing_extensions import Literal


class AgentContribution(BaseModel):
    """How a single agent influenced the consensus for one ticker."""

    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(description="Reported confidence 0-100")
    weight: float = Field(description="Voting weight assigned to this agent")
    contribution: float = Field(
        description="Signed contribution to the composite score, same scale as score"
    )


class ConsensusSignal(BaseModel):
    """Aggregated analyst signal for a single ticker on a single date."""

    signal: Literal["bullish", "bearish", "neutral"]
    score: float = Field(description="Weighted composite in [-1.0, +1.0]")
    confidence: float = Field(
        description="Aggregate confidence 0-100; degraded by disagreement"
    )
    agreement: float = Field(
        description="Share of total weight in the dominant vote camp, in [0.0, 1.0]"
    )
    vote_breakdown: dict[str, int] = Field(
        default_factory=lambda: {"bullish": 0, "bearish": 0, "neutral": 0},
        description="Raw vote counts keyed by 'bullish' / 'bearish' / 'neutral'",
    )
    contributions: dict[str, AgentContribution] = Field(default_factory=dict)
    arbitration: dict[str, Any] | None = Field(
        default=None,
        description="Populated by the optional LLM arbiter in Phase 4",
    )
    reasoning: str = ""
