"""Orchestrator: combines snapshot + backtest + AI investor council + synthesis.

The standard `generate_snapshot()` already produces snapshot + backtest cheaply
(~5 sec/ticker). This module adds the slow LLM-driven LangGraph council on
top, then attaches a FinalRecommendation that fuses all three inputs.

`deep_analyze()` is intentionally synchronous — the caller (web server) is
responsible for showing a loading state during the ~30-60s LangGraph call.
"""

from __future__ import annotations

from typing import Optional

from src.analysis.agent_runner import AgentRunResult, run_agents
from src.analysis.final_verdict import FinalRecommendation, synthesize
from src.analysis.snapshot import SnapshotReport, generate_snapshot


def attach_final_verdict(report: SnapshotReport) -> SnapshotReport:
    """Compute the FinalRecommendation from whatever inputs `report` carries
    and attach it. Safe to call whether or not `report.agents` is populated."""
    rec = synthesize(report, agents=report.agents, backtest=report.backtest)
    report.final_verdict = rec
    return report


def shallow_analyze(ticker: str) -> SnapshotReport:
    """Snapshot + backtest + rule-based verdict only. ~5 sec per ticker."""
    rep = generate_snapshot(ticker)
    attach_final_verdict(rep)
    return rep


def deep_analyze(
    ticker: str,
    *,
    model_name: str = "claude-opus-4-7",
    model_provider: str = "Anthropic",
    selected_analysts: Optional[list[str]] = None,
) -> SnapshotReport:
    """Snapshot + backtest + LangGraph council + final synthesis.

    Typical wall-clock: 30-60 seconds, dominated by the LangGraph LLM calls.
    If the agent run fails (e.g. no LLM credentials, network issue) we still
    return a usable report — `report.agents.error` carries the message and
    the final verdict simply falls back to snapshot-only.
    """
    rep = generate_snapshot(ticker)
    rep.agents = run_agents(
        ticker,
        model_name=model_name,
        model_provider=model_provider,
        selected_analysts=selected_analysts,
    )
    attach_final_verdict(rep)
    return rep
