"""What the paper screens show about a deployed fund, computed from its directory.

`PaperSnapshot` reads a fund once and answers questions about it; the
functions below turn a snapshot (and, for the approval step, a ledger state)
into Rich renderables. No screens here: everything renders with Rich, so
every row and detail pane tests with a Console and nothing else. The screens
that compose these live in paper.py.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date as _date
from datetime import datetime, timedelta
from pathlib import Path

from rich.console import Group
from rich.table import Table
from rich.text import Text

from hedge_fund.backtesting import performance_metrics
from hedge_fund.data import FDClient, FDClientError, PriceSnapshot
from hedge_fund.data.bars import bar_time, bars_per_day, is_intraday, next_bar
from hedge_fund.data.sessions import NEW_YORK
from hedge_fund.fund import FundSpec
from hedge_fund.paper import is_running, Ledger, LedgerError, load_deployed
from hedge_fund.pipeline import (
    DecisionRecord,
    FundState,
    is_rebalance_session,
    SessionRecord,
)
from hedge_fund.tui.palette import BRIGHT, CYAN, GREEN, MUTED, RED, TEXT
from hedge_fund.tui.report import session_row, weights_line
from hedge_fund.tui.shared import cadence_identity, render_area_chart

_PERIOD_WORD = {"daily": "day", "weekly": "week", "monthly": "month"}


# The reason the app's `h` writes to the kill switch. The ledger wants one for
# `aihf paper status` and the event log; the app does not ask, so it is not shown.
APP_HALT = "halted in the app"


LIVE_REFRESH = 30  # seconds between quote refreshes while the paper list is up


class PaperSnapshot:
    """Everything the paper screens show about one deployed fund, read once
    from its directory. `error` is set when the ledger cannot be trusted
    (broken chain, altered record); the fund is then display-only."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.deployed = load_deployed(directory)
        self.ledger = Ledger(directory)
        self.records: list[SessionRecord] = []
        self.state: FundState | None = None
        self.error: str | None = None
        # A minute fund is alive while its runner process is; a daily fund
        # has no process and is never "running".
        self.running = self.deployed.spec.is_intraday and is_running(directory)
        try:
            self.records = self.ledger.records()
            self.state = self.ledger.replay(self.deployed.spec.capital)
        except LedgerError as exc:
            self.error = str(exc)

    @property
    def spec(self) -> FundSpec:
        return self.deployed.spec

    @property
    def intraday(self) -> bool:
        return self.spec.is_intraday

    def today(self, today: str | None = None) -> list[SessionRecord]:
        """A minute fund's records from *today* (NY date; default: now)."""
        today = today or datetime.now(NEW_YORK).date().isoformat()
        return [r for r in self.records if r.session[:10] == today and is_intraday(r.session)]

    @property
    def halted(self) -> str | None:
        return self.state.halted if self.state is not None else None

    @property
    def pending(self) -> DecisionRecord | None:
        return self.state.pending if self.state is not None else None

    @property
    def nav(self) -> float:
        return self.records[-1].nav if self.records else self.spec.capital

    @property
    def last_session(self) -> str | None:
        return self.records[-1].session if self.records else None

    @property
    def runnable(self) -> bool:
        return self.error is None and self.halted is None

    def curves(self) -> tuple[list[str], list[float], list[float]]:
        """Dates, NAV, and the benchmark scaled to the fund's capital."""
        dates = [r.session for r in self.records]
        nav = [r.nav for r in self.records]
        first = self.records[0].benchmark_close if self.records else 1.0
        bench = [self.spec.capital * r.benchmark_close / first for r in self.records]
        return dates, nav, bench

    def metrics(self):
        dates, nav, bench = self.curves()
        cycles = [r.executed for r in self.records if r.executed is not None]
        per_year = bars_per_day(self.spec.interval_seconds, self.spec.window) * 252 if self.intraday else 252
        return performance_metrics(self.spec.capital, dates, nav, bench, cycles, periods_per_year=per_year)

    def _state_word(self) -> tuple[str, str, str]:
        """Glyph, word, tone. A minute fund's resting state is whether its
        runner is up; a daily fund's is whether it has a track record yet."""
        if self.error:
            return "✗", "ledger error", RED
        if self.halted:
            return "■", "halted", RED
        if self.intraday:
            return ("●", "running", GREEN) if self.running else ("○", "idle", MUTED)
        if self.last_session is None:
            return "●", "new", CYAN
        return "●", "live", GREEN

    def status(self) -> Text:
        """One line: the same facts as `aihf paper status`."""
        glyph, word, tone = self._state_word()
        line = Text()
        line.append(f"{glyph} {word.upper()}  ", style=f"bold {tone}")
        if self.error:
            line.append(self.error, style=RED)
        elif self.halted:
            line.append(self.halted, style=RED)
        elif self.last_session is None:
            line.append("no sessions yet", style=MUTED)
        else:
            line.append(f"last session {self.last_session}", style=TEXT)
        return line

    def badge(self) -> Text:
        """The state as a colored glyph and a quiet word, for a header line.
        The reason behind a halt or an error is told where there is room."""
        glyph, word, tone = self._state_word()
        return Text.assemble((f"{glyph} ", tone), (word, MUTED))


