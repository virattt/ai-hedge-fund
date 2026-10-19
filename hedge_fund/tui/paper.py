"""Paper trading: the fund list, the approval step, one run, and a fund's history."""

from __future__ import annotations

from concurrent.futures import as_completed, ThreadPoolExecutor
from pathlib import Path

from rich.console import Group
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.timer import Timer
from textual.widgets import ContentSwitcher, Footer, OptionList, Static
from textual.widgets.option_list import Option

from hedge_fund import paths
from hedge_fund.data import CachedDataClient, FDClient, PriceSnapshot
from hedge_fund.data.bars import is_intraday
from hedge_fund.fund import FundSpec
from hedge_fund.llm import make_llm
from hedge_fund.paper import (
    assessment_dates,
    DeployedFund,
    is_running,
    Ledger,
    list_deployed,
    load_deployed,
    next_session,
    NothingDue,
    redo,
    spawn_runner,
    stop_runner,
    tick,
)
from hedge_fund.pipeline import (
    DecisionRecord,
    FundState,
    SessionRecord,
)
from hedge_fund.scorecard import score
from hedge_fund.signals import ALPHA_MODEL_REGISTRY, LLMAgent
from hedge_fund.tui.builder import BuilderScreen
from hedge_fund.tui.funds import ConfirmWipeScreen, wipe_fund
from hedge_fund.tui.home import demand_run_keys
from hedge_fund.tui.palette import BRIGHT, CYAN, GREEN, MUTED, RED, TEXT
from hedge_fund.tui.paper_view import (
    APP_HALT,
    day_heading,
    fetch_snapshots,
    LIVE_REFRESH,
    paper_detail,
    paper_slot,
    PaperSnapshot,
    run_plan,
)
from hedge_fund.tui.report import (
    book_summary,
    Desk,
    desk_table,
    session_detail,
    session_headline,
    session_nav,
    session_overview,
    session_row,
)
from hedge_fund.tui.scorecard_view import analyst_table, strategy_table
from hedge_fund.tui.shared import (
    agent_names,
    BOARD_REFRESH,
    cadence_identity,
    DISPLAY_NAMES,
    render_area_chart,
    session_label,
)
from hedge_fund.tui.widgets import first_selectable, StatTiles


