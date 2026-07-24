"""Render a SnapshotReport to (a) a rich console table and (b) a single-file HTML dashboard."""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.analysis.snapshot import SnapshotReport
from src.analysis.verdicts import Verdict

_VERDICT_COLOR = {
    "STRONG BUY": "bold green",
    "BUY": "green",
    "HOLD": "yellow",
    "REDUCE": "magenta",
    "SELL": "red",
    "N/A": "dim white",
}


def _fmt_pct(x: Optional[float]) -> str:
    if x is None or x != x:
        return "—"
    return f"{x:+.2%}"


def _fmt_money(x: Optional[float]) -> str:
    if x is None or x != x:
        return "—"
    if abs(x) >= 1e12:
        return f"${x/1e12:.2f}T"
    if abs(x) >= 1e9:
        return f"${x/1e9:.2f}B"
    if abs(x) >= 1e6:
        return f"${x/1e6:.2f}M"
    return f"${x:,.2f}"


def render_console(report: SnapshotReport, console: Optional[Console] = None) -> None:
    """Pretty-print a SnapshotReport to the terminal."""
    if console is None:
        console = Console()

    header_text = Text()
    header_text.append(f" {report.ticker} ", style="bold white on blue")
    header_text.append(f"  {report.company_name}", style="bold")
    if report.sector:
        header_text.append(f"  ·  {report.sector}", style="dim")
    if report.current_price is not None:
        header_text.append(f"   {_fmt_money(report.current_price)}", style="bold cyan")

    verdict_color = _VERDICT_COLOR.get(report.overall_verdict_label, "white")
    verdict_text = Text()
    verdict_text.append("OVERALL: ", style="bold")
    verdict_text.append(report.overall_verdict_label, style=f"bold {verdict_color}")
    verdict_text.append(
        f"  ·  Score {report.composite_score:.0f}/100  ·  Confidence {report.composite_confidence:.0%}",
        style="bold",
    )

    console.print()
    console.print(Panel(header_text, title="[bold]Ticker Snapshot[/bold]", expand=False))
    console.print(Panel(verdict_text, expand=False, border_style=verdict_color))

    # Sub-verdicts table
    sub = Table(title="Component Verdicts", header_style="bold", show_lines=False, expand=False)
    sub.add_column("Component")
    sub.add_column("Verdict")
    sub.add_column("Confidence")
    sub.add_row(
        "Fundamental (40%)",
        Text(report.fundamental_verdict, style=_VERDICT_COLOR.get(report.fundamental_verdict, "white")),
        f"{report.fundamental_confidence:.0%}",
    )
    sub.add_row(
        "Technical (30%)",
        Text(report.technical_verdict, style=_VERDICT_COLOR.get(report.technical_verdict, "white")),
        f"{report.technical_confidence:.0%}",
    )
    sub.add_row(
        "Analyst (15%)",
        Text(report.analyst_verdict_label, style=_VERDICT_COLOR.get(report.analyst_verdict_label, "white")),
        "—",
    )
    console.print(sub)

    # Price snapshot
    pt = Table(title="Price Performance vs S&P 500", header_style="bold", expand=False)
    pt.add_column("Period")
    pt.add_column(report.ticker, justify="right")
    pt.add_column("S&P 500", justify="right")
    pt.add_column("Relative", justify="right")
    for pr in report.price_returns:
        rel = pr.relative
        rel_str = _fmt_pct(rel) if rel is not None else "—"
        rel_style = "green" if rel is not None and rel > 0 else ("red" if rel is not None and rel < 0 else "dim")
        pt.add_row(
            pr.label,
            _fmt_pct(pr.ticker_return),
            _fmt_pct(pr.spx_return),
            Text(rel_str, style=rel_style),
        )
    console.print(pt)

    # Fundamentals
    ft = Table(title="Fundamental Snapshot — 10 Key Metrics", header_style="bold", expand=False)
    ft.add_column("#", width=2)
    ft.add_column("Metric")
    ft.add_column("Value", justify="right")
    ft.add_column("Verdict")
    ft.add_column("Rationale")
    for i, m in enumerate(report.fundamental_metrics, 1):
        ft.add_row(
            str(i),
            m.name,
            m.fmt_value(),
            Text(m.verdict, style=_VERDICT_COLOR.get(m.verdict, "white")),
            m.rationale,
        )
    console.print(ft)

    # Technicals
    tt = Table(title="Technical Snapshot — 6 Indicators", header_style="bold", expand=False)
    tt.add_column("#", width=2)
    tt.add_column("Indicator")
    tt.add_column("State")
    tt.add_column("Signal")
    tt.add_column("Rationale")
    for i, ind in enumerate(report.technical_indicators, 1):
        tt.add_row(
            str(i),
            ind.name,
            ind.state,
            Text(ind.signal, style=_VERDICT_COLOR.get(ind.signal, "white")),
            ind.rationale,
        )
    console.print(tt)

    # Analyst panel
    at = Table(title="Analyst Consensus", header_style="bold", expand=False)
    at.add_column("Metric")
    at.add_column("Value", justify="right")
    a = report.analyst
    rows = [
        ("Total analysts", str(a.total_analysts) if a.total_analysts else "—"),
        ("% Strong Buy", _fmt_pct(a.pct_strong_buy) if a.pct_strong_buy is not None else "—"),
        ("% Buy", _fmt_pct(a.pct_buy) if a.pct_buy is not None else "—"),
        ("% Hold", _fmt_pct(a.pct_hold) if a.pct_hold is not None else "—"),
        ("% Sell", _fmt_pct(a.pct_sell) if a.pct_sell is not None else "—"),
        ("% Strong Sell", _fmt_pct(a.pct_strong_sell) if a.pct_strong_sell is not None else "—"),
        ("Mean target", _fmt_money(a.mean_target)),
        ("Median target", _fmt_money(a.median_target)),
        ("High target", _fmt_money(a.high_target)),
        ("Low target", _fmt_money(a.low_target)),
        ("Upside vs current", _fmt_pct(a.upside_pct)),
        ("Consensus", a.consensus_label or "—"),
        ("Recent action", a.recent_actions_note or "—"),
    ]
    for k, v in rows:
        at.add_row(k, v)
    console.print(at)

    # Synthesis
    console.print(Panel(report.synthesis, title="[bold]Synthesis[/bold]", border_style=verdict_color))
    if report.data_warnings:
        console.print(Panel("\n".join(f"• {w}" for w in report.data_warnings), title="[dim]Data warnings[/dim]", border_style="dim"))