def paper_slot(index: int, snap: PaperSnapshot) -> Text:
    """One fund in the paper rail: number, name, and how it is doing. One
    line; everything else about the fund belongs to the detail pane."""
    card = Text()
    card.append(f" {index + 1:02d}  ", style=MUTED)
    card.append(snap.deployed.name, style=TEXT)
    glyph, word, tone = snap._state_word()
    if snap.error:
        card.append("   ✗ ledger", style=RED)
        return card
    if snap.records and not snap.halted:
        ret = snap.nav / snap.spec.capital - 1
        card.append(f"   {ret:+.1%}", style=GREEN if ret >= 0 else RED)
        card.append("  ", style=MUTED)
    else:
        card.append("   ")
    card.append(f"{glyph} {word}", style=tone)
    return card


def next_run_rows(snap: PaperSnapshot, now: datetime | None = None) -> list[tuple[str, Text | str]]:
    """What the next run will do, from the ledger alone — no network on a
    highlight. Two steps: what happens to the pending decision, then
    whether a new one is made. The exact date is resolved when the user
    asks to run. For a minute fund the next run is the next bar on its
    grid, and whether anything happens at it depends on the runner."""
    if snap.halted:
        rows: list[tuple[str, Text | str]] = [("Halted", Text("r to resume before it can run", style=RED))]
        if snap.halted not in (APP_HALT, "halted"):  # a reason given from the CLI
            rows.append(("", Text(snap.halted, style=MUTED)))
        return rows
    rows: list[tuple[str, Text | str]] = []
    if snap.intraday:
        spec = snap.spec
        upcoming = next_bar(now or datetime.now(NEW_YORK), spec.interval_seconds, spec.window)
        today = (now or datetime.now(NEW_YORK)).astimezone(NEW_YORK).date()
        when = upcoming.strftime("%H:%M:%S ET") if upcoming.date() == today else upcoming.strftime("%a %H:%M:%S ET")
        rows.append(("Next bar", Text.assemble(
            (when, BRIGHT),
            ("   ● running" if snap.running else "   ○ idle · enter to start", GREEN if snap.running else MUTED))))
    if snap.pending is not None:
        rows.append(("First", Text.assemble(
            "execute the ", (snap.pending.as_of, BRIGHT), " decision")))
        rows.append(("", weights_line(snap.pending)))
    elif snap.last_session is None:
        rows.append(("First", "mark the book at the first bar's prints" if snap.intraday
                     else "mark the book at the latest completed close"))
    else:
        rows.append(("First", "mark the book"))
    cadence = snap.spec.rebalance
    if snap.last_session is None:
        rows.append(("Then", "make the first decision"))
    elif cadence in ("daily", "minute"):
        rows.append(("Then", "make a new decision"))
    else:
        rows.append(("Then", f"make a new decision if it opens a new {_PERIOD_WORD[cadence]}"))
    return rows


def today_rows(snap: PaperSnapshot, now: datetime | None = None) -> list[tuple[str, Text | str]]:
    """A minute fund's day so far: bars recorded out of the day's grid, the
    last one's time, and the move since the open (the NAV going into the
    day's first bar). Empty before the first bar of the day."""
    now = now or datetime.now(NEW_YORK)
    today = now.astimezone(NEW_YORK).date().isoformat()
    bars = snap.today(today)
    if not bars:
        return []
    spec = snap.spec
    total = bars_per_day(spec.interval_seconds, spec.window)
    first_index = snap.records.index(bars[0])
    opened_at = snap.records[first_index - 1].nav if first_index else spec.capital
    change = bars[-1].nav / opened_at - 1 if opened_at else 0.0
    fills = sum(len(r.executed.fills) for r in bars if r.executed is not None)
    return [
        ("Bars", Text.assemble((f"{len(bars)} / {total}", TEXT),
                               (f"   last {bar_time(bars[-1].session):%H:%M:%S} ET", MUTED))),
        ("Since open", Text.assemble((f"{change:+.2%}", GREEN if change >= 0 else RED),
                                     (f"   {fills} {'fill' if fills == 1 else 'fills'}", MUTED))),
    ]


