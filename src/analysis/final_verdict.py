"""Synthesize a final, actionable recommendation from all the inputs:
SnapshotReport (yfinance + rule-based), AgentRunResult (LangGraph council),
and BacktestSummary (technical track record).

The output is a `FinalRecommendation` containing the action, a 3-point
price target range, a hold period, suggested position sizing, risk grade,
key catalysts/risks, and a narrative explaining how the components combined.

All synthesis is rule-based and transparent — no hidden LLM call. The
methodology is fully documented in `compose_methodology()` so the user
can audit how every input contributed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.analysis.agent_runner import AgentRunResult
from src.analysis.backtest import BacktestSummary
from src.analysis.snapshot import SnapshotReport
from src.analysis.verdicts import Verdict


@dataclass
class FinalRecommendation:
    action: Verdict                # STRONG BUY / BUY / HOLD / REDUCE / SELL
    confidence_pct: float          # 0-100
    composite_score: float         # 0-100 — same scale as snapshot composite, but combined
    price_target_low: Optional[float]
    price_target_mid: Optional[float]
    price_target_high: Optional[float]
    upside_pct: Optional[float]    # mid target vs current price
    hold_period_label: str         # "1-3 years", "6-18 months", etc.
    hold_period_months_min: int
    hold_period_months_max: int
    position_size_pct: float       # 0-100, suggested portfolio %
    risk_grade: str                # "Low" / "Moderate" / "High" / "Very High"
    rationale: str                 # 3-5 sentence narrative
    key_catalysts: list[str] = field(default_factory=list)
    key_risks: list[str] = field(default_factory=list)
    component_scores: dict = field(default_factory=dict)


# --- Internal helpers -------------------------------------------------------


def _action_from_score(score: float) -> Verdict:
    if score >= 78:
        return "STRONG BUY"
    if score >= 62:
        return "BUY"
    if score >= 42:
        return "HOLD"
    if score >= 28:
        return "REDUCE"
    return "SELL"


def _hold_period(action: Verdict, snapshot: SnapshotReport) -> tuple[str, int, int]:
    """Hold-period guidance keyed off the verdict and snapshot quality."""
    # Look at ROE and revenue-growth verdicts as a proxy for "compounder quality".
    quality_flags = [
        m for m in snapshot.fundamental_metrics
        if m.name in ("ROE (TTM)", "ROE (3Y avg)", "ROIC (proxy)", "Revenue Growth (3Y CAGR)")
    ]
    quality_buys = sum(1 for m in quality_flags if m.verdict in ("BUY", "STRONG BUY"))
    is_compounder = quality_buys >= 3

    if action == "STRONG BUY":
        return ("3-5 years (long-term compounding)" if is_compounder else "12-24 months",
                36, 60) if is_compounder else ("12-24 months", 12, 24)
    if action == "BUY":
        return ("12-36 months" if is_compounder else "6-18 months",
                24 if is_compounder else 12, 36 if is_compounder else 18)
    if action == "HOLD":
        return ("Reassess in 3-6 months", 3, 6)
    if action == "REDUCE":
        return ("Trim within 1-3 months", 1, 3)
    return ("Exit within 30 days", 0, 1)


def _position_size(action: Verdict, confidence: float, risk_grade: str) -> float:
    """Suggest a portfolio weight (0-100%). Conservative by design."""
    base = {
        "STRONG BUY": 8.0,
        "BUY": 5.0,
        "HOLD": 2.0,
        "REDUCE": 0.0,
        "SELL": 0.0,
        "N/A": 0.0,
    }.get(action, 0.0)
    if risk_grade == "Very High":
        base *= 0.5
    elif risk_grade == "High":
        base *= 0.75
    # Scale by confidence (50% confidence → 70% of base, 90% confidence → 100% of base)
    scale = 0.4 + 0.6 * (confidence / 100.0)
    return round(base * scale, 1)


def _risk_grade(
    snapshot: SnapshotReport, agents: Optional[AgentRunResult], backtest: Optional[BacktestSummary]
) -> str:
    """Score volatility, valuation premium, balance-sheet strength, and analyst dispersion."""
    flags = 0
    # 1) Valuation premium
    if any(
        m.verdict == "SELL"
        for m in snapshot.fundamental_metrics
        if m.name in ("P/E (TTM)", "Forward P/E", "PEG", "EV/EBITDA")
    ):
        flags += 1
    # 2) Leverage
    if any(
        m.verdict == "SELL"
        for m in snapshot.fundamental_metrics
        if m.name == "Debt / Equity"
    ):
        flags += 1
    # 3) Technical regime
    if snapshot.technical_verdict == "SELL":
        flags += 1
    # 4) Analyst dispersion (wide low/high spread)
    a = snapshot.analyst
    if a.high_target and a.low_target and a.mean_target:
        spread = (a.high_target - a.low_target) / a.mean_target
        if spread > 0.6:
            flags += 1
    # 5) Backtest hit rate
    if backtest and backtest.hit_rate is not None and backtest.hit_rate < 0.5:
        flags += 1
    # 6) Council disagreement
    if agents and agents.agent_signals and agents.agreement_pct < 0.5:
        flags += 1

    if flags <= 1:
        return "Low"
    if flags == 2:
        return "Moderate"
    if flags == 3:
        return "High"
    return "Very High"


def _agent_score(agents: AgentRunResult) -> float:
    """Convert agent council output to a 0-100 score on the same scale as snapshot.composite_score."""
    if not agents.agent_signals:
        return 50.0
    bull_share = agents.bullish_count / max(1, agents.total_analysts)
    bear_share = agents.bearish_count / max(1, agents.total_analysts)
    net = bull_share - bear_share  # in [-1, 1]
    base = 50 + net * 50

    # Confidence-weighted average reinforcement: high-confidence bulls/bears nudge harder
    avg_conf = sum(s.confidence for s in agents.agent_signals) / agents.total_analysts
    nudge = (avg_conf - 50) / 5  # ±10 at extremes
    if net > 0:
        base += nudge
    elif net < 0:
        base -= nudge

    # PM override
    if agents.pm_decision:
        act = agents.pm_decision.action
        if "buy" in act:
            base = max(base, 72)
        elif "sell" in act or "short" in act:
            base = min(base, 28)

    return max(0.0, min(100.0, base))


# --- Catalyst / risk extraction --------------------------------------------


def _extract_catalysts(
    snapshot: SnapshotReport, agents: Optional[AgentRunResult]
) -> list[str]:
    out: list[str] = []
    for m in snapshot.fundamental_metrics:
        if m.verdict in ("BUY", "STRONG BUY") and m.name in (
            "ROE (TTM)",
            "ROE (3Y avg)",
            "ROIC (proxy)",
            "FCF Yield",
            "Revenue Growth (3Y CAGR)",
            "PEG",
            "Debt / Equity",
        ):
            out.append(f"{m.name} — {m.rationale}")
    for ind_row in snapshot.technical_indicators:
        if ind_row.signal in ("BUY", "STRONG BUY") and ind_row.name in (
            "Price vs SMA 200 + slope",
            "MACD",
            "Volume vs 50d avg",
        ):
            out.append(f"{ind_row.name} — {ind_row.rationale}")
    if (
        snapshot.analyst.pct_buy is not None
        and snapshot.analyst.pct_strong_buy is not None
        and (snapshot.analyst.pct_buy + snapshot.analyst.pct_strong_buy) >= 0.6
    ):
        pct = snapshot.analyst.pct_buy + snapshot.analyst.pct_strong_buy
        out.append(f"Analyst consensus — {pct*100:.0f}% Buy/Strong Buy among {snapshot.analyst.total_analysts or '?'} covering")
    if agents and agents.bullish_count >= 3 and agents.bullish_count > agents.bearish_count:
        top = next((s for s in agents.agent_signals if s.signal == "bullish"), None)
        if top:
            snippet = (top.reasoning[:140] + "…") if len(top.reasoning) > 140 else top.reasoning
            out.append(f"AI council bullish lead ({top.agent_name}) — {snippet}")
    return out[:5]


def _extract_risks(
    snapshot: SnapshotReport, agents: Optional[AgentRunResult]
) -> list[str]:
    out: list[str] = []
    for m in snapshot.fundamental_metrics:
        if m.verdict in ("SELL", "REDUCE") and m.name in (
            "P/E (TTM)",
            "Forward P/E",
            "PEG",
            "EV/EBITDA",
            "Debt / Equity",
            "FCF Yield",
        ):
            out.append(f"{m.name} — {m.rationale}")
    for ind_row in snapshot.technical_indicators:
        if ind_row.signal in ("SELL",) and ind_row.name in (
            "RSI (14)",
            "Bollinger Bands (20, 2σ)",
            "Bollinger Bands",
            "Price vs SMA 200 + slope",
        ):
            out.append(f"{ind_row.name} — {ind_row.rationale}")
    if (
        snapshot.analyst.pct_sell is not None
        and snapshot.analyst.pct_strong_sell is not None
        and (snapshot.analyst.pct_sell + snapshot.analyst.pct_strong_sell) >= 0.20
    ):
        pct = snapshot.analyst.pct_sell + snapshot.analyst.pct_strong_sell
        out.append(f"Analyst caution — {pct*100:.0f}% Sell/Strong Sell")
    if agents and agents.bearish_count > 0 and agents.bearish_count >= agents.bullish_count:
        bear = next((s for s in agents.agent_signals if s.signal == "bearish"), None)
        if bear:
            snippet = (bear.reasoning[:140] + "…") if len(bear.reasoning) > 140 else bear.reasoning
            out.append(f"AI council bearish lead ({bear.agent_name}) — {snippet}")
    return out[:5]


# --- Main entry point ------------------------------------------------------


def synthesize(
    snapshot: SnapshotReport,
    agents: Optional[AgentRunResult] = None,
    backtest: Optional[BacktestSummary] = None,
) -> FinalRecommendation:
    snapshot_score = snapshot.composite_score
    component_scores: dict[str, float] = {"snapshot": snapshot_score}

    # Weight the snapshot composite + agent council. If agents missing or
    # failed, just use the snapshot. If we have a backtest hit rate we
    # tilt the confidence slightly.
    if agents and not agents.error and agents.agent_signals:
        ag_score = _agent_score(agents)
        component_scores["ai_council"] = ag_score
        combined = 0.55 * snapshot_score + 0.45 * ag_score
    else:
        combined = snapshot_score

    if backtest and backtest.hit_rate is not None:
        component_scores["backtest_hit_rate"] = backtest.hit_rate * 100
        # If our track record is poor (<40%) we discount the conviction by
        # pulling the combined score toward 50 (HOLD). If great (>70%) we
        # amplify it slightly.
        if backtest.hit_rate < 0.4:
            combined = 50 + (combined - 50) * 0.6
        elif backtest.hit_rate > 0.7:
            combined = 50 + (combined - 50) * 1.1
            combined = max(0.0, min(100.0, combined))

    action = _action_from_score(combined)
    risk = _risk_grade(snapshot, agents, backtest)
    hold_label, hold_min, hold_max = _hold_period(action, snapshot)

    # Confidence: distance from HOLD center (50), scaled and clamped
    distance_from_center = abs(combined - 50)  # 0-50
    base_conf = 50 + distance_from_center * 0.9
    # Penalize if council and snapshot disagree sharply
    if agents and "ai_council" in component_scores:
        gap = abs(component_scores["snapshot"] - component_scores["ai_council"])
        if gap > 30:
            base_conf -= 10
    confidence = max(40.0, min(95.0, base_conf))

    size = _position_size(action, confidence, risk)

    # Price target range
    target_low = target_mid = target_high = upside = None
    a = snapshot.analyst
    if a.mean_target and snapshot.current_price:
        analyst_mid = a.mean_target
        # Our model adjusts the analyst mean:
        # - More bullish (combined >= 75): +6%
        # - Bullish (60-75): +2%
        # - Neutral (45-60): 0%
        # - Bearish (30-45): -4%
        # - Strongly bearish (<30): -10%
        if combined >= 75:
            mult = 1.06
        elif combined >= 60:
            mult = 1.02
        elif combined >= 45:
            mult = 1.00
        elif combined >= 30:
            mult = 0.96
        else:
            mult = 0.90
        target_mid = analyst_mid * mult
        target_low = a.low_target if a.low_target else target_mid * 0.88
        target_high = a.high_target if a.high_target else target_mid * 1.12
        upside = target_mid / snapshot.current_price - 1.0

    catalysts = _extract_catalysts(snapshot, agents)
    risks = _extract_risks(snapshot, agents)

    # Narrative rationale
    parts: list[str] = []
    parts.append(f"Composite verdict {action} (score {combined:.0f}/100, confidence {confidence:.0f}%).")
    parts.append(
        f"Snapshot model: {snapshot.overall_verdict_label.lower()} ({snapshot.composite_score:.0f}/100)."
    )
    if agents and not agents.error:
        parts.append(
            f"AI investor council ({agents.total_analysts} analysts): {agents.bullish_count} bullish / "
            f"{agents.neutral_count} neutral / {agents.bearish_count} bearish "
            f"({agents.agreement_pct*100:.0f}% agreement)."
        )
        if agents.pm_decision:
            parts.append(
                f"Portfolio Manager: {agents.pm_decision.action.upper()} {agents.pm_decision.quantity or ''} "
                f"(conf. {agents.pm_decision.confidence:.0f}%)."
            )
    if backtest and backtest.points:
        hr = backtest.hit_rate
        parts.append(
            f"Technical backtest: hit rate {hr*100:.0f}% across {len(backtest.points)} historical signals." if hr is not None else ""
        )
    if upside is not None and target_mid is not None:
        parts.append(
            f"Price-target midpoint ${target_mid:,.2f} implies {upside*100:+.1f}% from current."
        )
    parts.append(f"Risk grade: {risk}.")
    if size > 0:
        parts.append(f"Suggested position: {size:.1f}% of portfolio over a {hold_label.lower()} horizon.")
    else:
        parts.append(f"Action: {hold_label.lower()}.")

    rationale = " ".join(p for p in parts if p)

    return FinalRecommendation(
        action=action,
        confidence_pct=confidence,
        composite_score=combined,
        price_target_low=target_low,
        price_target_mid=target_mid,
        price_target_high=target_high,
        upside_pct=upside,
        hold_period_label=hold_label,
        hold_period_months_min=hold_min,
        hold_period_months_max=hold_max,
        position_size_pct=size,
        risk_grade=risk,
        rationale=rationale,
        key_catalysts=catalysts,
        key_risks=risks,
        component_scores=component_scores,
    )


def compose_methodology(rec: FinalRecommendation) -> str:
    """Plain-English explanation of how the final verdict was derived. Shown in the report."""
    pieces = [
        f"<b>Composite score: {rec.composite_score:.1f}/100</b> mapped to action <b>{rec.action}</b> using bands: "
        f"&lt;28 SELL · 28-42 REDUCE · 42-62 HOLD · 62-78 BUY · ≥78 STRONG BUY.",
        "Component inputs (weights):",
        "<ul>",
        f"<li><b>Snapshot model (55% if council present, else 100%):</b> rule-based aggregation of "
        f"price returns, 10 fundamental metrics, 6 technical indicators, analyst consensus, and macro tilt.</li>",
    ]
    if "ai_council" in rec.component_scores:
        pieces.append(
            "<li><b>AI investor council (45%):</b> 14+ LLM-driven analyst personas (Buffett, Munger, Lynch, Druckenmiller, "
            "Marks, Klarman, etc.) — score derived from bullish-vs-bearish mix, confidence-weighted, with Portfolio "
            "Manager override at ±72/28 floor/ceiling.</li>"
        )
    if "backtest_hit_rate" in rec.component_scores:
        pieces.append(
            f"<li><b>Backtest adjustment:</b> historical hit rate "
            f"{rec.component_scores['backtest_hit_rate']:.0f}% — if &lt;40%, conviction pulled toward HOLD (×0.6 distance from 50); "
            f"if &gt;70%, conviction amplified (×1.1).</li>"
        )
    pieces.append("</ul>")
    pieces.append(
        f"<b>Price target ${rec.price_target_mid:,.2f}</b>" if rec.price_target_mid else "<b>Price target unavailable</b> (no analyst data)."
    )
    if rec.price_target_mid:
        pieces.append(" computed from analyst mean × score-dependent multiplier (0.90× at SELL → 1.06× at STRONG BUY).")
    pieces.append(
        f" <b>Hold period {rec.hold_period_label}</b> set by verdict + quality flags "
        f"(ROE / ROIC / Revenue Growth — wide-moat compounders earn longer horizons)."
    )
    pieces.append(
        f" <b>Position size {rec.position_size_pct:.1f}%</b> = verdict base "
        f"(STRONG BUY 8% / BUY 5% / HOLD 2% / REDUCE-SELL 0%) × risk factor "
        f"(High ×0.75, Very High ×0.5) × confidence scale."
    )
    return "".join(pieces)
