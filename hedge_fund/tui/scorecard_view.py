"""Rich tables for the scorecard: one for the analysts, one for the sleeves.

Textual-free, like report.py: the backtest board, the paper sessions
screen and the CLI all print the same two tables. Every rate is shown next
to its count, so a hit rate from twelve calls reads as the noise it is.
"""

from __future__ import annotations

from rich import box
from rich.table import Table
from rich.text import Text

from hedge_fund.scorecard import Scorecard
from hedge_fund.tui.palette import BRIGHT, GREEN, MUTED, RED, TEXT
from hedge_fund.tui.shared import SHORT_NAMES

_NONE = Text("–", style=MUTED)


def analyst_table(card: Scorecard) -> Table:
    """Hit rate and slugging on benchmark-relative returns; IC as a per-date
    series. Views are judged to the next decision: one cadence period."""
    judged = f"judged over one {card.horizon} period" if card.horizon else "no decisions yet"
    table = _table(f"ANALYSTS  ·  {judged}")
    table.add_column("analyst", style=f"bold {TEXT}")
    table.add_column("views", justify="right")
    table.add_column("abstained", justify="right")
    table.add_column("hit rate", justify="right")
    table.add_column("slugging", justify="right")
    table.add_column("IC", justify="right")
    table.add_column("IC t", justify="right")
    table.add_column("dates", justify="right")
    if not card.analysts:
        table.caption = "nothing to grade yet: a view is scored once the next decision is made"
        table.caption_style = MUTED
        table.caption_justify = "left"
        return table
    for a in card.analysts:
        table.add_row(
            SHORT_NAMES.get(a.name, a.name),
            str(a.n_views),
            Text(str(a.n_abstained), style=MUTED if a.n_abstained == 0 else TEXT),
            _rate(a.hit_rate, a.n_directional),
            _NONE if a.slugging is None else Text(f"{a.slugging:.2f}×", style=TEXT),
            _NONE if a.ic_mean is None else Text(f"{a.ic_mean:+.3f}", style=_signed(a.ic_mean)),
            _NONE if a.ic_t_stat is None else Text(f"{a.ic_t_stat:+.1f}", style=_significance(a.ic_t_stat)),
            str(a.n_dates),
        )
    return table


def strategy_table(card: Scorecard) -> Table:
    """Each sleeve's P&L between executions, and the part no sleeve explains."""
    table = _table("STRATEGIES  ·  P&L between executions")
    table.add_column("strategy", style=f"bold {TEXT}")
    table.add_column("periods", justify="right")
    table.add_column("P&L", justify="right")
    table.add_column("return", justify="right")
    table.add_column("win rate", justify="right")
    table.add_column("max DD", justify="right")
    table.add_column("share", justify="right")
    if not card.strategies:
        table.caption = "nothing to attribute yet: a sleeve is scored between two executions"
        table.caption_style = MUTED
        table.caption_justify = "left"
        return table
    for s in card.strategies:
        table.add_row(
            s.name,
            str(s.n_periods),
            Text(f"{s.pnl:+,.0f}", style=_signed(s.pnl)),
            Text(f"{s.return_pct:+.2%}", style=_signed(s.return_pct)),
            _rate(s.win_rate, s.n_periods),
            Text(f"{s.max_drawdown_pct:.1%}", style=RED if s.max_drawdown_pct > 0 else MUTED),
            _NONE if s.share_of_pnl is None else Text(f"{s.share_of_pnl:+.0%}", style=TEXT),
        )
    table.caption = (f"fund P&L {card.fund_pnl:+,.0f}  ·  unattributed {card.unattributed:+,.0f}  ·  "
                     f"of which trading costs {-card.trading_cost:+,.0f}")
    table.caption_style = MUTED
    table.caption_justify = "left"
    return table


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _table(title: str) -> Table:
    return Table(box=box.SQUARE, header_style="bold", border_style="#1f2b25",
                 title=Text(title, style=f"bold {BRIGHT}"), title_justify="left")


def _rate(value: float | None, n: int) -> Text:
    if value is None:
        return _NONE
    return Text.assemble((f"{value:.0%}", _signed(value - 0.5)), (f" of {n}", MUTED))


def _signed(value: float) -> str:
    if value > 0:
        return GREEN
    if value < 0:
        return RED
    return MUTED


def _significance(t_stat: float) -> str:
    """Two standard errors either way is the usual bar for 'not noise'."""
    if t_stat >= 2:
        return GREEN
    if t_stat <= -2:
        return RED
    return MUTED