def live_rows(
    snap: PaperSnapshot, quotes: dict[str, PriceSnapshot], today: str | None = None,
) -> list[tuple[str, Text | str]]:
    """The book at the latest prints: value, change since the last close,
    and when the newest print was. Empty unless every held name has a quote;
    muted all through when the newest print is from before *today*, because
    a stale quote marked green would be a lie."""
    if snap.state is None or not snap.state.positions:
        return []
    positions = snap.state.positions
    if any(t not in quotes for t in positions):
        return []
    value = snap.state.cash + sum(shares * quotes[t].price for t, shares in positions.items())
    change = value / snap.nav - 1 if snap.nav else 0.0
    newest = max(_quote_time(quotes[t]) for t in positions)
    today = today or datetime.now(NEW_YORK).date().isoformat()
    stale = newest.date().isoformat() < today
    tone = MUTED if stale else GREEN if change >= 0 else RED
    when = newest.strftime("%b %-d %H:%M") if stale else newest.strftime("%H:%M")
    return [("Live", Text.assemble(
        (f"${value:,.0f}", MUTED if stale else TEXT),
        (f"   {change:+.2%}", tone),
        (f"   as of {when} ET", MUTED)))]


def paper_detail(
    snap: PaperSnapshot, width: int = 60, quotes: dict[str, PriceSnapshot] | None = None,
    now: datetime | None = None,
) -> Group:
    """The right pane, top to bottom: who the fund is, what the next run
    does, (a minute fund's day so far,) how it has done, its last few
    sessions. One bold line (the name); color only where it means something
    — gains, losses, state. *quotes* (the latest prints for the held names)
    adds a live value line; *now* is for tests."""
    spec = snap.spec
    staff = ", ".join(s.title for s in spec.strategies)
    parts: list = [
        Text.assemble((snap.deployed.name, f"bold {BRIGHT}"), "   ", snap.badge()),
        Text(f"{staff} · {cadence_identity(spec)} · ${spec.capital:,.0f} · {' '.join(snap.deployed.universe)}",
             style=MUTED),
        Text(""),
    ]
    if snap.error:
        parts.append(Text(snap.error, style=RED))
        return Group(*parts)
    parts += [_section("NEXT RUN"), _facts(next_run_rows(snap, now))]
    today = today_rows(snap, now) if snap.intraday else []
    if today:
        parts += [Text(""), _section("TODAY"), _facts(today)]
    if snap.records:
        m = snap.metrics()
        _, nav, bench = snap.curves()
        n = len(snap.records)
        ret, bench_ret = m.total_return_pct, m.benchmark_return_pct
        parts += [Text(""), _section("PERFORMANCE"), _facts([
            ("Value", f"${snap.nav:,.0f}"),
            ("Return", Text.assemble((f"{ret:+.1%}", GREEN if ret >= 0 else RED),
                                     (f"   {spec.benchmark} {bench_ret:+.1%}", MUTED))),
            ("Since", Text(f"{snap.records[0].session} · {n} {'session' if n == 1 else 'sessions'}"
                           f" · {m.n_orders} {'order' if m.n_orders == 1 else 'orders'}", style=MUTED)),
            *(live_rows(snap, quotes) if quotes else []),
        ])]
        if n >= 2:  # one point is a flat block, not a curve
            parts.append(Text(""))
            parts.extend(render_area_chart(nav, bench, spec.capital, width))
        parts += [Text(""), _section("SESSIONS")]
        navs = [spec.capital, *(r.nav for r in snap.records)]
        shown = min(n, 3)
        for i in range(n - 1, n - 1 - shown, -1):
            parts.append(Text(" ").append_text(session_row(snap.records[i], navs[i])))
        if n > shown:
            parts.append(Text(f"   … {n - shown} more · s for all", style=MUTED))
    return Group(*parts)