class PaperScreen(Screen):
    """Paper trading. The fund list is the home of the fund: every deployed
    fund on the left, the highlighted one's state and its next run on the
    right. Enter runs its next session (through the approval step); `space`
    starts or stops its runner, the detached loop that does the same thing
    unattended; `s` opens its history; `h`/`r` work the kill switch; the
    last row builds a new fund. Every verb means the same thing at every
    cadence; the cadence only decides when the next session is.
    """

    BINDINGS = [
        Binding("escape", "back", "back"),
        Binding("enter", "run", "run next session", priority=True),
        Binding("space", "runner", "start/stop runner"),
        Binding("s", "sessions", "sessions"),
        Binding("h", "halt", "halt"),
        Binding("r", "resume", "resume"),
        Binding("d", "delete", "delete"),
    ]

    def __init__(self, select: str | None = None, run: bool = False) -> None:
        super().__init__()
        self._snaps: list[PaperSnapshot | None] = []
        self._select = select   # highlight this fund on first paint
        self._run_on_mount = run  # ...and open its approval step right away
        self._quotes: dict[str, dict[str, PriceSnapshot]] = {}  # fund name -> latest prints
        self._quote_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="select"):
            with Vertical(id="select-rail"):
                yield Static(Text("PAPER TRADING", style=MUTED), classes="rail-title")
                yield OptionList(id="paper-menu")
            with VerticalScroll(id="select-detail"):
                yield Static("", id="detail-body")
        yield Footer()

    def on_mount(self) -> None:
        self._populate(self._select)
        self._quote_timer = self.set_interval(LIVE_REFRESH, self._poll_quotes)
        if self._run_on_mount:
            self._run_on_mount = False
            self.call_after_refresh(self.action_run)

    def on_screen_suspend(self) -> None:
        if self._quote_timer is not None:
            self._quote_timer.pause()

    def on_screen_resume(self) -> None:
        current = self._current()
        self._populate(current.deployed.name if current else None)
        if self._quote_timer is not None:
            self._quote_timer.resume()

    # ---- the list ---------------------------------------------------------

    def _populate(self, select: str | None) -> None:
        menu = self.query_one("#paper-menu", OptionList)
        menu.clear_options()
        self._snaps = []
        for i, directory in enumerate(list_deployed(paths.PAPER_DIR)):
            try:
                snap = PaperSnapshot(directory)
            except ValueError as exc:
                self._snaps.append(None)
                menu.add_option(Option(
                    Text(f" {directory.name} — Unavailable\n     {exc}", style=MUTED), disabled=True))
                continue
            self._snaps.append(snap)
            menu.add_option(Option(paper_slot(i, snap), id=f"paper:{i}"))
        if self._snaps:
            menu.add_option(None)
        menu.add_option(Option(Text.assemble(
            ("  +  ", GREEN), ("Build a new fund", TEXT)), id="build"))
        # Options added after mount leave `highlighted` unset — pin it to the
        # asked-for fund, else the first readable one, else the build row.
        wanted = next((f"paper:{i}" for i, s in enumerate(self._snaps)
                       if s is not None and s.deployed.name == select), None)
        first = wanted or next((f"paper:{i}" for i, s in enumerate(self._snaps) if s is not None), "build")
        menu.highlighted = menu.get_option_index(first)
        menu.focus()
        self._show_detail(first)
        self.refresh_bindings()

    def _current(self) -> PaperSnapshot | None:
        menu = self.query_one("#paper-menu", OptionList)
        if menu.highlighted is None:
            return None
        oid = menu.get_option_at_index(menu.highlighted).id or ""
        if not oid.startswith("paper:"):
            return None
        return self._snaps[int(oid.split(":")[1])]

    @on(OptionList.OptionHighlighted, "#paper-menu")
    def _highlight(self, event: OptionList.OptionHighlighted) -> None:
        oid = (event.option.id or "") if event.option else ""
        if oid:
            self._show_detail(oid)
        self.refresh_bindings()

    def _show_detail(self, oid: str) -> None:
        detail = self.query_one("#detail-body", Static)
        if oid.startswith("paper:"):
            snap = self._snaps[int(oid.split(":")[1])]
            if snap is not None:
                width = detail.content_size.width or 60
                detail.update(paper_detail(snap, min(width, 100), self._quotes.get(snap.deployed.name)))
                self._poll_quotes()
        elif oid == "build":
            blurb = Text()
            if not self._snaps:
                blurb.append("No funds yet.\n\n", style=f"bold {BRIGHT}")
            blurb.append(
                "Build a fund here and it starts paper trading at once: pick its "
                "strategies, capital, cadence and tickers, and it gets a ledger, a "
                "book and a kill switch of its own under\n" + str(paths.PAPER_DIR) + "\n\n"
                "Then run it a session at a time with enter, or leave it running with "
                "space (`aihf paper run <name>` from a shell). Whatever its cadence, "
                "the next session is the next close or the next bar.", style=MUTED)
            detail.update(blurb)

    # ---- live quotes ------------------------------------------------------

    def _poll_quotes(self) -> None:
        """Ask for the highlighted fund's prints, off-thread. Only a fund with
        positions has anything live to show; cash is cash. A runner changes
        the ledger under us: re-read it when the runner has come or gone, or
        has recorded a session since the last read."""
        snap = self._current()
        if snap is None:
            return
        if snap.error is None and (
                is_running(snap.directory) != snap.running
                or (snap.ledger.sessions() or [None])[-1] != snap.last_session):
            self._populate(snap.deployed.name)
            return
        if snap.state is not None and snap.state.positions:
            self._fetch_quotes(snap.deployed.name, sorted(snap.state.positions))

    @work(thread=True, group="quotes", exclusive=True)
    def _fetch_quotes(self, name: str, tickers: list[str]) -> None:
        quotes = fetch_snapshots(tickers)
        if quotes:
            self.app.call_from_thread(self._quotes_arrived, name, quotes)

    def _quotes_arrived(self, name: str, quotes: dict[str, PriceSnapshot]) -> None:
        self._quotes[name] = quotes
        snap = self._current()
        if snap is not None and snap.deployed.name == name:
            detail = self.query_one("#detail-body", Static)
            width = detail.content_size.width or 60
            detail.update(paper_detail(snap, min(width, 100), quotes))

    # ---- actions ----------------------------------------------------------

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        if action in ("back", "run"):
            return True  # run also handles the build row
        snap = self._current()
        if snap is None:
            return False
        if action == "delete":
            return True  # a fund with a broken ledger can still be deleted
        if snap.error:
            return False
        if action == "halt":
            return snap.halted is None
        if action == "resume":
            return snap.halted is not None
        if action == "runner":
            return snap.halted is None or snap.running  # a halted fund's runner can still be stopped
        return True

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_run(self) -> None:
        menu = self.query_one("#paper-menu", OptionList)
        if menu.highlighted is None:
            return
        if (menu.get_option_at_index(menu.highlighted).id or "") == "build":
            self.app.push_screen(BuilderScreen(mode="paper"))
            return
        snap = self._current()
        if snap is None or snap.error:
            return
        if snap.halted:
            self.notify(f"{snap.deployed.name} is halted — r to resume first.", severity="warning")
            return
        if snap.running:
            self.notify(f"{snap.deployed.name}'s runner is advancing it — space to stop it first.",
                        severity="warning")
            return
        directory = snap.directory

        def resume() -> None:
            if demand_run_keys(self.app, resume):
                self.app.push_screen(RunConfirmScreen(directory),
                                     lambda verdict: self._after_confirm(directory, verdict))
        resume()

    def action_runner(self) -> None:
        """Space: stop the fund's runner if one is up, else start one (a
        detached `aihf paper run`, so it outlives this screen). The runner
        does what enter does, unattended, at the fund's cadence."""
        snap = self._current()
        if snap is None or snap.error:
            return
        name = snap.deployed.name
        if is_running(snap.directory):
            stop_runner(snap.directory)
            self.notify(f"{name} stopping after the session in flight")
            self._populate(name)
            return
        if snap.halted:
            self.notify(f"{name} is halted — r to resume first.", severity="warning")
            return

        def resume() -> None:
            if demand_run_keys(self.app, resume):
                try:
                    spawn_runner(snap.directory)
                except OSError as exc:
                    self.notify(f"Could not start {name}: {exc}", severity="error")
                    return
                self.notify(f"{name} running · {cadence_identity(snap.spec)}")
                self._populate(name)
        resume()

    def _after_confirm(self, directory: Path, verdict: str | None) -> None:
        if verdict is not None:
            self.app.push_screen(RunSessionScreen(directory, redo=verdict == "redo"))

    def action_sessions(self) -> None:
        snap = self._current()
        if snap is not None:
            self.app.push_screen(SessionsScreen(snap.directory))

    def action_halt(self) -> None:
        snap = self._current()
        if snap is None:
            return
        snap.ledger.halt(APP_HALT)
        self.notify(f"{snap.deployed.name} halted · r to resume", severity="warning")
        self._populate(snap.deployed.name)

    def action_resume(self) -> None:
        snap = self._current()
        if snap is None:
            return
        snap.ledger.resume()
        self.notify(f"{snap.deployed.name} resumed")
        self._populate(snap.deployed.name)

    def action_delete(self) -> None:
        snap = self._current()
        if snap is None:
            return
        name = snap.deployed.name
        self.app.push_screen(ConfirmWipeScreen(name), lambda yes: self._finish_delete(name, yes))

    def _finish_delete(self, name: str, yes: bool | None) -> None:
        if not yes:
            return
        wipe_fund(name)
        self.notify(f"Deleted {name}", severity="warning")
        self._populate(None)


