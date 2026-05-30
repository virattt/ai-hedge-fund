"""Lightweight signals dashboard.

Runs the hedge fund once and renders a self-contained HTML page showing every
agent's signal (bullish/bearish/neutral) and confidence per ticker, plus the
final trading decision. No extra dependencies, no Node.js.

Usage:
    poetry run python src/dashboard.py --tickers AAPL,MSFT,NVDA --analysts macro --model claude-haiku-4-5-20251001
"""

import html
import webbrowser
from datetime import datetime
from pathlib import Path

from src.cli.input import parse_cli_inputs
from src.main import run_hedge_fund
from src.utils.analysts import ANALYST_CONFIG

SIGNAL_COLORS = {"bullish": "#16a34a", "bearish": "#dc2626", "neutral": "#6b7280"}
ACTION_COLORS = {
    "buy": "#16a34a",
    "sell": "#dc2626",
    "short": "#b91c1c",
    "cover": "#2563eb",
    "hold": "#6b7280",
}


def _agent_display_map() -> dict[str, str]:
    """Map graph node id (e.g. 'macro_agent') -> display name (e.g. 'Macro Agent')."""
    return {f"{key}_agent": cfg["display_name"] for key, cfg in ANALYST_CONFIG.items()}


def _badge(text: str, color: str) -> str:
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:12px;'
        f'background:{color};color:#fff;font-weight:600;font-size:12px;">{html.escape(text)}</span>'
    )


def _confidence_bar(conf: float) -> str:
    pct = max(0.0, min(100.0, float(conf)))
    return (
        f'<div style="background:#e5e7eb;border-radius:6px;width:120px;height:14px;display:inline-block;'
        f'vertical-align:middle;overflow:hidden;">'
        f'<div style="background:#3b82f6;height:100%;width:{pct:.0f}%;"></div></div>'
        f'<span style="margin-left:6px;font-size:12px;color:#374151;">{pct:.0f}%</span>'
    )


