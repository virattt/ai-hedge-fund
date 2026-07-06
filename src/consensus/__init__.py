"""Consensus aggregation module for multi-agent trading signals.

Phase 2: Wired into the LangGraph workflow between risk_manager and portfolio_manager.
Builds on Issue #586 and complements tony-ku's Phase 1 models (#595).
"""

from src.consensus.models import (
    ConsensusSignal,
    AgentContribution,
    ConsensusResult,
)
from src.consensus.aggregation import (
    aggregate_signals,
    compute_agreement,
    detect_outliers,
)

__all__ = [
    "ConsensusSignal",
    "AgentContribution",
    "ConsensusResult",
    "aggregate_signals",
    "compute_agreement",
    "detect_outliers",
]