class RunConfirmScreen(ModalScreen[str | None]):
    """The approval step. Enter on a fund is "run", so before anything trades
    the user sees exactly what this run will do — the decision about to be
    executed, its targets, whether a new decision follows — and says yes.
    Nothing has touched the ledger or the broker until they do.

    Dismisses with "run" when a session is due, "redo" when nothing is due
    but the last session can be run again, None when the user backs out.
    """

    BINDINGS = [
        Binding("escape", "cancel", "cancel"),
        Binding("enter", "confirm", "run", priority=True),
    ]

    def __init__(self, directory: Path) -> None:
        super().__init__()
        self._directory = directory
        self._verdict: str | None = None  # what enter will do once resolved
        self._ready = False

    def compose(self) -> ComposeResult:
        with Vertical(id="run-confirm"):
            yield Static("", id="run-q")
            yield Static(Text("finding the next session…", style=MUTED), id="run-body")
            yield Static("", id="run-keys")

    def on_mount(self) -> None:
        self.query_one("#run-q", Static).update(
            Text.assemble(("Run ", f"bold {BRIGHT}"), (self._directory.name, f"bold {GREEN}"),
                          ("?", f"bold {BRIGHT}")))
        self.query_one("#run-keys", Static).update(Text("esc  cancel", style=MUTED))
        self._resolve()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        if action == "confirm":
            return self._ready and self._verdict is not None
        return True

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_confirm(self) -> None:
        self.dismiss(self._verdict)

    @work(thread=True, exclusive=True)
    def _resolve(self) -> None:
        app = self.app
        try:
            deployed, state, due = _resolve_next_session(self._directory)
        except Exception as exc:
            app.call_from_thread(self._show_error, exc)
            return
        app.call_from_thread(self._show, deployed, state, due)

    def _show(self, deployed: DeployedFund, state: FundState, due: str | None) -> None:
        self._verdict = "run" if due is not None else "redo" if state.last_session else None
        self._ready = True
        self.query_one("#run-q", Static).update(Text.assemble(
            ("Run ", f"bold {BRIGHT}"), (deployed.name, f"bold {GREEN}"),
            (f" through {session_label(due)}?" if due else
             f" again through {session_label(state.last_session)}?" if self._verdict == "redo" else "?",
             f"bold {BRIGHT}")))
        self.query_one("#run-body", Static).update(run_plan(deployed.name, state, due, deployed.spec))
        keys = Text()
        if self._verdict is not None:
            keys.append("enter", style=f"bold {GREEN}")
            keys.append("  run   " if self._verdict == "run" else "  run again   ", style=MUTED)
        keys.append("esc", style=f"bold {BRIGHT}")
        keys.append("  cancel", style=MUTED)
        self.query_one("#run-keys", Static).update(keys)
        self.refresh_bindings()

    def _show_error(self, exc: Exception) -> None:
        self._ready = True
        self.query_one("#run-body", Static).update(
            Text.assemble(("✗ ", f"bold {RED}"), (f"{type(exc).__name__}: {exc}", RED)))
        self.refresh_bindings()


