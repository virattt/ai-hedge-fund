"""Small Textual pieces that more than one screen composes."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import OptionList, Static

from hedge_fund.tui.palette import BRIGHT, GREEN, MUTED, RED


class StatTiles(Horizontal):
    """One row of six tallies — portfolio value, return, benchmark, excess
    return, Sharpe, max drawdown — shared by the backtest board and the paper
    fund's history. Styled by `#stats` and `#stats > Static` in app.tcss."""

    def compose(self) -> ComposeResult:
        for name in ("nav", "return", "bench", "excess", "sharpe", "dd"):
            yield Static("", id=f"stat-{name}")

    def update(self, benchmark: str, nav: float, fund_return: float,
               benchmark_return: float, excess: float, sharpe: float, max_dd: float) -> None:
        def tile(label: str, value: str, style: str) -> Text:
            return Text.assemble((f"{label}\n", MUTED), (value, f"bold {style}"), justify="center")

        self.query_one("#stat-nav", Static).update(tile("PORTFOLIO", f"${nav:,.0f}", BRIGHT))
        self.query_one("#stat-return", Static).update(
            tile("RETURN", f"{fund_return:+.2%}", GREEN if fund_return >= 0 else RED))
        self.query_one("#stat-bench", Static).update(
            tile(benchmark, f"{benchmark_return:+.2%}", GREEN if benchmark_return >= 0 else RED))
        self.query_one("#stat-excess", Static).update(
            tile("EXCESS", f"{excess:+.2%}", GREEN if excess >= 0 else RED))
        self.query_one("#stat-sharpe", Static).update(
            tile("SHARPE", f"{sharpe:.2f}", GREEN if sharpe > 1 else "yellow" if sharpe > 0 else RED))
        self.query_one("#stat-dd", Static).update(tile("MAX DRAWDOWN", f"{max_dd:.2%}", RED))


def first_selectable(nav: OptionList) -> int | None:
    for i in range(nav.option_count):
        if not nav.get_option_at_index(i).disabled:
            return i
    return None
