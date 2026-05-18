"""Ticker snapshot reporting layer.

Produces a `SnapshotReport` for any ticker with:
- Price performance snapshot (1D / 1W / 1M / 6M / 1Y / 3Y vs S&P 500)
- 10 fundamental metrics, each with a verdict
- 6 technical indicators, each with a BUY/HOLD/SELL signal
- Analyst consensus panel with % breakdown and price targets
- Aggregate Fundamental / Technical / Analyst verdicts
- Composite overall verdict (0-100 score)

Public entry points:
    from src.analysis import generate_snapshot, render_console, render_html
"""

from src.analysis.snapshot import generate_snapshot, SnapshotReport
from src.analysis.renderers import render_console, render_html

__all__ = ["generate_snapshot", "SnapshotReport", "render_console", "render_html"]