# ---- HTML ------------------------------------------------------------------


_HTML_STYLE = """
:root { --bg:#0b1220; --panel:#111a2e; --line:#22304a; --text:#e6ecf5; --dim:#9aa7be;
  --buy:#1eb980; --hold:#f5c451; --sell:#ef5350; --reduce:#b864c4; --na:#6b7280; }
* { box-sizing: border-box; }
body { background:var(--bg); color:var(--text); font-family: 'Inter', system-ui, sans-serif; margin:0; padding:24px; }
h1, h2, h3 { margin: 0 0 12px; }
.container { max-width: 1200px; margin: 0 auto; }
.header { display:flex; flex-wrap:wrap; align-items:baseline; gap:16px; margin-bottom: 16px; }
.ticker { font-size: 36px; font-weight: 700; }
.company { font-size: 18px; color: var(--dim); }
.price { margin-left:auto; font-size: 28px; font-weight: 600; color:#7dd3fc; }
.verdict-banner { padding: 20px 24px; border-radius: 12px; display:flex; gap:24px; align-items:center;
  background: var(--panel); border: 1px solid var(--line); margin-bottom:16px; }
.verdict-label { font-size: 14px; color: var(--dim); text-transform: uppercase; letter-spacing: 1px; }
.verdict-value { font-size: 26px; font-weight: 800; }
.panel { background: var(--panel); border:1px solid var(--line); border-radius: 12px; padding: 16px 20px; margin-bottom: 16px; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 800px) { .grid { grid-template-columns: 1fr; } }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--line); }
th { color: var(--dim); font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; }
.right { text-align: right; }
.badge { display:inline-block; padding:2px 10px; border-radius: 999px; font-weight: 700; font-size: 12px; }
.b-BUY { background: rgba(30,185,128,0.15); color: var(--buy); }
.b-STRONG-BUY { background: rgba(30,185,128,0.25); color: var(--buy); }
.b-HOLD { background: rgba(245,196,81,0.15); color: var(--hold); }
.b-REDUCE { background: rgba(184,100,196,0.15); color: var(--reduce); }
.b-SELL { background: rgba(239,83,80,0.15); color: var(--sell); }
.b-N\\/A { background: rgba(107,114,128,0.15); color: var(--na); }
.rel-pos { color: var(--buy); } .rel-neg { color: var(--sell); }
.synth { font-size: 15px; line-height: 1.6; color: var(--text); }
.warnings { font-size: 12px; color: var(--dim); }
.meta { color: var(--dim); font-size: 12px; }
"""


