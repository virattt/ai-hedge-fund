"""Data models for consensus aggregation of multi-agent trading signals."""

from pydantic import BaseModel, Field
from typing import Optional


class AgentContribution(BaseModel):
    """A single agent's contribution to the consensus."""
    agent_name: str = Field(description="Agent identifier, e.g. 'warren_buffett_agent'")
    signal: str = Field(description="Signal value: 'bullish', 'bearish', or 'neutral'")
    confidence: float = Field(description="Confidence score 0-100")
    reasoning: str = Field(default="", description="Agent's reasoning for this signal")


class ConsensusSignal(BaseModel):
    """Aggregated consensus for a single ticker."""
    ticker: str = Field(description="Stock ticker symbol")
    signal: str = Field(
        description="Consensus signal: 'bullish', 'bearish', or 'neutral'"
    )
    score: float = Field(
        description="Composite score in [-1, +1]. Positive=bullish, negative=bearish, near zero=neutral"
    )
    confidence: float = Field(
        description="Aggregated confidence 0-100. Lower when agents disagree."
    )
    agreement: float = Field(
        description="Agreement score 0-1. How much the agents agree with each other."
    )
    contributions: list[AgentContribution] = Field(
        default_factory=list,
        description="Individual agent contributions that formed this consensus.",
    )
    outliers: list[str] = Field(
        default_factory=list,
        description="Agent names whose signals deviate significantly from consensus.",
    )
    strategy: str = Field(
        default="weighted",
        description="Aggregation strategy used: 'weighted', 'majority', or 'mean'.",
    )


class ConsensusResult(BaseModel):
    """Full consensus output for all tickers."""
    signals: dict[str, ConsensusSignal] = Field(
        description="Dictionary of ticker to consensus signal"
    )
    summary: str = Field(
        default="",
        description="Human-readable summary of the consensus across all tickers",
    )
