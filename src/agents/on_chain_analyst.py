from __future__ import annotations

import json

from langchain_core.messages import HumanMessage

from src.data.api import get_token_metrics
from src.graph.state import AgentState, show_agent_reasoning
from src.utils.progress import progress

##### On-Chain Analyst #####


def on_chain_analyst_agent(state: AgentState):
    """Analyze on-chain metrics for crypto pairs."""
    data = state.get("data", {})
    pairs = data.get("pairs") or data.get("tickers") or []

    analysis = {}
    for pair in pairs:
        token = pair.split("/")[0]
        progress.update_status("on_chain_analyst_agent", pair, "Fetching metrics")
        metrics = get_token_metrics(token)
        market = metrics.get("market_data", {}) if metrics else {}
        price_change = market.get("price_change_percentage_24h", 0)
        signal = "bullish" if price_change > 0 else "bearish" if price_change < 0 else "neutral"
        analysis[pair] = {
            "signal": signal,
            "confidence": abs(price_change),
            "reasoning": f"24h price change {price_change}%",
        }
        progress.update_status("on_chain_analyst_agent", pair, "Done")

    message = HumanMessage(content=json.dumps(analysis), name="on_chain_analyst_agent")
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(analysis, "On-Chain Analyst")
    state["data"]["analyst_signals"]["on_chain_analyst"] = analysis
    return {"messages": [message], "data": data}
