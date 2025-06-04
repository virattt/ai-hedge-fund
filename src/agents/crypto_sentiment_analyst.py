from __future__ import annotations

import json

from langchain_core.messages import HumanMessage

from src.data.api import get_token_metrics
from src.graph.state import AgentState, show_agent_reasoning
from src.utils.progress import progress

##### Crypto Sentiment Analyst #####


def crypto_sentiment_analyst_agent(state: AgentState):
    """Assess crypto sentiment from short-term price momentum."""
    data = state.get("data", {})
    pairs = data.get("pairs") or data.get("tickers") or []

    analysis = {}
    for pair in pairs:
        token = pair.split("/")[0]
        progress.update_status("crypto_sentiment_analyst_agent", pair, "Fetching metrics")
        metrics = get_token_metrics(token)
        market = metrics.get("market_data", {}) if metrics else {}
        momentum = market.get("price_change_percentage_7d", 0)
        signal = "bullish" if momentum > 0 else "bearish" if momentum < 0 else "neutral"
        analysis[pair] = {
            "signal": signal,
            "confidence": abs(momentum),
            "reasoning": f"7d price change {momentum}%",
        }
        progress.update_status("crypto_sentiment_analyst_agent", pair, "Done")

    message = HumanMessage(content=json.dumps(analysis), name="crypto_sentiment_analyst_agent")
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(analysis, "Crypto Sentiment Analyst")
    state["data"]["analyst_signals"]["crypto_sentiment_analyst"] = analysis
    return {"messages": [message], "data": data}