class RunSessionScreen(Screen):
    """Run a paper fund through its next session, with the analysts' live
    board while they think, then the session's report. Reached only through
    the approval step, which has already checked the fund is runnable and
    that a session is due.

    The board is a best-effort warm: each analyst streams its thesis for the
    dates the run will assess, filling the caches `tick` reads a moment
    later. `tick` is the source of truth; it writes the ledger.
    """

    BINDINGS = [Binding("escape", "back", "back")]

    def __init__(self, directory: Path, *, redo: bool = False) -> None:
        super().__init__()
        self._directory = directory
        self._redo = redo  # run the last recorded session again, replacing it
        self._phase = "running"
        self._record: SessionRecord | None = None
        self._desks: list[Desk] = []
        self._painter: Timer | None = None

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial="run-live", id="run-panes"):
            with VerticalScroll(id="run-live", classes="pane"):
                yield Static("", id="run-phase")
                yield Static("", id="run-roster")
            with Vertical(id="run-report"):
                yield Static("", id="report-head")
                with Horizontal(id="report-panes"):
                    with Vertical(id="report-rail"):
                        yield OptionList(id="report-nav")
                    with VerticalScroll(id="report-detail"):
                        yield Static("", id="detail-pane")
                yield Static("", id="report-foot")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#run-phase", Static).update(
            Text(f"Starting {self._directory.name}…", style=MUTED))
        self._run()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        # No leaving mid-run: the worker is writing the ledger.
        return not (action == "back" and self._phase == "running")

    def action_back(self) -> None:
        self.app.pop_screen()

    @on(OptionList.OptionHighlighted, "#report-nav")
    def _browse(self, event: OptionList.OptionHighlighted) -> None:
        assert self._record is not None
        oid = (event.option.id or "") if event.option else ""
        detail = session_detail(self._record, oid)
        if detail is not None:
            self.query_one("#detail-pane", Static).update(detail)
            self.query_one("#report-detail", VerticalScroll).scroll_home(animate=False)

    @work(thread=True, exclusive=True)
    def _run(self) -> None:
        app = self.app
        directory = self._directory
        try:
            deployed = load_deployed(directory)
            spec = deployed.spec
            ledger = Ledger(directory)
            state = ledger.replay(spec.capital)
            with FDClient() as raw:
                data = CachedDataClient(raw, live=spec.is_intraday)
                if self._redo:
                    if state.last_session is None:
                        raise NothingDue("no session recorded yet, nothing to run again")
                    # The board is told about the state going into the session,
                    # which is what `redo` will advance from.
                    due = state.last_session
                    state = ledger.replay(spec.capital, before=due)
                else:
                    due = next_session(data, spec, state.last_session)
                    if due is None:  # the session slipped out from under the approval step
                        raise NothingDue(f"nothing due after {state.last_session}")
                dates = assessment_dates(state, due, spec)
                app.call_from_thread(self._begin_board, deployed, due, dates, state.pending)
                if dates:
                    self._warm(spec, deployed.universe, dates)
                record = redo(directory, data) if self._redo else tick(directory, data)
            app.call_from_thread(self._show_report, deployed, record)
        except Exception as exc:  # fail loud, in the UI
            app.call_from_thread(self._fail, exc)

    def _warm(self, spec: FundSpec, universe: list[str], dates: list[str]) -> None:
        desks = dict(zip(agent_names(spec), self._desks, strict=True))

        def warm(agent_name: str) -> None:
            desk = desks[agent_name]
            cls = ALPHA_MODEL_REGISTRY[agent_name]  # own instance per thread
            # Only LLM agents have anything to stream; a quant model carries
            # no client and simply runs.
            model = (cls(llm=make_llm(on_token=desk.feed))
                     if issubclass(cls, LLMAgent) else cls())
            with FDClient() as raw:
                fd = CachedDataClient(raw)
                for as_of in dates:
                    for ticker in universe:
                        desk.begin(ticker)
                        try:
                            desk.settle(model.predict(ticker, as_of, fd))
                        except Exception:
                            pass  # best-effort warm; tick is the source of truth
            desk.finish()

        names = list(desks)
        with ThreadPoolExecutor(max_workers=min(8, len(names))) as pool:
            for future in as_completed([pool.submit(warm, n) for n in names]):
                future.result()

    # ---- UI-thread updates ------------------------------------------------

    def _begin_board(self, deployed: DeployedFund, due: str, dates: list[str],
                     pending: DecisionRecord | None) -> None:
        doing = []
        if pending is not None:
            doing.append(f"executing the {pending.as_of} decision")
        if due in dates:
            doing.append("assessing the next decision")
        if not doing:
            doing.append("marking the book")
        self.query_one("#run-phase", Static).update(Text.assemble(
            (f"Running {deployed.name} {'again through' if self._redo else 'through'} ", f"bold {BRIGHT}"),
            (session_label(due), f"bold {RED}"),
            ("  ·  " + " · ".join(doing), MUTED),
        ))
        if not dates:
            return
        self._desks = [Desk(DISPLAY_NAMES.get(n, n)) for n in agent_names(deployed.spec)]
        self._paint_board()
        # The worker threads mutate their own desk; this redraws all of them on
        # one clock, so token rate never sets frame rate.
        self._painter = self.set_interval(BOARD_REFRESH, self._paint_board)

    def _paint_board(self) -> None:
        self.query_one("#run-roster", Static).update(desk_table(self._desks))

    def _stop_painting(self) -> None:
        if self._painter is not None:
            self._painter.stop()
            self._painter = None
        if self._desks:
            self._paint_board()

    def _show_report(self, deployed: DeployedFund, record: SessionRecord) -> None:
        self._stop_painting()
        self._phase = "done"
        self._record = record
        self.query_one("#report-head", Static).update(session_headline(deployed.name, record))
        self.query_one("#report-foot", Static).update(Group(
            book_summary(record),
            Text.assemble(("✓ ", f"bold {GREEN}"), ("Recorded ", MUTED),
                          (str(Ledger(self._directory).path(record.session)), MUTED)),
        ))
        self.refresh_bindings()  # phase changed: esc is offered again
        nav = self.query_one("#report-nav", OptionList)
        nav.clear_options()
        nav.add_options(session_nav(record))
        self.query_one("#run-panes", ContentSwitcher).current = "run-report"
        nav.highlighted = first_selectable(nav)
        nav.focus()

    def _fail(self, exc: Exception) -> None:
        self._stop_painting()
        self._phase = "failed"
        phase = self.query_one("#run-phase", Static)
        if isinstance(exc, NothingDue):
            phase.update(Text.assemble(
                ("Nothing due  ", f"bold {BRIGHT}"), (f"{exc}", MUTED),
                ("\n\nThe fund is up to date. Run it again when the next session is in. esc to go back.", MUTED)))
        else:
            phase.update(Text.assemble(
                ("✗ ", f"bold {RED}"), (f"{type(exc).__name__}: {exc}", RED),
                ("\n\nesc to go back", MUTED)))
            self.notify(str(exc), title="Run failed", severity="error")
        self.refresh_bindings()


