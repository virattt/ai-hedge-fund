from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Sequence, TypedDict, Literal
from enum import Enum

import pandas as pd


class Action(str, Enum):
    BUY = "buy"
    SELL = "sell"
    SHORT = "short"
    COVER = "cover"
    HOLD = "hold"

# Backward-compatible alias
ActionLiteral = Literal["buy", "sell", "short", "cover", "hold"]


class PositionState(TypedDict):
    """Represents per-ticker position state in the portfolio."""

    long: int
    short: int
    long_cost_basis: float
    short_cost_basis: float
    short_margin_used: float


class TickerRealizedGains(TypedDict):
    """Realized PnL per side for a single ticker."""

    long: float
    short: float


class PortfolioSnapshot(TypedDict):
    """Snapshot of portfolio state.

    The structure mirrors the existing dict used by the current Backtester
    to ensure drop-in compatibility during incremental refactors.
    """

    cash: float
    margin_used: float
    margin_requirement: float
    positions: Dict[str, PositionState]
    realized_gains: Dict[str, TickerRealizedGains]


# DataFrame alias for clarity in interfaces
PriceDataFrame = pd.DataFrame


class AgentDecision(TypedDict):
    action: ActionLiteral
    quantity: float


AgentDecisions = Dict[str, AgentDecision]


# Analyst signal payloads can vary by agent; keep as loose dicts
AnalystSignal = Dict[str, Any]
AgentSignals = Dict[str, Dict[str, AnalystSignal]]


class AgentOutput(TypedDict):
    decisions: AgentDecisions
    analyst_signals: AgentSignals


# Use functional style to allow keys with spaces to mirror current code
PortfolioValuePoint = TypedDict(
    "PortfolioValuePoint",
    {
        "Date": datetime,
        "Portfolio Value": float,
        "Long Exposure": float,
        "Short Exposure": float,
        "Gross Exposure": float,
        "Net Exposure": float,
        "Long/Short Ratio": float,
    },
    total=False,
)


class PerformanceMetrics(TypedDict, total=False):
    """Performance metrics computed over the equity curve.

    Keys are aligned with the current implementation in src/backtester.py.
    Values are optional to support progressive calculation over time.
    """

    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    max_drawdown: Optional[float]
    max_drawdown_date: Optional[str]
    long_short_ratio: Optional[float]
    gross_exposure: Optional[float]
    net_exposure: Optional[float]


