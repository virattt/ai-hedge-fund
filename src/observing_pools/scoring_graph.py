"""Scoring-only analyst graph (PRD v4 §11.4 / Phase 5).

Reuses ai-hedge-fund's analyst nodes but wires ``start → analysts → END``,
dropping ``risk_management_agent`` and ``portfolio_manager`` (the expensive
synthesis nodes) since pools need per-analyst signals, not a trade decision.

This is the *real* ``run_analysts`` implementation. It imports the agent stack,
so it is kept separate from ``pipeline.py`` (whose pure logic is unit-tested with
a stub runner — no LLM calls, no network).
"""

from datetime import datetime, timedelta

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph

from src.graph.state import AgentState
from src.utils.analysts import get_analyst_nodes


def _start(state: AgentState) -> AgentState:
    return state


def _build_scoring_workflow(selected_analysts: list[str]) -> StateGraph:
    workflow = StateGraph(AgentState)
    workflow.add_node("start_node", _start)
    analyst_nodes = get_analyst_nodes()
    for key in selected_analysts:
        node_name, node_func = analyst_nodes[key]
        workflow.add_node(node_name, node_func)
        workflow.add_edge("start_node", node_name)
        workflow.add_edge(node_name, END)  # scoring-only: no risk/portfolio
    workflow.set_entry_point("start_node")
    return workflow


def run_scoring_analysts(
    tickers: list[str],
    selected_analysts: list[str],
    end_date: str,
    *,
    start_date: str | None = None,
    model_name: str = "gpt-4.1",
    model_provider: str = "OpenAI",
) -> tuple[dict[str, dict[str, dict]], dict]:
    """Run the scoring-only graph over ``tickers``. Returns (analyst_signals, token_cost).

    ``analyst_signals`` is ``{agent_id: {ticker: {signal, confidence, ...}}}``.
    Token cost is a coarse proxy in Phase 0 (real metering is an expansion-phase item).
    """
    if start_date is None:
        start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")

    workflow = _build_scoring_workflow(selected_analysts)
    agent = workflow.compile()
    final_state = agent.invoke(
        {
            "messages": [HumanMessage(content="Score these tickers for observing-pool ranking.")],
            "data": {
                "tickers": tickers,
                "portfolio": {"cash": 0.0, "positions": {}},
                "start_date": start_date,
                "end_date": end_date,
                "analyst_signals": {},
                "degraded_analysts": [],
            },
            "metadata": {"show_reasoning": False, "model_name": model_name, "model_provider": model_provider},
        },
    )
    signals = final_state["data"]["analyst_signals"]
    degraded = sorted(set(final_state["data"].get("degraded_analysts", [])))
    token_cost = {
        "calls": len(selected_analysts) * len(tickers),
        "tokens": None,
        "est_usd": None,
        "degraded_analysts": degraded,
    }
    return signals, token_cost