class SessionsScreen(Screen):
    """One fund's history: the running numbers, the equity curve, and every
    session it has recorded. Enter on a session opens its full report.
    Running and the kill switch live on the fund list, not here.
    """

    BINDINGS = [Binding("escape", "back", "back")]

    def __init__(self, directory: Path) -> None:
        super().__init__()
        self._directory = directory
        self._snap: PaperSnapshot | None = None
        self._shown: list[SessionRecord] = []  # newest first, as listed

    def compose(self) -> ComposeResult:
        with Vertical(id="pf"):
            yield Static("", id="pf-head")
            yield Static("", id="pf-status")
            yield StatTiles(id="stats")
            with Vertical(id="curve-box"):
                yield Static("", id="curve")
            yield Static("", id="scorecard")
            with Horizontal(id="pf-panes"):
                with Vertical(id="report-rail"):
                    yield Static(Text("SESSIONS", style=MUTED), classes="rail-title")
                    yield OptionList(id="pf-sessions")
                with VerticalScroll(id="report-detail"):
                    yield Static("", id="detail-pane")
        yield Footer()

    def on_mount(self) -> None:
        self._load()

    def on_screen_resume(self) -> None:
        self._load()

    def action_back(self) -> None:
        self.app.pop_screen()

    def _load(self) -> None:
        try:
            snap = PaperSnapshot(self._directory)
        except ValueError as exc:
            self._snap = None
            self.query_one("#pf-head", Static).update(Text(str(self._directory), style=f"bold {BRIGHT}"))
            self.query_one("#pf-status", Static).update(Text.assemble(("✗ ", f"bold {RED}"), (str(exc), RED)))
            return
        self._snap = snap
        spec = snap.spec
        staff = ", ".join(s.title for s in spec.strategies)
        self.query_one("#pf-head", Static).update(Group(
            Text.assemble((snap.deployed.name, f"bold {BRIGHT}"), ("  ·  paper", MUTED)),
            Text(f"{staff}  ·  {cadence_identity(spec)}  ·  ${spec.capital:,.0f}"
                 f"  ·  {' '.join(snap.deployed.universe)}", style=MUTED),
        ))
        self.query_one("#pf-status", Static).update(snap.status())
        self._render_numbers(snap)
        self._render_sessions(snap)

    def _render_numbers(self, snap: PaperSnapshot) -> None:
        curve_box = self.query_one("#curve-box", Vertical)
        curve_box.border_title = "equity curve"
        curve_box.border_subtitle = f"[{GREEN}]██[/] fund   [{CYAN}]──[/] {snap.spec.benchmark}"
        if not snap.records:
            self.query_one("#stats", StatTiles).add_class("hidden")
            self.query_one("#scorecard", Static).add_class("hidden")
            self.query_one("#curve", Static).update(
                Text("The curve starts with the first session.", style=MUTED))
            return
        self.query_one("#stats", StatTiles).remove_class("hidden")
        m = snap.metrics()
        self.query_one("#stats", StatTiles).update(
            snap.spec.benchmark, snap.nav, m.total_return_pct, m.benchmark_return_pct,
            m.excess_return_pct, m.sharpe_ratio, m.max_drawdown_pct)
        _, nav, bench = snap.curves()
        curve_widget = self.query_one("#curve", Static)
        width = curve_widget.content_size.width or 80
        curve_widget.update(Group(*render_area_chart(nav, bench, snap.spec.capital, min(width, 100))))
        card = score(snap.records)
        scorecard = self.query_one("#scorecard", Static)
        scorecard.update(Group(analyst_table(card), strategy_table(card)))
        scorecard.remove_class("hidden")

    def _render_sessions(self, snap: PaperSnapshot) -> None:
        menu = self.query_one("#pf-sessions", OptionList)
        menu.clear_options()
        self._shown = list(reversed(snap.records))
        if not self._shown:
            self.query_one("#detail-pane", Static).update(Text(
                "No sessions recorded yet.\n\nThe first run values the book at the most "
                "recent completed close and makes the first decision; the run after "
                "executes it.", style=MUTED))
            return
        navs = [snap.spec.capital, *(r.nav for r in snap.records)]
        day: str | None = None
        for i, record in enumerate(self._shown):
            index = len(snap.records) - 1 - i
            grouped = is_intraday(record.session)
            if grouped and record.session[:10] != day:  # a minute fund's bars, under their day
                day = record.session[:10]
                menu.add_option(Option(day_heading(day, snap.records, navs), disabled=True))
            menu.add_option(Option(session_row(record, navs[index], time_only=grouped), id=f"s:{i}"))
        menu.highlighted = menu.get_option_index("s:0")
        menu.focus()

    @on(OptionList.OptionHighlighted, "#pf-sessions")
    def _highlight(self, event: OptionList.OptionHighlighted) -> None:
        oid = (event.option.id or "") if event.option else ""
        if oid.startswith("s:"):
            record = self._shown[int(oid.split(":")[1])]
            self.query_one("#detail-pane", Static).update(session_overview(record))
            self.query_one("#report-detail", VerticalScroll).scroll_home(animate=False)

    @on(OptionList.OptionSelected, "#pf-sessions")
    def _open(self, event: OptionList.OptionSelected) -> None:
        oid = event.option.id or ""
        if oid.startswith("s:") and self._snap is not None:
            record = self._shown[int(oid.split(":")[1])]
            self.app.push_screen(SessionReportScreen(self._snap.deployed.name, record))


