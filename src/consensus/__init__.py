"""Consensus layer — aggregate analyst signals into a single decision.

Phase 1 exposes pure aggregation math with no LLM calls. See
``src/consensus/aggregation.py`` for the entry point ``aggregate_signals``.
"""

from src.consensus.aggregation import (
    Strategy,
    aggregate_signals,
    compute_agreement,
)
from src.consensus.models import AgentContribution, ConsensusSignal

__all__ = [
    "AgentContribution",
    "ConsensusSignal",
    "Strategy",
    "aggregate_signals",
    "compute_agreement",
]
