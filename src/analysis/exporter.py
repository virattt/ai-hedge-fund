"""Render a SnapshotReport as Markdown for download / sharing / git-diff.

The Markdown output mirrors the detail-page sections in their full depth:
final verdict + targets + price snapshot + 10 fundamentals + 6 technicals +
analyst consensus + backtest + multi-horizon targets + (if present)
AI investor council + PM decision + synthesis + methodology footnote.

Pure stdlib + the SnapshotReport dataclass. No external deps.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.analysis.snapshot import SnapshotReport


def _money(v: Optional[float]) -> str:
    if v is None or v != v:
        return "—"
    if abs(v) >= 1e12:
        return f"${v/1e12:.2f}T"
    if abs(v) >= 1e9:
        return f"${v/1e9:.2f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:.2f}M"
    return f"${v:,.2f}"


def _pct(v: Optional[float]) -> str:
    if v is None or v != v:
        return "—"
    return f"{v*100:+.2f}%"


def _val(v: Optional[float], unit: str) -> str:
    if v is None or v != v:
        return "—"
    if unit == "%":
        return f"{v*100:.2f}%"
    if unit == "x":
        return f"{v:.2f}x"
    return f"{v:.2f}"


def to_markdown(rep: SnapshotReport) -> str:
    """Render `rep` as a clean, self-contained Markdown document."""
    lines: list[str] = []

    # Header
    lines.append(f"# {rep.ticker} — {rep.company_name}")
    if rep.sector or rep.industry:
        meta_bits = [b for b in (rep.sector, rep.industry) if b]
        lines.append(f"_{' · '.join(meta_bits)}_")
    lines.append("")
    lines.append(f"**Generated:** {rep.timestamp:%Y-%m-%d %H:%M}  ")
    if rep.current_price is not None:
        lines.append(f"**Current price:** {_money(rep.current_price)}  ")
    if rep.market_cap:
        lines.append(f"**Market cap:** {_money(rep.market_cap)}  ")
    if rep.week_52_low is not None and rep.week_52_high is not None:
        lines.append(f"**52-week range:** {_money(rep.week_52_low)} – {_money(rep.week_52_high)}  ")
    lines.append("")

    # Final verdict
    rec = rep.final_verdict
    if rec:
        lines.append("## 🎯 Final verdict")
        lines.append("")
        lines.append(f"**{rec.action}** — composite {rec.composite_score:.0f}/100, confidence {rec.confidence_pct:.0f}%")
        lines.append("")
        if rec.price_target_mid is not None:
            tlow = _money(rec.price_target_low)
            tmid = _money(rec.price_target_mid)
            thi = _money(rec.price_target_high)
            up = _pct(rec.upside_pct) if rec.upside_pct is not None else "—"
            lines.append(f"- **Price target (12M mid):** {tmid} ({up} upside)")
            lines.append(f"- **Target range:** {tlow} – {thi}")
        lines.append(f"- **Hold period:** {rec.hold_period_label} ({rec.hold_period_months_min}–{rec.hold_period_months_max} months)")
        lines.append(f"- **Suggested position size:** {rec.position_size_pct:.1f}% of portfolio")
        lines.append(f"- **Risk grade:** {rec.risk_grade}")
        lines.append("")
        lines.append("**Rationale**")
        lines.append("")
        lines.append(rec.rationale)
        lines.append("")
        if rec.key_catalysts:
            lines.append("**Key catalysts**")
            for c in rec.key_catalysts:
                lines.append(f"- {c}")
            lines.append("")
        if rec.key_risks:
            lines.append("**Key risks**")
            for r in rec.key_risks:
                lines.append(f"- {r}")
            lines.append("")

    # Price snapshot vs S&P
    if rep.price_returns:
        lines.append("## 📈 Price performance vs S&P 500")
        lines.append("")
        lines.append("| Period | Ticker | S&P 500 | Relative |")
        lines.append("|---|---|---|---|")
        for pr in rep.price_returns:
            rel = pr.relative
            lines.append(
                f"| {pr.label} | {_pct(pr.ticker_return)} | {_pct(pr.spx_return)} | {_pct(rel) if rel is not None else '—'} |"
            )
        lines.append("")

    # Fundamentals
    if rep.fundamental_metrics:
        lines.append("## 📊 Fundamental snapshot — 10 metrics")
        lines.append("")
        lines.append("| Metric | Value | Verdict | Rationale |")
        lines.append("|---|---|---|---|")
        for m in rep.fundamental_metrics:
            lines.append(f"| {m.name} | {_val(m.value, m.unit)} | **{m.verdict}** | {m.rationale} |")
        lines.append("")
        lines.append(f"**Fundamental verdict:** {rep.fundamental_verdict} (confidence {rep.fundamental_confidence*100:.0f}%)")
        lines.append("")

    # Technicals
    if rep.technical_indicators:
        lines.append("## ⏳ Technical snapshot — 6 indicators")
        lines.append("")
        lines.append("| Indicator | State | Signal | Rationale |")
        lines.append("|---|---|---|---|")
        for i in rep.technical_indicators:
            lines.append(f"| {i.name} | {i.state} | **{i.signal}** | {i.rationale} |")
        lines.append("")
        lines.append(f"**Technical verdict:** {rep.technical_verdict} (confidence {rep.technical_confidence*100:.0f}%)")
        lines.append("")

    # Analyst panel
    a = rep.analyst
    if a:
        lines.append("## 🎓 Analyst consensus")
        lines.append("")
        if a.total_analysts:
            lines.append(f"- **Total analysts:** {a.total_analysts}")
        if a.consensus_label:
            lines.append(f"- **Consensus:** {a.consensus_label}")
        if a.pct_strong_buy is not None:
            lines.append(
                f"- **Distribution:** Strong Buy {a.pct_strong_buy*100:.0f}% · "
                f"Buy {(a.pct_buy or 0)*100:.0f}% · "
                f"Hold {(a.pct_hold or 0)*100:.0f}% · "
                f"Sell {(a.pct_sell or 0)*100:.0f}% · "
                f"Strong Sell {(a.pct_strong_sell or 0)*100:.0f}%"
            )
        if a.mean_target:
            lines.append(
                f"- **Targets:** mean {_money(a.mean_target)} · "
                f"median {_money(a.median_target)} · "
                f"high {_money(a.high_target)} · "
                f"low {_money(a.low_target)}"
            )
        if a.upside_pct is not None:
            lines.append(f"- **Upside vs current:** {a.upside_pct*100:+.1f}%")
        if a.recent_actions_note:
            lines.append(f"- **Recent action:** {a.recent_actions_note}")
        lines.append("")
        lines.append(f"**Analyst verdict:** {rep.analyst_verdict_label}")
        lines.append("")

    # Multi-horizon price targets
    pts = rep.price_target_set
    if pts and pts.targets:
        lines.append("## 🎯 Multi-horizon price targets")
        lines.append("")
        if pts.annualized_volatility is not None:
            lines.append(f"_Annualised volatility: {pts.annualized_volatility*100:.1f}%_")
            lines.append("")
        lines.append("| Horizon | Technical | Fundamental | Analyst | Combined | Bear | Bull | Upside | Confidence |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for t in pts.targets:
            lines.append(
                f"| {t.label} | {_money(t.technical_target)} | {_money(t.fundamental_target)} | "
                f"{_money(t.analyst_target)} | **{_money(t.combined_target)}** | "
                f"{_money(t.bear_case)} | {_money(t.bull_case)} | "
                f"{_pct(t.upside_pct) if t.upside_pct is not None else '—'} | "
                f"{t.confidence:.0f}% |"
            )
        lines.append("")

    # Backtest
    bt = rep.backtest
    if bt and bt.points:
        lines.append("## ⏪ Track record (technical backtest)")
        lines.append("")
        hr = bt.hit_rate
        if hr is not None:
            lines.append(f"**Hit rate:** {hr*100:.0f}% across {len(bt.points)} historical signals ({bt.hit_count} hits, {bt.miss_count} misses)")
        if bt.avg_alpha is not None:
            lines.append(f"**Avg alpha on BUY calls:** {bt.avg_alpha*100:+.1f}% vs S&P 500")
        lines.append("")
        lines.append("| As of | Verdict | Price then | Price now | Realized | Alpha | Hit? |")
        lines.append("|---|---|---|---|---|---|---|")
        for p in bt.points:
            hit_icon = "✓" if p.correct is True else ("✗" if p.correct is False else "—")
            lines.append(
                f"| {p.label} ({p.as_of_date}) | **{p.technical_verdict}** | "
                f"{_money(p.price_then)} | {_money(p.price_now)} | "
                f"{_pct(p.realized_return)} | "
                f"{_pct(p.alpha) if p.alpha is not None else '—'} | {hit_icon} |"
            )
        lines.append("")

    # AI investor council
    agents = rep.agents
    if agents and not getattr(agents, "error", None) and getattr(agents, "agent_signals", None):
        lines.append("## 🤖 AI Investor Council")
        lines.append("")
        lines.append(
            f"{agents.total_analysts} analysts: "
            f"{agents.bullish_count} bullish · {agents.neutral_count} neutral · "
            f"{agents.bearish_count} bearish · {agents.agreement_pct*100:.0f}% agreement"
        )
        lines.append("")
        lines.append("| Analyst | Signal | Confidence | Reasoning |")
        lines.append("|---|---|---|---|")
        for s in agents.agent_signals:
            sig_label = {"bullish": "BUY", "bearish": "SELL", "neutral": "HOLD"}.get(s.signal, "HOLD")
            reasoning = (s.reasoning or "—").replace("|", "\\|").replace("\n", " ")
            if len(reasoning) > 300:
                reasoning = reasoning[:297] + "…"
            lines.append(f"| **{s.agent_name}** | {sig_label} | {s.confidence:.0f}% | {reasoning} |")
        lines.append("")

        pm = agents.pm_decision
        if pm:
            lines.append("### Portfolio Manager")
            lines.append("")
            lines.append(f"**Action:** {pm.action.upper()} · **Quantity:** {pm.quantity:,} · **Confidence:** {pm.confidence:.0f}%")
            lines.append("")
            pm_reasoning = (pm.reasoning or "").replace("\n", "\n> ")
            if pm_reasoning:
                lines.append(f"> {pm_reasoning}")
                lines.append("")

    # Synthesis
    if rep.synthesis:
        lines.append("## 💡 Synthesis")
        lines.append("")
        lines.append(rep.synthesis)
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(
        f"_Generated by Strategist on {datetime.now():%Y-%m-%d %H:%M}. "
        f"Data via yfinance + Financial Datasets API. "
        f"Educational/research use only — not investment advice._"
    )
    if rep.data_warnings:
        lines.append("")
        lines.append("**Data warnings**")
        for w in rep.data_warnings:
            lines.append(f"- {w}")

    return "\n".join(lines) + "\n"