def _badge(verdict: Verdict) -> str:
    cls = "b-" + verdict.replace(" ", "-")
    return f'<span class="badge {cls}">{html.escape(verdict)}</span>'


def _fmt_pct_html(x: Optional[float]) -> str:
    if x is None or x != x:
        return "—"
    cls = "rel-pos" if x >= 0 else "rel-neg"
    return f'<span class="{cls}">{x:+.2%}</span>'


def render_html_body(report: SnapshotReport) -> str:
    """Return just the inner HTML for this report (no <html>/<head> wrapper).

    Useful when embedding multiple snapshots on a single page — the caller
    is responsible for emitting `<style>{HTML_STYLE}</style>` once.
    """
    rows_returns = "".join(
        f"<tr><td>{pr.label}</td>"
        f"<td class='right'>{_fmt_pct_html(pr.ticker_return)}</td>"
        f"<td class='right'>{_fmt_pct_html(pr.spx_return)}</td>"
        f"<td class='right'>{_fmt_pct_html(pr.relative)}</td></tr>"
        for pr in report.price_returns
    )
    rows_fund = "".join(
        f"<tr><td>{i+1}</td><td>{html.escape(m.name)}</td>"
        f"<td class='right'>{html.escape(m.fmt_value())}</td>"
        f"<td>{_badge(m.verdict)}</td>"
        f"<td>{html.escape(m.rationale)}</td></tr>"
        for i, m in enumerate(report.fundamental_metrics)
    )
    rows_tech = "".join(
        f"<tr><td>{i+1}</td><td>{html.escape(ind.name)}</td>"
        f"<td>{html.escape(ind.state)}</td>"
        f"<td>{_badge(ind.signal)}</td>"
        f"<td>{html.escape(ind.rationale)}</td></tr>"
        for i, ind in enumerate(report.technical_indicators)
    )
    a = report.analyst
    analyst_rows = [
        ("Total analysts", str(a.total_analysts) if a.total_analysts else "—"),
        ("% Strong Buy", _fmt_pct_html(a.pct_strong_buy) if a.pct_strong_buy is not None else "—"),
        ("% Buy", _fmt_pct_html(a.pct_buy) if a.pct_buy is not None else "—"),
        ("% Hold", _fmt_pct_html(a.pct_hold) if a.pct_hold is not None else "—"),
        ("% Sell", _fmt_pct_html(a.pct_sell) if a.pct_sell is not None else "—"),
        ("% Strong Sell", _fmt_pct_html(a.pct_strong_sell) if a.pct_strong_sell is not None else "—"),
        ("Mean target", _fmt_money(a.mean_target)),
        ("Median target", _fmt_money(a.median_target)),
        ("High target", _fmt_money(a.high_target)),
        ("Low target", _fmt_money(a.low_target)),
        ("Upside vs current", _fmt_pct_html(a.upside_pct)),
        ("Consensus", html.escape(a.consensus_label or "—")),
        ("Recent action", html.escape(a.recent_actions_note or "—")),
    ]
    rows_analyst = "".join(
        f"<tr><td>{html.escape(k)}</td><td class='right'>{v}</td></tr>" for k, v in analyst_rows
    )
    warnings_block = ""
    if report.data_warnings:
        items = "".join(f"<li>{html.escape(w)}</li>" for w in report.data_warnings)
        warnings_block = f'<div class="panel warnings"><h3>Data warnings</h3><ul>{items}</ul></div>'

    return f"""
<div class="report" id="report-{html.escape(report.ticker)}">
<div class="header">
  <span class="ticker">{html.escape(report.ticker)}</span>
  <span class="company">{html.escape(report.company_name)}{f' · {html.escape(report.sector)}' if report.sector else ''}</span>
  <span class="price">{_fmt_money(report.current_price)}</span>
</div>

<div class="verdict-banner">
  <div><div class="verdict-label">Overall Verdict</div><div class="verdict-value">{_badge(report.overall_verdict_label)}</div></div>
  <div><div class="verdict-label">Composite Score</div><div class="verdict-value">{report.composite_score:.0f}/100</div></div>
  <div><div class="verdict-label">Confidence</div><div class="verdict-value">{report.composite_confidence:.0%}</div></div>
  <div><div class="verdict-label">Fundamental</div><div>{_badge(report.fundamental_verdict)} <span class="meta">({report.fundamental_confidence:.0%})</span></div></div>
  <div><div class="verdict-label">Technical</div><div>{_badge(report.technical_verdict)} <span class="meta">({report.technical_confidence:.0%})</span></div></div>
  <div><div class="verdict-label">Analyst</div><div>{_badge(report.analyst_verdict_label)}</div></div>
</div>

<div class="panel">
  <h2>Synthesis</h2>
  <p class="synth">{html.escape(report.synthesis)}</p>
</div>

<div class="grid">
  <div class="panel">
    <h2>Price Performance vs S&P 500</h2>
    <table>
      <thead><tr><th>Period</th><th class="right">{html.escape(report.ticker)}</th>
        <th class="right">S&P 500</th><th class="right">Relative</th></tr></thead>
      <tbody>{rows_returns}</tbody>
    </table>
  </div>
  <div class="panel">
    <h2>Analyst Consensus</h2>
    <table>{rows_analyst}</table>
  </div>
</div>

<div class="panel">
  <h2>Fundamental Snapshot — 10 Key Metrics</h2>
  <table>
    <thead><tr><th>#</th><th>Metric</th><th class="right">Value</th><th>Verdict</th><th>Rationale</th></tr></thead>
    <tbody>{rows_fund}</tbody>
  </table>
</div>

<div class="panel">
  <h2>Technical Snapshot — 6 Indicators</h2>
  <table>
    <thead><tr><th>#</th><th>Indicator</th><th>State</th><th>Signal</th><th>Rationale</th></tr></thead>
    <tbody>{rows_tech}</tbody>
  </table>
</div>

{warnings_block}

<div class="meta">Generated {report.timestamp:%Y-%m-%d %H:%M:%S}. Educational/research use only.</div>
</div>
"""