def build_html(result: dict, tickers: list[str], model_name: str, start_date: str, end_date: str) -> str:
    decisions = result.get("decisions") or {}
    analyst_signals = result.get("analyst_signals") or {}
    name_map = _agent_display_map()
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sections = []
    for ticker in tickers:
        # Collect per-agent signals for this ticker (skip non-signal agents like risk manager)
        rows = []
        counts = {"bullish": 0, "bearish": 0, "neutral": 0}
        for agent_id, by_ticker in analyst_signals.items():
            entry = by_ticker.get(ticker) if isinstance(by_ticker, dict) else None
            if not isinstance(entry, dict) or "signal" not in entry:
                continue
            signal = str(entry.get("signal", "neutral")).lower()
            conf = entry.get("confidence", 0) or 0
            reasoning = str(entry.get("reasoning", ""))
            counts[signal] = counts.get(signal, 0) + 1
            display = name_map.get(agent_id, agent_id)
            rows.append(
                "<tr>"
                f'<td style="padding:6px 10px;border-bottom:1px solid #f0f0f0;">{html.escape(display)}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #f0f0f0;">{_badge(signal.upper(), SIGNAL_COLORS.get(signal, "#6b7280"))}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #f0f0f0;">{_confidence_bar(conf)}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #f0f0f0;color:#4b5563;font-size:13px;">{html.escape(reasoning[:280])}</td>'
                "</tr>"
            )

        # Final decision panel
        decision = decisions.get(ticker, {}) if isinstance(decisions, dict) else {}
        action = str(decision.get("action", "hold")).lower()
        qty = decision.get("quantity", 0)
        dconf = decision.get("confidence", 0) or 0
        dreason = str(decision.get("reasoning", ""))

        summary = (
            f'<span style="margin-right:14px;">{_badge("BULLISH " + str(counts["bullish"]), SIGNAL_COLORS["bullish"])}</span>'
            f'<span style="margin-right:14px;">{_badge("BEARISH " + str(counts["bearish"]), SIGNAL_COLORS["bearish"])}</span>'
            f'<span>{_badge("NEUTRAL " + str(counts["neutral"]), SIGNAL_COLORS["neutral"])}</span>'
        )

        decision_panel = (
            f'<div style="margin:10px 0 14px 0;padding:12px 16px;border-radius:8px;background:#f9fafb;border:1px solid #e5e7eb;">'
            f'<span style="font-weight:700;margin-right:12px;">DECISION:</span>'
            f'{_badge(action.upper(), ACTION_COLORS.get(action, "#6b7280"))}'
            f'<span style="margin:0 14px;color:#111;">Qty: <b>{html.escape(str(qty))}</b></span>'
            f'<span style="color:#111;">Confidence: <b>{float(dconf):.0f}%</b></span>'
            f'<div style="margin-top:8px;color:#4b5563;font-size:13px;">{html.escape(dreason[:400])}</div>'
            f"</div>"
        )

        if rows:
            table = (
                '<table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;">'
                '<thead><tr style="text-align:left;color:#6b7280;font-size:12px;">'
                '<th style="padding:6px 10px;">Agent</th><th style="padding:6px 10px;">Signal</th>'
                '<th style="padding:6px 10px;">Confidence</th><th style="padding:6px 10px;">Reasoning</th>'
                "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
            )
        else:
            table = '<p style="color:#9ca3af;">No agent signals for this ticker.</p>'

        sections.append(
            f'<section style="margin-bottom:32px;">'
            f'<h2 style="font-family:Arial,sans-serif;margin-bottom:4px;">{html.escape(ticker)}</h2>'
            f'<div style="margin-bottom:8px;">{summary}</div>'
            f"{decision_panel}{table}</section>"
        )

    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>AI Hedge Fund — Signals Dashboard</title></head>"
        '<body style="max-width:1000px;margin:24px auto;padding:0 16px;font-family:Arial,sans-serif;color:#111;">'
        '<h1 style="margin-bottom:2px;">AI Hedge Fund — Signals Dashboard</h1>'
        f'<p style="color:#6b7280;margin-top:0;">Tickers: {html.escape(", ".join(tickers))} &nbsp;|&nbsp; '
        f"Model: {html.escape(model_name)} &nbsp;|&nbsp; Window: {html.escape(start_date)} → {html.escape(end_date)} "
        f"&nbsp;|&nbsp; Generated: {generated}</p><hr style='border:none;border-top:1px solid #e5e7eb;'>"
        + "".join(sections)
        + "</body></html>"
    )


def main() -> None:
    inputs = parse_cli_inputs(
        description="Render a signals dashboard for the hedge fund",
        require_tickers=True,
        default_months_back=None,
        include_graph_flag=False,
        include_reasoning_flag=False,
    )

    portfolio = {
        "cash": inputs.initial_cash,
        "margin_requirement": inputs.margin_requirement,
        "margin_used": 0.0,
        "positions": {
            t: {"long": 0, "short": 0, "long_cost_basis": 0.0, "short_cost_basis": 0.0, "short_margin_used": 0.0}
            for t in inputs.tickers
        },
        "realized_gains": {t: {"long": 0.0, "short": 0.0} for t in inputs.tickers},
    }

    result = run_hedge_fund(
        tickers=inputs.tickers,
        start_date=inputs.start_date,
        end_date=inputs.end_date,
        portfolio=portfolio,
        show_reasoning=False,
        selected_analysts=inputs.selected_analysts,
        model_name=inputs.model_name,
        model_provider=inputs.model_provider,
    )

    page = build_html(result, inputs.tickers, inputs.model_name, inputs.start_date, inputs.end_date)
    out_path = Path("dashboard.html").resolve()
    out_path.write_text(page, encoding="utf-8")
    print(f"\nDashboard written to: {out_path}")
    try:
        webbrowser.open(out_path.as_uri())
    except Exception:
        pass


if __name__ == "__main__":
    main()
