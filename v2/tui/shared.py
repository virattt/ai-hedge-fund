"""Presentation constants and renderables shared by the app and the CLI.

Textual-free by design: the interactive app (v2/tui/app.py) and the
non-interactive CLI (v2/run.py) both import from here, and the CLI must not
pay to import Textual. Everything here is plain data, small pure helpers, or
rich renderables (which Textual Statics render natively).
"""

from __future__ import annotations

import json
from datetime import date as _date
from pathlib import Path

from rich.text import Text

from v2.fund import FundSpec, StrategySpec
from v2.llm import is_supported, load_api_models  # noqa: F401  (re-export)
from v2.signals import ALPHA_MODEL_REGISTRY, LLMAgent

VERSION = "2.0.0"  # keep in sync with pyproject.toml

# Strategy libraries live in v2/strategies/; funds the app writes live in
# v2/funds/. This module is v2/tui/shared.py, so the package root is two up.
STRATEGY_DIR = Path(__file__).resolve().parent.parent / "strategies"
FUNDS_DIR = Path(__file__).resolve().parent.parent / "funds"

UNIVERSE_PRESETS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
                    "META", "TSLA", "JPM", "UNH", "XOM"]

DISPLAY_NAMES = {
    "buffett": "Warren Buffett",
    "munger": "Charlie Munger",
    "graham": "Benjamin Graham",
    "lynch": "Peter Lynch",
    "druckenmiller": "Stanley Druckenmiller",
    "pead": "post-earnings drift",
}

_SHORT_NAMES = {
    "buffett": "Buffett",
    "munger": "Munger",
    "graham": "Graham",
    "lynch": "Lynch",
    "druckenmiller": "Druckenmiller",
    "pead": "PEAD",
}

# The LLM the investor agents reason with. Picked once, upfront; make_llm()
# reads V2_LLM_MODEL (v2/llm/client.py) and routes to the right provider, so
# setting that env var steers every agent instance — the warm roster AND the
# Fund — with no threading. Quant models (PEAD) carry no LLM and ignore it.
_DEFAULT_MODEL_LABEL = "Opus 5"

# The registry lives in v2/llm — it is a fact about providers, not about
# presentation. Re-exported here so screens keep importing from one place.


DEFAULT_RISK = {"max_position_pct": 0.25, "max_gross_exposure": 1.0}
DEFAULT_CAPITAL = 100_000.0
_BACKTEST_WEEKS = 78  # ~18 months of history for the default backtest window
_CYCLE_DWELL = 0.08   # min seconds per backtest tick, so the curve draws visibly
_WARM_CHUNK = 10      # dates per warm task — small enough that one stock still fans out

_CHART_HEIGHT = 8


def _valid_date(text: str):
    try:
        _date.fromisoformat(text.strip())
        return True
    except ValueError:
        return "Use YYYY-MM-DD."


def _fund_label(spec: FundSpec) -> str:
    """One aligned line per fund: name, staff, cadence."""
    staff = ", ".join(s.title for s in spec.strategies[:3])
    if len(spec.strategies) > 3:
        staff += ", …"
    return f"{spec.name:<18} {staff} · {spec.rebalance}"


def _agent_names(spec: FundSpec) -> list[str]:
    """Unique model names across strategies, in first-appearance order."""
    names: list[str] = []
    for strategy in spec.strategies:
        for m in strategy.models:
            if m.name not in names:
                names.append(m.name)
    return names


def _strategy_kind(strategy: StrategySpec) -> str:
    """Discretionary pods are staffed entirely by LLM agents; anything with a
    quant model in the mix is systematic. Derived, never declared."""
    if all(issubclass(ALPHA_MODEL_REGISTRY[m.name], LLMAgent)
           for m in strategy.models):
        return "discretionary"
    return "systematic"


def _money(value: float) -> str:
    if abs(value) >= 10_000:
        return f"${value / 1000:,.0f}k"
    return f"${value:,.0f}"


def _render_chart(
    fund: list[float],
    benchmark: list[float],
    baseline: float,
    width: int,
) -> list[Text]:
    """Two-series unicode line chart, tearsheet-style: the fund against its
    benchmark on one set of axes, dollar labels in a left gutter. Lines are
    box-drawing polylines (asciichart-style), not filled areas — the gap
    between the two lines is the point. The fund draws last, so where the
    lines collide the fund wins the cell.
    """
    lo = min(min(fund), min(benchmark))
    hi = max(max(fund), max(benchmark))
    span = (hi - lo) or 1.0

    labels = {
        _CHART_HEIGHT - 1: _money(hi),
        _CHART_HEIGHT // 2: _money(lo + span * (_CHART_HEIGHT // 2) / (_CHART_HEIGHT - 1)),
        0: _money(lo),
    }
    gutter = max(len(label) for label in labels.values())
    plot_width = max(20, width - gutter - 1)

    def resample(values: list[float]) -> list[float]:
        if len(values) == 1:
            return values * plot_width
        step = (len(values) - 1) / (plot_width - 1)
        return [values[round(i * step)] for i in range(plot_width)]

    # grid[row][col] = (char, style); row 0 is the top
    grid = [[(" ", "") for _ in range(plot_width)] for _ in range(_CHART_HEIGHT)]

    def draw(values: list[float], style_of) -> None:
        cols = resample(values)
        level = [round((v - lo) / span * (_CHART_HEIGHT - 1)) for v in cols]
        for x in range(plot_width - 1):
            y0, y1 = level[x], level[x + 1]
            if y0 == y1:
                grid[_CHART_HEIGHT - 1 - y0][x] = ("─", style_of(cols[x]))
            else:
                # Rising: turn up (╯) at the low level, arrive (╭) at the high.
                # Falling: turn down (╮) at the high, arrive (╰) at the low.
                grid[_CHART_HEIGHT - 1 - y0][x] = (
                    "╯" if y1 > y0 else "╮", style_of(cols[x]))
                grid[_CHART_HEIGHT - 1 - y1][x] = (
                    "╭" if y1 > y0 else "╰", style_of(cols[x]))
                for y in range(min(y0, y1) + 1, max(y0, y1)):
                    grid[_CHART_HEIGHT - 1 - y][x] = ("│", style_of(cols[x]))
        grid[_CHART_HEIGHT - 1 - level[-1]][-1] = ("─", style_of(cols[-1]))

    draw(benchmark, lambda v: "cyan")
    draw(fund, lambda v: "bold green" if v >= baseline else "bold red")

    rows: list[Text] = []
    for row in range(_CHART_HEIGHT):
        level = _CHART_HEIGHT - 1 - row
        line = Text()
        if level in labels:
            line.append(f"{labels[level]:>{gutter}}┤", style="dim")
        else:
            line.append(f"{'':>{gutter}}│", style="dim")
        for char, style in grid[row]:
            line.append(char, style=style)
        rows.append(line)
    return rows
