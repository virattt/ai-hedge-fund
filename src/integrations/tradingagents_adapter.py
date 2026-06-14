"""ai-hedge-fund → TradingAgents analyzing-flow adapter (PRD: the hybrid seam).

TradingAgents (langgraph 0.4+) and ai-hedge-fund (langgraph 0.2) cannot share an
interpreter, so this calls TradingAgents' debate graph across a PROCESS boundary:
``uv run --project <TradingAgent> python tradingagents_runner.py`` with JSON over
stdin/stdout. Any failure (missing project, timeout, non-zero exit, bad output,
runner-reported error) is mapped to a *degraded* result with an
``insufficient-evidence`` label — never a fabricated directional signal.

The directional rating (Buy/Sell/…) is mapped to a descriptive ``ReportLabel``;
the buy/sell wording is never surfaced (research-only posture, PRD §9.9).
"""

import json
import os
import subprocess
from dataclasses import dataclass, field

from src.storage.models import ReportLabel

TA_PROJECT = os.environ.get("TRADINGAGENTS_PROJECT", "/Users/laiyama/Stocks/TradingAgent")
TA_RUNNER = os.path.join(TA_PROJECT, "tradingagents_runner.py")
DEFAULT_TIMEOUT = int(os.environ.get("TRADINGAGENTS_TIMEOUT", "900"))

# TradingAgents rating → descriptive ReportLabel (never the raw buy/sell word).
_RATING_TO_LABEL: dict[str, ReportLabel] = {
    "buy": ReportLabel.THESIS_SUPPORTIVE,
    "overweight": ReportLabel.THESIS_SUPPORTIVE,
    "hold": ReportLabel.MIXED,
    "underweight": ReportLabel.THESIS_CHALLENGING,
    "sell": ReportLabel.THESIS_CHALLENGING,
}
_LABEL_CONFIDENCE = {
    ReportLabel.THESIS_SUPPORTIVE: 70.0,
    ReportLabel.THESIS_CHALLENGING: 70.0,
    ReportLabel.MIXED: 50.0,
    ReportLabel.INSUFFICIENT_EVIDENCE: 0.0,
}


@dataclass(frozen=True)
class AnalyzingFlowResult:
    ticker: str
    label: ReportLabel
    confidence: float
    degraded: bool
    summary: str
    raw_decision: str | None = None
    agent_reports: dict = field(default_factory=dict)
    error: str | None = None


def _degraded(ticker: str, reason: str) -> AnalyzingFlowResult:
    return AnalyzingFlowResult(
        ticker=ticker,
        label=ReportLabel.INSUFFICIENT_EVIDENCE,
        confidence=0.0,
        degraded=True,
        summary="Analysis unavailable.",
        raw_decision=None,
        agent_reports={},
        error=reason,
    )


def _label_for(decision: str | None) -> ReportLabel:
    if not decision:
        return ReportLabel.INSUFFICIENT_EVIDENCE
    return _RATING_TO_LABEL.get(decision.strip().lower(), ReportLabel.MIXED)


def map_runner_payload(ticker: str, payload: dict) -> AnalyzingFlowResult:
    """Pure mapping from the runner's JSON payload → AnalyzingFlowResult.

    Separated from the subprocess call so it can be unit-tested directly.
    """
    if not payload.get("ok"):
        return _degraded(ticker, payload.get("error", "unknown runner error"))
    decision = payload.get("decision")
    label = _label_for(decision)
    reports = payload.get("reports") or {}
    summary = reports.get("final_trade_decision") or f"TradingAgents rating: {decision}"
    if isinstance(summary, str) and len(summary) > 800:
        summary = summary[:800] + "…"
    return AnalyzingFlowResult(
        ticker=ticker,
        label=label,
        confidence=_LABEL_CONFIDENCE[label],
        degraded=False,
        summary=summary,
        raw_decision=decision,
        agent_reports=reports,
    )


def run_analyzing_flow(
    ticker: str,
    trade_date: str,
    *,
    asset_type: str = "stock",
    config_overrides: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> AnalyzingFlowResult:
    """Run TradingAgents' debate graph for one ticker; degrade on any failure."""
    if not os.path.exists(TA_RUNNER):
        return _degraded(ticker, f"tradingagents runner not found at {TA_RUNNER}")

    request = json.dumps({"ticker": ticker, "trade_date": trade_date, "asset_type": asset_type, "config_overrides": config_overrides or {}})
    try:
        proc = subprocess.run(
            ["uv", "run", "--project", TA_PROJECT, "python", TA_RUNNER],
            input=request,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=TA_PROJECT,
        )
    except subprocess.TimeoutExpired:
        return _degraded(ticker, f"tradingagents timed out after {timeout}s")
    except (OSError, ValueError) as exc:
        return _degraded(ticker, f"tradingagents subprocess error: {exc}")

    if proc.returncode != 0:
        return _degraded(ticker, f"runner exited {proc.returncode}: {(proc.stderr or '')[-300:]}")

    last_line = (proc.stdout or "").strip().splitlines()[-1:] or [""]
    try:
        payload = json.loads(last_line[0])
    except (json.JSONDecodeError, IndexError) as exc:
        return _degraded(ticker, f"unparseable runner output: {exc}")
    return map_runner_payload(ticker, payload)
