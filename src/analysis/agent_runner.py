"""Run the LangGraph hedge fund pipeline programmatically.

`run_hedge_fund` (defined in src/main.py) drives a multi-agent council
(Buffett, Munger, Graham, Lynch, Druckenmiller, Marks, Klarman, etc.)
plus a Risk Manager and Portfolio Manager. This module wraps that call
with stdout suppression so it can be invoked from a web server without
polluting the console, and unpacks the response into clean dataclasses
for the UI.
"""

from __future__ import annotations

import contextlib
import io
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional


_PRETTY_AGENT_NAMES = {
    "warren_buffett_agent": "Warren Buffett",
    "charlie_munger_agent": "Charlie Munger",
    "ben_graham_agent": "Ben Graham",
    "phil_fisher_agent": "Phil Fisher",
    "peter_lynch_agent": "Peter Lynch",
    "bill_ackman_agent": "Bill Ackman",
    "michael_burry_agent": "Michael Burry",
    "mohnish_pabrai_agent": "Mohnish Pabrai",
    "nassim_taleb_agent": "Nassim Taleb",
    "stanley_druckenmiller_agent": "Stanley Druckenmiller",
    "cathie_wood_agent": "Cathie Wood",
    "aswath_damodaran_agent": "Aswath Damodaran",
    "rakesh_jhunjhunwala_agent": "Rakesh Jhunjhunwala",
    "valuation_agent": "Valuation Model",
    "sentiment_agent": "Sentiment Analyst",
    "fundamentals_agent": "Fundamentals Analyst",
    "technicals_agent": "Technicals Analyst",
    "risk_management_agent": "Risk Manager",
    "fyi_market_context_agent": "Market Context (FYI)",
    "fyi_deep_technical_agent": "Deep Technical (FYI)",
    "fyi_deep_fundamental_agent": "Deep Fundamental (FYI)",
}


@dataclass
class AgentSignal:
    agent_id: str
    agent_name: str  # human-readable
    signal: str       # 'bullish', 'bearish', 'neutral'
    confidence: float  # 0-100
    reasoning: str


@dataclass
class PMDecision:
    action: str       # 'buy', 'sell', 'short', 'cover', 'hold'
    quantity: int
    confidence: float  # 0-100
    reasoning: str


@dataclass
class AgentRunResult:
    ticker: str
    pm_decision: Optional[PMDecision]
    agent_signals: list[AgentSignal] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    error: Optional[str] = None

    @property
    def bullish_count(self) -> int:
        return sum(1 for s in self.agent_signals if s.signal == "bullish")

    @property
    def bearish_count(self) -> int:
        return sum(1 for s in self.agent_signals if s.signal == "bearish")

    @property
    def neutral_count(self) -> int:
        return sum(1 for s in self.agent_signals if s.signal == "neutral")

    @property
    def total_analysts(self) -> int:
        return len(self.agent_signals)

    @property
    def consensus_signal(self) -> str:
        """Majority bias across the analyst council."""
        if not self.agent_signals:
            return "neutral"
        counts = {
            "bullish": self.bullish_count,
            "bearish": self.bearish_count,
            "neutral": self.neutral_count,
        }
        return max(counts, key=counts.get)

    @property
    def agreement_pct(self) -> float:
        if not self.agent_signals:
            return 0.0
        counts = [self.bullish_count, self.bearish_count, self.neutral_count]
        return max(counts) / sum(counts) if sum(counts) > 0 else 0.0


def _pretty_name(agent_id: str) -> str:
    return _PRETTY_AGENT_NAMES.get(
        agent_id, agent_id.replace("_agent", "").replace("_", " ").title()
    )


def run_agents(
    ticker: str,
    *,
    model_name: str = "claude-opus-4-7",
    model_provider: str = "Anthropic",
    selected_analysts: Optional[list[str]] = None,
    days_back: int = 180,
    show_reasoning: bool = False,
) -> AgentRunResult:
    """Run the multi-agent LangGraph pipeline for ONE ticker.

    Defaults assume the Claude Code subscription fallback wired into
    `src/llm/models.py` will pick up an unset ANTHROPIC_API_KEY.
    """
    from src.main import run_hedge_fund  # lazy import — avoids a circular at module load

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    portfolio = {
        "cash": 100_000.0,
        "margin_requirement": 0.0,
        "margin_used": 0.0,
        "positions": {
            ticker: {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
        },
        "realized_gains": {ticker: {"long": 0.0, "short": 0.0}},
    }

    started = time.perf_counter()
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            result = run_hedge_fund(
                tickers=[ticker],
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                portfolio=portfolio,
                show_reasoning=show_reasoning,
                selected_analysts=selected_analysts or [],
                model_name=model_name,
                model_provider=model_provider,
            )
    except Exception as exc:
        return AgentRunResult(
            ticker=ticker,
            pm_decision=None,
            elapsed_seconds=time.perf_counter() - started,
            error=f"{type(exc).__name__}: {exc}",
        )

    elapsed = time.perf_counter() - started

    decisions: dict = result.get("decisions") or {}
    signals: dict = result.get("analyst_signals") or {}

    pm_decision = None
    pm = decisions.get(ticker) if isinstance(decisions, dict) else None
    if isinstance(pm, dict):
        pm_decision = PMDecision(
            action=str(pm.get("action") or "hold").lower(),
            quantity=int(pm.get("quantity") or 0),
            confidence=float(pm.get("confidence") or 0.0),
            reasoning=str(pm.get("reasoning") or "").strip(),
        )

    agent_signals: list[AgentSignal] = []
    for agent_id, ticker_signals in (signals or {}).items():
        if not isinstance(ticker_signals, dict):
            continue
        sig = ticker_signals.get(ticker)
        if not isinstance(sig, dict):
            continue
        agent_signals.append(
            AgentSignal(
                agent_id=agent_id,
                agent_name=_pretty_name(agent_id),
                signal=str(sig.get("signal") or "neutral").lower(),
                confidence=float(sig.get("confidence") or 0.0),
                reasoning=str(sig.get("reasoning") or "").strip(),
            )
        )

    # Sort: bullish first, then neutral, then bearish; within each, by confidence desc
    rank = {"bullish": 0, "neutral": 1, "bearish": 2}
    agent_signals.sort(key=lambda s: (rank.get(s.signal, 1), -s.confidence))

    return AgentRunResult(
        ticker=ticker,
        pm_decision=pm_decision,
        agent_signals=agent_signals,
        elapsed_seconds=elapsed,
    )
