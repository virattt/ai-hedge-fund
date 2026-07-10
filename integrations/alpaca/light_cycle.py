"""Run a light analysis cycle — rule-based analysts only, no LLM."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage

from integrations.alpaca.light_portfolio import generate_light_decisions
from src.agents.risk_manager import risk_management_agent
from src.graph.state import AgentState
from src.utils.analysts import get_analyst_nodes

logger = logging.getLogger(__name__)


def _build_state(
    *,
    tickers: list[str],
    portfolio: dict[str, Any],
    start_date: str,
    end_date: str,
    show_reasoning: bool,
) -> AgentState:
    return {
        "messages": [
            HumanMessage(content="Light refresh — rule-based analysts only."),
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
            "model_name": "none",
            "model_provider": "none",
        },
    }


def _apply_update(state: AgentState, update: dict[str, Any]) -> AgentState:
    state["messages"] = update.get("messages", state["messages"])
    merged_data = {**state["data"], **update.get("data", {})}
    if "analyst_signals" in state["data"]:
        merged_signals = {**state["data"]["analyst_signals"]}
        merged_signals.update(merged_data.get("analyst_signals", {}))
        merged_data["analyst_signals"] = merged_signals
    state["data"] = merged_data
    return state


def run_light_analysis(
    *,
    tickers: list[str],
    portfolio: dict[str, Any],
    start_date: str,
    end_date: str,
    light_analysts: list[str],
    show_reasoning: bool = False,
) -> dict[str, Any]:
    """Execute rule-based analysts + risk manager; return hedge-fund-shaped result."""
    from src.utils.progress import progress

    progress.start()
    try:
        state = _build_state(
            tickers=tickers,
            portfolio=portfolio,
            start_date=start_date,
            end_date=end_date,
            show_reasoning=show_reasoning,
        )
        analyst_nodes = get_analyst_nodes()

        for key in light_analysts:
            if key not in analyst_nodes:
                logger.warning("Unknown light analyst %s — skipping", key)
                continue
            _node_name, agent_func = analyst_nodes[key]
            update = agent_func(state)
            state = _apply_update(state, update)

        update = risk_management_agent(state)
        state = _apply_update(state, update)

        decisions = generate_light_decisions(
            tickers=tickers,
            analyst_signals=state["data"]["analyst_signals"],
            portfolio=portfolio,
        )
        return {
            "decisions": decisions,
            "analyst_signals": state["data"]["analyst_signals"],
        }
    finally:
        progress.stop()


def snapshot_reference_prices(agent_result: dict[str, Any]) -> dict[str, float]:
    """Extract latest prices from analyst signals for trigger baselines."""
    prices: dict[str, float] = {}
    signals = agent_result.get("analyst_signals", {})
    risk = signals.get("risk_management_agent", {})
    if isinstance(risk, dict):
        for ticker, payload in risk.items():
            if isinstance(payload, dict) and payload.get("current_price") is not None:
                prices[ticker.upper()] = float(payload["current_price"])
    if prices:
        return prices
    for _agent, agent_signals in signals.items():
        if not isinstance(agent_signals, dict):
            continue
        for ticker, payload in agent_signals.items():
            if not isinstance(payload, dict):
                continue
            price = payload.get("current_price")
            if price is not None:
                prices[ticker.upper()] = float(price)
    return prices


def fetch_spy_price(end_date: str | None = None) -> float | None:
    end = end_date or datetime.now().date().isoformat()
    start = end  # same-day snapshot
    try:
        from datetime import timedelta

        from integrations.alpaca.market_hours import now_et

        start = (now_et().date() - timedelta(days=5)).isoformat()
        from src.tools.api import get_prices

        rows = get_prices("SPY", start, end)
        if rows:
            return float(rows[-1].close)
    except Exception as exc:
        logger.debug("SPY price fetch failed: %s", exc)
    return None
