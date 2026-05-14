"""Named multi-agent workflows.

Each module in this package exposes a fixed, opinionated LangGraph workflow
that captures a specific business scenario. Unlike ``src.main.create_workflow``,
which assembles a graph dynamically based on user-selected analysts, workflows
here are curated playbooks — the analyst lineup is part of the product.

See ``docs/decisions/ADR-006-earnings-reaction-playbook-and-claude-sdk-comparison.md``
for the rationale.
"""

from src.workflows.earnings_reaction import (
    EARNINGS_REACTION_ANALYSTS,
    build_earnings_reaction_graph,
    earnings_reaction_initial_state,
    memory_checkpointer,
    sqlite_checkpointer,
)

__all__ = [
    "EARNINGS_REACTION_ANALYSTS",
    "build_earnings_reaction_graph",
    "earnings_reaction_initial_state",
    "memory_checkpointer",
    "sqlite_checkpointer",
]