class SessionReportScreen(Screen):
    """One recorded session, browsable: every signal on the rail, the full
    thesis on the right. The same browser the tick lands on."""

    BINDINGS = [Binding("escape", "back", "back")]

    def __init__(self, name: str, record: SessionRecord) -> None:
        super().__init__()
        self._name = name
        self._record = record

    def compose(self) -> ComposeResult:
        with Vertical(id="run-report"):
            yield Static("", id="report-head")
            with Horizontal(id="report-panes"):
                with Vertical(id="report-rail"):
                    yield OptionList(id="report-nav")
                with VerticalScroll(id="report-detail"):
                    yield Static("", id="detail-pane")
            yield Static("", id="report-foot")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#report-head", Static).update(session_headline(self._name, self._record))
        self.query_one("#report-foot", Static).update(book_summary(self._record))
        nav = self.query_one("#report-nav", OptionList)
        nav.add_options(session_nav(self._record))
        nav.highlighted = first_selectable(nav)
        nav.focus()

    def action_back(self) -> None:
        self.app.pop_screen()

    @on(OptionList.OptionHighlighted, "#report-nav")
    def _browse(self, event: OptionList.OptionHighlighted) -> None:
        oid = (event.option.id or "") if event.option else ""
        detail = session_detail(self._record, oid)
        if detail is not None:
            self.query_one("#detail-pane", Static).update(detail)
            self.query_one("#report-detail", VerticalScroll).scroll_home(animate=False)


def _resolve_next_session(directory: Path) -> tuple[DeployedFund, FundState, str | None]:
    """Load the fund, replay its ledger, and ask which session is due. The
    one place the confirm modal touches the network (a daily fund asks the
    market for its closes; a minute fund's bar is read off the clock)."""
    deployed = load_deployed(directory)
    state = Ledger(directory).replay(deployed.spec.capital)
    with FDClient() as raw:
        due = next_session(CachedDataClient(raw), deployed.spec, state.last_session)
    return deployed, state, due