def fetch_snapshots(tickers: list[str]) -> dict[str, PriceSnapshot]:
    """One real-time quote per ticker, fetched together. Empty when there is
    no key to ask with or the API refuses: the pane then shows the last close
    and nothing else, which is the honest fallback."""
    if not tickers or not os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        return {}
    quotes: dict[str, PriceSnapshot] = {}
    try:
        with FDClient() as fd, ThreadPoolExecutor(max_workers=min(8, len(tickers))) as pool:
            for ticker, snapshot in zip(tickers, pool.map(fd.get_snapshot, tickers)):
                if snapshot is not None:
                    quotes[ticker] = snapshot
    except FDClientError:
        return {}
    return quotes


def run_plan(name: str, state: FundState, due: str | None, spec: FundSpec) -> Text:
    """What pressing enter will do, in plain words, from the ledger state and
    the session that is due. Pure: the confirm modal renders it, tests read it.

    Three shapes when a session is due — execute then decide, execute then
    mark, or mark only. When nothing is due, enter runs the last session
    again instead, and the body says what that replaces.
    """
    body = Text()
    if due is None:
        if state.last_session is None:
            body.append(f"No completed {spec.benchmark} session to run yet.", style=TEXT)
            return body
        body.append("Up to date through ", style=TEXT)
        body.append(state.last_session, style=f"bold {BRIGHT}")
        body.append(".  Next session closes ", style=TEXT)
        body.append(_next_weekday(state.last_session), style=f"bold {BRIGHT}")
        body.append(" at 4pm ET.\n\n", style=TEXT)
        body.append("Run ", style=TEXT)
        body.append(state.last_session, style=f"bold {BRIGHT}")
        body.append(" again?  ", style=TEXT)
        body.append("The analysts look again and the book is sized again at the same close. "
                    "The recorded session is replaced; the old record is kept aside, off the chain.",
                    style=MUTED)
        return body
    if state.pending is not None:
        body.append("Execute the ", style=TEXT)
        body.append(state.pending.as_of, style=f"bold {BRIGHT}")
        body.append(" decision at the ", style=TEXT)
        body.append(due, style=f"bold {BRIGHT}")
        body.append(" close\n  ", style=TEXT)
        body.append_text(weights_line(state.pending))
        body.append("\n  views refreshed before sizing\n", style=MUTED)
        then = "Then "
    else:
        body.append("Mark the book at the ", style=TEXT)
        body.append(due, style=f"bold {BRIGHT}")
        body.append(" close.  No trades.\n", style=TEXT)
        then = ""
    if is_rebalance_session(due, state.last_session, spec.rebalance):
        why = ("the fund's first decision" if state.last_session is None
               else "every session" if spec.rebalance == "daily"
               else f"first session of the {_PERIOD_WORD[spec.rebalance]}")
        body.append(f"{then}make a new decision", style=TEXT)
        body.append(f"  ({why})", style=MUTED)
    elif then:
        body.append("Then mark the book.", style=TEXT)
    return body


def day_heading(day: str, records: list[SessionRecord], navs: list[float]) -> Text:
    """A day's line over its bars in the history rail: the date, how many
    bars, and the day's move (its last bar against the NAV going into it)."""
    indices = [i for i, r in enumerate(records) if r.session[:10] == day]
    opened_at, closed_at = navs[indices[0]], navs[indices[-1] + 1]
    change = closed_at / opened_at - 1 if opened_at else 0.0
    n = len(indices)
    return Text.assemble(
        (f" {day}", f"bold {BRIGHT}"),
        (f"  {change:+.2%}", GREEN if change >= 0 else RED),
        (f"  {n} {'bar' if n == 1 else 'bars'}", MUTED),
    )


def _section(title: str) -> Text:
    """A block title in the detail pane: quiet, so the values carry the weight."""
    return Text(title, style=MUTED)


def _facts(rows: list[tuple[str, Text | str]]) -> Table:
    """Label/value rows with the values in one aligned column — easier to
    scan than a sentence strung together with dots."""
    grid = Table.grid(padding=(0, 3))
    grid.add_column(style=MUTED, no_wrap=True)
    grid.add_column(style=TEXT)
    for label, value in rows:
        grid.add_row(f"  {label}" if label else "", value)
    return grid


def _quote_time(snapshot: PriceSnapshot) -> datetime:
    """The quote's trade time in New York."""
    return datetime.fromisoformat(snapshot.time.replace("Z", "+00:00")).astimezone(NEW_YORK)


def _next_weekday(after: str) -> str:
    """The first Monday–Friday strictly after *after* (YYYY-MM-DD). Holidays
    are not consulted; this is a hint, not a schedule."""
    day = _date.fromisoformat(after) + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day.isoformat()
