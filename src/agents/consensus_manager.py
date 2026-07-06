"""Consensus Manager Agent — aggregates multi-agent signals into a consensus view.

Sits between risk_manager and portfolio_manager in the LangGraph workflow.
No LLM calls — purely deterministic computation on top of existing analyst signals.
"""

import json

from langchain_core.messages import HumanMessage

from src.graph.state import AgentState, show_agent_reasoning
from src.consensus.aggregation import build_consensus_result
from src.consensus.models import AgentContribution, ConsensusResult
from src.utils.progress import progress


# Default equal weights for all agents
DEFAULT_AGENT_WEIGHTS: dict[str, float] = {}


def consensus_manager_agent(state: AgentState, agent_id: str = "consensus_manager"):
    """Aggregate analyst signals into a consensus view per ticker.

    This agent:
    1. Collects all analyst signals from state["data"]["analyst_signals"]
    2. Groups them by ticker
    3. Computes consensus using the configured strategy
    4. Stores the consensus result back into state
    5. Flags outlier agents and disagreement levels

    The portfolio manager can then use state["data"]["consensus"] to make
    more informed decisions.
    """
    data = state["data"]
    tickers = data["tickers"]
    analyst_signals = data["analyst_signals"]

    # Strategy from metadata (default: weighted)
    consensus_strategy = state.get("metadata", {}).get("consensus_strategy", "weighted")

    progress.update_status(agent_id, None, "Aggregating analyst signals")

    # Collect contributions per ticker
    contributions_by_ticker: dict[str, list[AgentContribution]] = {
        t: [] for t in tickers
    }

    for agent_name, signals in analyst_signals.items():
        # Skip risk management and portfolio management agents
        if agent_name.startswith("risk_management_agent") or agent_name.startswith(
            "portfolio_manager"
        ):
            continue

        for ticker in tickers:
            ticker_data = signals.get(ticker, {})
            signal_val = ticker_data.get("signal")
            confidence_val = ticker_data.get("confidence")

            if signal_val is not None and confidence_val is not None:
                contributions_by_ticker[ticker].append(
                    AgentContribution(
                        agent_name=agent_name,
                        signal=str(signal_val),
                        confidence=float(confidence_val),
                        reasoning=str(ticker_data.get("reasoning", "")),
                    )
                )

    # Build consensus
    result = build_consensus_result(
        signals_by_ticker=contributions_by_ticker,
        strategy=consensus_strategy,
        weights=DEFAULT_AGENT_WEIGHTS,
    )

    # Store consensus result in state for portfolio manager to use
    consensus_data = {}
    for ticker, cs in result.signals.items():
        consensus_data[ticker] = {
            "signal": cs.signal,
            "score": cs.score,
            "confidence": cs.confidence,
            "agreement": cs.agreement,
            "outliers": cs.outliers,
            "contributions_count": len(cs.contributions),
        }

    state["data"]["consensus"] = consensus_data

    progress.update_status(agent_id, None, "Consensus built")

    # Create message for the graph
    message = HumanMessage(
        content=json.dumps(consensus_data),
        name=agent_id,
    )

    # Show reasoning if requested
    if state["metadata"].get("show_reasoning"):
        display_data = {
            ticker: {
                "signal": cs.signal,
                "score": cs.score,
                "confidence": cs.confidence,
                "agreement": cs.agreement,
                "outliers": cs.outliers,
                "agents": len(cs.contributions),
            }
            for ticker, cs in result.signals.items()
        }
        show_agent_reasoning(display_data, "Consensus Manager")

    progress.update_status(agent_id, None, "Done")

    return {
        "messages": state["messages"] + [message],
        "data": state["data"],
    }