# Expose the stylesheet so the multi-ticker page can reuse it
HTML_STYLE = _HTML_STYLE


def render_html(report: SnapshotReport, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows_returns = "".join(
        f"<tr><td>{pr.label}</td>"
        f"<td class='right'>{_fmt_pct_html(pr.ticker_return)}</td>"
        f"<td class='right'>{_fmt_pct_html(pr.spx_return)}</td>"
        f"<td class='right'>{_fmt_pct_html(pr.relative)}</td></tr>"
        for pr in report.price_returns
    )

    rows_fund = "".join(
        f"<tr><td>{i+1}</td><td>{html.escape(m.name)}</td>"
        f"<td class='right'>{html.escape(m.fmt_value())}</td>"
        f"<td>{_badge(m.verdict)}</td>"
        f"<td>{html.escape(m.rationale)}</td></tr>"
        for i, m in enumerate(report.fundamental_metrics)
    )

    rows_tech = "".join(
        f"<tr><td>{i+1}</td><td>{html.escape(ind.name)}</td>"
        f"<td>{html.escape(ind.state)}</td>"
        f"<td>{_badge(ind.signal)}</td>"
        f"<td>{html.escape(ind.rationale)}</td></tr>"
        for i, ind in enumerate(report.technical_indicators)
    )

    a = report.analyst
    analyst_rows = [
        ("Total analysts", str(a.total_analysts) if a.total_analysts else "—"),
        ("% Strong Buy", _fmt_pct_html(a.pct_strong_buy) if a.pct_strong_buy is not None else "—"),
        ("% Buy", _fmt_pct_html(a.pct_buy) if a.pct_buy is not None else "—"),
        ("% Hold", _fmt_pct_html(a.pct_hold) if a.pct_hold is not None else "—"),
        ("% Sell", _fmt_pct_html(a.pct_sell) if a.pct_sell is not None else "—"),
        ("% Strong Sell", _fmt_pct_html(a.pct_strong_sell) if a.pct_strong_sell is not None else "—"),
        ("Mean target", _fmt_money(a.mean_target)),
        ("Median target", _fmt_money(a.median_target)),
        ("High target", _fmt_money(a.high_target)),
        ("Low target", _fmt_money(a.low_target)),
        ("Upside vs current", _fmt_pct_html(a.upside_pct)),
        ("Consensus", html.escape(a.consensus_label or "—")),
        ("Recent action", html.escape(a.recent_actions_note or "—")),
    ]
    rows_analyst = "".join(
        f"<tr><td>{html.escape(k)}</td><td class='right'>{v}</td></tr>" for k, v in analyst_rows
    )

    warnings_block = ""
    if report.data_warnings:
        items = "".join(f"<li>{html.escape(w)}</li>" for w in report.data_warnings)
        warnings_block = f'<div class="panel warnings"><h3>Data warnings</h3><ul>{items}</ul></div>'

    html_str = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<title>{html.escape(report.ticker)} Snapshot — {report.timestamp:%Y-%m-%d}</title>
<style>{_HTML_STYLE}</style></head>
<body><div class="container">
<div class="header">
  <span class="ticker">{html.escape(report.ticker)}</span>
  <span class="company">{html.escape(report.company_name)}{f' · {html.escape(report.sector)}' if report.sector else ''}</span>
  <span class="price">{_fmt_money(report.current_price)}</span>
</div>

<div class="verdict-banner">
  <div><div class="verdict-label">Overall Verdict</div><div class="verdict-value">{_badge(report.overall_verdict_label)}</div></div>
  <div><div class="verdict-label">Composite Score</div><div class="verdict-value">{report.composite_score:.0f}/100</div></div>
  <div><div class="verdict-label">Confidence</div><div class="verdict-value">{report.composite_confidence:.0%}</div></div>
  <div><div class="verdict-label">Fundamental</div><div>{_badge(report.fundamental_verdict)} <span class="meta">({report.fundamental_confidence:.0%})</span></div></div>
  <div><div class="verdict-label">Technical</div><div>{_badge(report.technical_verdict)} <span class="meta">({report.technical_confidence:.0%})</span></div></div>
  <div><div class="verdict-label">Analyst</div><div>{_badge(report.analyst_verdict_label)}</div></div>
</div>

<div class="panel">
  <h2>Synthesis</h2>
  <p class="synth">{html.escape(report.synthesis)}</p>
</div>

<div class="grid">
  <div class="panel">
    <h2>Price Performance vs S&P 500</h2>
    <table>
      <thead><tr><th>Period</th><th class="right">{html.escape(report.ticker)}</th>
        <th class="right">S&P 500</th><th class="right">Relative</th></tr></thead>
      <tbody>{rows_returns}</tbody>
    </table>
  </div>
  <div class="panel">
    <h2>Analyst Consensus</h2>
    <table>{rows_analyst}</table>
  </div>
</div>

<div class="panel">
  <h2>Fundamental Snapshot — 10 Key Metrics</h2>
  <table>
    <thead><tr><th>#</th><th>Metric</th><th class="right">Value</th><th>Verdict</th><th>Rationale</th></tr></thead>
    <tbody>{rows_fund}</tbody>
  </table>
</div>

<div class="panel">
  <h2>Technical Snapshot — 6 Indicators</h2>
  <table>
    <thead><tr><th>#</th><th>Indicator</th><th>State</th><th>Signal</th><th>Rationale</th></tr></thead>
    <tbody>{rows_tech}</tbody>
  </table>
</div>

{warnings_block}

<div class="meta">Generated {report.timestamp:%Y-%m-%d %H:%M:%S}. Educational/research use only — not investment advice.</div>
</div></body></html>
"""
    out_path.write_text(html_str, encoding="utf-8")
    return out_path
