"""Presentation constants and renderables shared by the app and the CLI.

Textual-free by design: the interactive app (hedge_fund/tui/app.py) and the
non-interactive CLI (hedge_fund/run.py) both import from here, and the CLI must not
pay to import Textual. Everything here is plain data, small pure helpers, or
rich renderables (which Textual Statics render natively).
"""

from __future__ import annotations

import json
from datetime import date as _date
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version
from pathlib import Path

from rich.text import Text

from hedge_fund.fund import FundSpec, StrategySpec
from hedge_fund.llm import is_supported, load_api_models  # noqa: F401  (re-export)
from hedge_fund.paths import MANDATES_DIR, ensure_mandates_dir  # noqa: F401  (re-export)
from hedge_fund.signals import ALPHA_MODEL_REGISTRY, LLMAgent

try:
    VERSION = _version("aihf")
except PackageNotFoundError:  # running from source without an install
    VERSION = "dev"

# Strategy libraries live in hedge_fund/strategies/ (code, inside the package).
# Mandates the app writes are user data and live in ~/.hedge-fund/ (see paths.py).
STRATEGY_DIR = Path(__file__).resolve().parent.parent / "strategies"
FUNDS_DIR = MANDATES_DIR

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
# reads HEDGE_FUND_LLM_MODEL (hedge_fund/llm/client.py) and routes to the right provider, so
# setting that env var steers every agent instance — the warm roster AND the
# Fund — with no threading. Quant models (PEAD) carry no LLM and ignore it.
_DEFAULT_MODEL_LABEL = "Opus 5"

# The registry lives in hedge_fund/llm — it is a fact about providers, not about
# presentation. Re-exported here so screens keep importing from one place.


DEFAULT_RISK = {"max_position_pct": 0.25, "max_gross_exposure": 1.0}
DEFAULT_CAPITAL = 100_000.0
_BACKTEST_WEEKS = 78  # ~18 months of history for the default backtest window
_CYCLE_DWELL = 0.08   # min seconds per backtest tick, so the curve draws visibly
_BOARD_REFRESH = 1 / 12  # seconds between run-board repaints — smooth, not frantic
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


_BLOCKS = " ▁▂▃▄▅▆▇█"


def _render_area_chart(
    fund: list[float],
    benchmark: list[float],
    baseline: float,
    width: int,
) -> list[Text]:
    """Filled-area equity curve: the fund as a solid mass of eighth-blocks —
    green above its starting capital, red below — with the benchmark threaded
    through it as a cyan polyline. The fill is the fund's P&L made physical;
    the line is the market it has to beat.
    """
    lo = min(min(fund), min(benchmark), baseline)
    hi = max(max(fund), max(benchmark), baseline)
    # Drop the floor a touch below the true low: the worst column still draws
    # a sliver of fill instead of vanishing into a hole in the mass.
    lo -= ((hi - lo) or 1.0) * 0.06
    span = (hi - lo) or 1.0

    labels = {
        _CHART_HEIGHT - 1: _money(hi),
        _CHART_HEIGHT // 2: _money(lo + span * (_CHART_HEIGHT // 2) / (_CHART_HEIGHT - 1)),
        0: _money(lo),
    }
    gutter = max(len(label) for label in labels.values())
    plot_width = max(20, width - gutter - 1)

    def resample(values: list[float]) -> list[float]:
        """Linear interpolation, not nearest-neighbor: a handful of rebalance
        cycles stretched over the full width should read as slopes, not slabs."""
        if len(values) == 1:
            return values * plot_width
        step = (len(values) - 1) / (plot_width - 1)
        out = []
        for i in range(plot_width):
            pos = i * step
            j = int(pos)
            k = min(j + 1, len(values) - 1)
            frac = pos - j
            out.append(values[j] * (1 - frac) + values[k] * frac)
        return out

    # The fund, as filled columns measured in 1/8 blocks from the floor.
    cols = resample(fund)
    eighths = [(v - lo) / span * _CHART_HEIGHT * 8 for v in cols]
    grid = [[(" ", "") for _ in range(plot_width)] for _ in range(_CHART_HEIGHT)]
    for x, (v, lvl) in enumerate(zip(cols, eighths)):
        style = "green" if v >= baseline else "red"
        for row in range(_CHART_HEIGHT):  # row 0 is the top
            filled = max(0, min(8, round(lvl - (_CHART_HEIGHT - 1 - row) * 8)))
            if filled:
                grid[row][x] = (_BLOCKS[filled], style)

    # The benchmark, as a polyline punched through the fill.
    bench = resample(benchmark)
    level = [round((v - lo) / span * (_CHART_HEIGHT - 1)) for v in bench]
    for x in range(plot_width - 1):
        y0, y1 = level[x], level[x + 1]
        if y0 == y1:
            grid[_CHART_HEIGHT - 1 - y0][x] = ("─", "cyan")
        else:
            grid[_CHART_HEIGHT - 1 - y0][x] = ("╯" if y1 > y0 else "╮", "cyan")
            grid[_CHART_HEIGHT - 1 - y1][x] = ("╭" if y1 > y0 else "╰", "cyan")
            for y in range(min(y0, y1) + 1, max(y0, y1)):
                grid[_CHART_HEIGHT - 1 - y][x] = ("│", "cyan")
    grid[_CHART_HEIGHT - 1 - level[-1]][-1] = ("─", "cyan")

    rows: list[Text] = []
    for row in range(_CHART_HEIGHT):
        lvl = _CHART_HEIGHT - 1 - row
        line = Text()
        if lvl in labels:
            line.append(f"{labels[lvl]:>{gutter}}┤", style="dim")
        else:
            line.append(f"{'':>{gutter}}│", style="dim")
        for char, style in grid[row]:
            line.append(char, style=style)
        rows.append(line)
    return rows
