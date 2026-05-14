"""Earnings Reaction Playbook — fixed-sequence multi-agent workflow.

When a company reports earnings, six curated analyst lenses run in parallel,
then a risk manager consolidates their signals, then a portfolio manager
issues a trading decision:

    start_node
        ├──► fundamentals_analyst    (financial statement delta)
        ├──► sentiment_analyst       (post-earnings news/social sentiment)
        ├──► technical_analyst       (price-action confirmation)
        ├──► valuation_analyst       (re-rating model output)
        ├──► warren_buffett          (long-term holder POV)
        └──► michael_burry           (contrarian / short-side POV)
                  │
                  ▼
            risk_management_agent
                  │
                  ▼
           portfolio_manager
                  │
                  ▼
                 END

Checkpointing is optional:

* ``MemorySaver`` (default for tests and quick local runs) — state is lost on
  process exit.
* ``SqliteSaver`` (recommended for the live sales-demo server) — state
  persists across restart; a crashed run can be resumed.

See ``docs/decisions/ADR-006`` for the design rationale.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from src.agents.portfolio_manager import portfolio_management_agent
from src.agents.risk_manager import risk_management_agent
from src.graph.state import AgentState
from src.utils.analysts import ANALYST_CONFIG

if TYPE_CHECKING:
    from collections.abc import Iterator

    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph


# The six analyst lenses we curated for the post-earnings scenario.
# Order is informational only — all six run in parallel after start_node.
EARNINGS_REACTION_ANALYSTS: tuple[str, ...] = (
    "fundamentals_analyst",
    "sentiment_analyst",
    "technical_analyst",
    "valuation_analyst",
    "warren_buffett",
    "michael_burry",
)


def _start(state: AgentState) -> AgentState:
    """Entry node — pass-through. Kept as a named node so the SSE stream
    surfaces a clean ``start_node`` event before fan-out."""
    return state


def _resolve_analyst(key: str) -> tuple[str, Any]:
    """Look up the (node_name, agent_func) tuple for an analyst key.

    Mirrors ``src.utils.analysts.get_analyst_nodes`` but for a single key, so
    we fail fast with a precise error if the playbook references an analyst
    that has been removed upstream.
    """
    if key not in ANALYST_CONFIG:
        msg = (
            f"Earnings Reaction Playbook references unknown analyst {key!r}. "
            f"Available analysts: {sorted(ANALYST_CONFIG)}"
        )
        raise KeyError(msg)
    return f"{key}_agent", ANALYST_CONFIG[key]["agent_func"]


def build_earnings_reaction_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Build and compile the Earnings Reaction Playbook graph.

    Args:
        checkpointer: Optional ``BaseCheckpointSaver``. When supplied, the
            compiled graph persists state per-thread. When ``None``, the graph
            runs without checkpointing — state lives only for the duration of
            the ``invoke()`` call.

    Returns:
        Compiled ``StateGraph`` ready for ``invoke()`` / ``astream()``.
    """
    workflow = StateGraph(AgentState)
    workflow.add_node("start_node", _start)

    for key in EARNINGS_REACTION_ANALYSTS:
        node_name, node_func = _resolve_analyst(key)
        workflow.add_node(node_name, node_func)
        workflow.add_edge("start_node", node_name)

    workflow.add_node("risk_management_agent", risk_management_agent)
    workflow.add_node("portfolio_manager", portfolio_management_agent)

    for key in EARNINGS_REACTION_ANALYSTS:
        node_name = f"{key}_agent"
        workflow.add_edge(node_name, "risk_management_agent")

    workflow.add_edge("risk_management_agent", "portfolio_manager")
    workflow.add_edge("portfolio_manager", END)

    workflow.set_entry_point("start_node")

    return workflow.compile(checkpointer=checkpointer) if checkpointer else workflow.compile()


def earnings_reaction_initial_state(
    tickers: list[str],
    start_date: str,
    end_date: str,
    portfolio: dict[str, Any],
    *,
    model_name: str = "claude-3-5-sonnet-latest",
    model_provider: str = "Anthropic",
    show_reasoning: bool = False,
) -> dict[str, Any]:
    """Build the initial AgentState payload for an Earnings Reaction run.

    Mirrors the shape of ``src.main.run_hedge_fund`` so the playbook plugs into
    the same agent contracts without reimplementing input handling.
    """
    return {
        "messages": [
            HumanMessage(
                content=(
                    "Run the Earnings Reaction Playbook. Each analyst evaluates the "
                    "named tickers in the context of the most recent earnings event "
                    "in the date range. Risk and portfolio managers consolidate."
                )
            )
        ],
        "data": {
            "tickers": tickers,
            "portfolio": portfolio,
            "start_date": start_date,
            "end_date": end_date,
            "analyst_signals": {},
        },
        "metadata": {
            "show_reasoning": show_reasoning,
            "model_name": model_name,
            "model_provider": model_provider,
            "workflow": "earnings_reaction",
        },
    }


def memory_checkpointer() -> MemorySaver:
    """In-process checkpointer. Zero-config. State lost on process exit.

    Use for tests and quick local runs. The compiled graph still gets the
    benefits of LangGraph's checkpoint mechanics (state inspection per node,
    replay within a single process) without any persistence concern.
    """
    return MemorySaver()


@contextmanager
def sqlite_checkpointer(db_path: str) -> Iterator[SqliteSaver]:
    """SQLite-backed checkpointer for the live demo system.

    Yields a ``SqliteSaver`` bound to ``db_path``. State persists across
    process restarts; a crashed run can be resumed by re-invoking the graph
    with the same ``thread_id`` in the run config.

    Use as a context manager so the underlying ``sqlite3.Connection`` is
    closed cleanly. In a long-lived FastAPI server, wire this into the
    lifespan context (see ``docs/sales-demo.md``).

    Example:
        with sqlite_checkpointer("./data/earnings_reaction.db") as saver:
            graph = build_earnings_reaction_graph(checkpointer=saver)
            graph.invoke(state, config={"configurable": {"thread_id": "run-001"}})
    """
    with SqliteSaver.from_conn_string(db_path) as saver:
        yield saver
