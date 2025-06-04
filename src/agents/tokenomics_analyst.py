from __future__ import annotations

import json

from langchain_core.messages import HumanMessage

from src.data.api import get_token_metrics
from src.graph.state import AgentState, show_agent_reasoning
from src.utils.progress import progress

##### Tokenomics Analyst #####


def tokenomics_analyst_agent(state: AgentState):
    """Analyze tokenomics data for crypto pairs."""
    data = state.get("data", {})
    pairs = data.get("pairs") or data.get("tickers") or []

    analysis = {}
    for pair in pairs:
        token = pair.split("/")[0]
        progress.update_status("tokenomics_analyst_agent", pair, "Fetching metrics")
        metrics = get_token_metrics(token)
        supply = metrics.get("market_data", {}).get("circulating_supply", 0) if metrics else 0
        max_supply = metrics.get("market_data", {}).get("max_supply", 0) if metrics else 0
        ratio = supply / max_supply if max_supply else 0
        signal = "bullish" if ratio < 0.5 else "bearish" if ratio > 0.9 else "neutral"
        analysis[pair] = {
            "signal": signal,
            "confidence": ratio,
            "reasoning": f"Circulating/max supply ratio {ratio:.2f}",
        }
        progress.update_status("tokenomics_analyst_agent", pair, "Done")

    message = HumanMessage(content=json.dumps(analysis), name="tokenomics_analyst_agent")
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(analysis, "Tokenomics Analyst")
    state["data"]["analyst_signals"]["tokenomics_analyst"] = analysis
    return {"messages": [message], "data": data}
