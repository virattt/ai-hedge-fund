"""Backtesting: pick a mandate and a window, warm the caches, replay with a live board."""

from __future__ import annotations

from concurrent.futures import as_completed, ThreadPoolExecutor
from datetime import date as _date
from datetime import timedelta
from pathlib import Path

from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    ContentSwitcher,
    Footer,
    Input,
    Label,
    OptionList,
    ProgressBar,
    Static,
)
from textual.widgets.option_list import Option

from hedge_fund import paths
from hedge_fund.backtesting import (
    backtest_fund,
    build_schedule,
    DailyValuation,
    FundBacktestResult,
    performance_metrics,
)
from hedge_fund.backtesting.research import last_universe, save_result
from hedge_fund.brokers import Fill
from hedge_fund.data import CachedDataClient, FDClient
from hedge_fund.fund import discover_funds, Fund, FundSpec, normalize_universe
from hedge_fund.pipeline import CycleRecord, mark_lookback_start
from hedge_fund.scorecard import score
from hedge_fund.signals import ALPHA_MODEL_REGISTRY, LLMAgent
from hedge_fund.tui.home import demand_run_keys, HomeScreen
from hedge_fund.tui.palette import BRIGHT, CYAN, GREEN, MUTED, RED, TEXT
from hedge_fund.tui.report import roster_table, tape_table
from hedge_fund.tui.scorecard_view import analyst_table, strategy_table
from hedge_fund.tui.shared import (
    agent_names,
    BACKTEST_WEEKS,
    DISPLAY_NAMES,
    fund_label,
    render_area_chart,
    UNIVERSE_PRESETS,
    valid_date,
    WARM_CHUNK,
)
from hedge_fund.tui.widgets import first_selectable, StatTiles


class BacktestScreen(Screen):
    """Pick a mandate → pick a window → warm → replay with a live equity curve.

    Warm-then-replay: threads only warm the disk caches (market data first,
    then every agent across the whole window); the sequential `backtest_fund`
    afterward is the source of truth.
    """

    BINDINGS = [Binding("escape", "back", "back")]

    def __init__(self, spec: FundSpec | None = None) -> None:
        super().__init__()
        self._spec = spec  # preselected by the mandate picker or the builder
        self._preselected = spec is not None
        self._specs: list[FundSpec | None] = []
        self._phase = "pick"
        self._roster_order: list[str] = []
        self._roster_state: dict[str, tuple[str, str | None]] = {}
        self._closes: dict[str, float] = {}
        self._dates: list[str] = []
        self._nav: list[float] = []
        self._n_cycles = 0
        self._tape: list[tuple[str, Fill, int]] = []  # (as_of, fill, shares after)

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial="bt-pick", id="bt-panes"):
            with Vertical(id="bt-pick", classes="pane"):
                yield Label("Which mandate?", classes="q")
                yield OptionList(id="fund-list")
                yield Static("", id="no-funds", classes="hint")
            with Vertical(id="bt-dates", classes="pane"):
                yield Label("Time-travel window", classes="q")
                yield Static(Text("tickers to trade", style=MUTED))
                yield Input(
                    placeholder=f"e.g. {', '.join(UNIVERSE_PRESETS[:5])}",
                    id="bt-tickers",
                )
                yield Static(Text("from (YYYY-MM-DD)", style=MUTED))
                yield Input(id="start-input")
                yield Static(Text("to (YYYY-MM-DD)", style=MUTED))
                yield Input(id="end-input")
            with VerticalScroll(id="bt-run", classes="pane"):
                yield Static("", id="phase-line")
                yield ProgressBar(id="warm-progress", show_eta=False,
                                  classes="hidden")
                yield Static("", id="roster", classes="hidden")
                yield StatTiles(id="stats", classes="hidden")
                with Vertical(id="curve-box", classes="hidden"):
                    yield Static("", id="curve")
                with Vertical(id="tape-box", classes="hidden"):
                    yield Static("", id="tape")
                yield Static("", id="cycle-line")
                yield Static("", id="result-summary", classes="hidden")
                yield Static("", id="scorecard", classes="hidden")
                yield OptionList(
                    Option("Back to home", id="bt-home"),
                    id="bt-done-menu",
                    classes="hidden",
                )
        yield Footer()

    def on_mount(self) -> None:
        if self._spec is not None:
            self._begin_dates()
            return
        entries = discover_funds(paths.MANDATES_DIR)
        self._specs = [entry.spec for entry in entries]
        fund_list = self.query_one("#fund-list", OptionList)
        if not self._specs:
            self.query_one("#no-funds", Static).update(
                Text("No mandates yet — build one first. Esc to go back.",
                     style=MUTED)
            )
            return
        for entry in entries:
            if entry.spec is None:
                fund_list.add_option(Option(Text(f"{entry.path.name} — Unavailable\n{entry.error}"), disabled=True))
            else:
                fund_list.add_option(Option(Text(fund_label(entry.spec))))
        fund_list.highlighted = first_selectable(fund_list)
        fund_list.focus()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        # No stepping out mid-run: the worker threads are warming caches and
        # replaying the fund; leaving the screen would orphan them.
        if action == "back" and self._phase == "run":
            return False
        return True

    def action_back(self) -> None:
        pane = self.query_one("#bt-panes", ContentSwitcher).current
        if pane == "bt-dates" and not self._preselected:
            self._phase = "pick"
            self.query_one("#bt-panes", ContentSwitcher).current = "bt-pick"
            self.query_one("#fund-list", OptionList).focus()
        else:
            self.app.pop_screen()

    @on(OptionList.OptionSelected, "#fund-list")
    def _pick_fund(self, event: OptionList.OptionSelected) -> None:
        self._spec = self._specs[event.option_index]
        if self._spec is None:
            return
        self._begin_dates()

    def _begin_dates(self) -> None:
        assert self._spec is not None
        self._phase = "dates"
        today = _date.today()
        tickers = self.query_one("#bt-tickers", Input)
        start = self.query_one("#start-input", Input)
        end = self.query_one("#end-input", Input)
        if not tickers.value:
            last = last_universe(self._spec.name)
            if last:
                tickers.value = ", ".join(last)
        if not start.value:
            start.value = (today - timedelta(weeks=BACKTEST_WEEKS)).isoformat()
        if not end.value:
            end.value = today.isoformat()
        self.query_one("#bt-panes", ContentSwitcher).current = "bt-dates"
        tickers.focus()

    @on(Input.Submitted, "#bt-tickers")
    def _submit_tickers(self, event: Input.Submitted) -> None:
        self.query_one("#start-input", Input).focus()

    @on(Input.Submitted, "#start-input")
    def _submit_start(self, event: Input.Submitted) -> None:
        self.query_one("#end-input", Input).focus()

    @on(Input.Submitted, "#end-input")
    def _submit_end(self, event: Input.Submitted) -> None:
        assert self._spec is not None
        start = self.query_one("#start-input", Input).value.strip()
        end = event.value.strip()
        for value in (start, end):
            ok = valid_date(value)
            if ok is not True:
                self.notify(ok, severity="error")
                return
        if end <= start:
            self.notify(f"End must be after {start}.", severity="error")
            return
        try:
            universe = normalize_universe(
                self.query_one("#bt-tickers", Input).value.replace(",", " ").split())
        except ValueError:
            self.notify("Enter at least one ticker.", severity="error")
            self.query_one("#bt-tickers", Input).focus()
            return
        assert self._spec is not None

        def resume() -> None:
            if demand_run_keys(self.app, resume):
                self._begin(start, end, universe)
        resume()

    def _begin(self, start: str, end: str, universe: list[str]) -> None:
        assert self._spec is not None
        self._phase = "run"
        self.query_one("#bt-panes", ContentSwitcher).current = "bt-run"
        self.query_one("#phase-line", Static).update(
            Text("Building the trading grid…", style=MUTED)
        )
        self._run(self._spec, start, end, universe)

    @on(OptionList.OptionSelected, "#bt-done-menu")
    def _after_done(self, event: OptionList.OptionSelected) -> None:
        # "Back to home" means home, however deep the stack got here.
        while not isinstance(self.app.screen, HomeScreen):
            self.app.pop_screen()

    # ---- the worker (everything below the UI runs off-thread) -------------

    @work(thread=True, exclusive=True)
    def _run(self, spec: FundSpec, start: str, end: str,
             universe: list[str]) -> None:
        app = self.app
        try:
            with FDClient() as raw:
                schedule = build_schedule(CachedDataClient(raw), spec.benchmark, start, end, spec.rebalance)
            grid = schedule.assessment_dates
            app.call_from_thread(self._begin_warm, spec, universe, len(grid))
            self._warm_market(spec, universe, grid)
            app.call_from_thread(self._begin_agents, spec)
            self._warm_agents(spec, universe, grid)
            app.call_from_thread(self._begin_replay, spec, schedule.closes, len(schedule.closes))

            fund = Fund(spec, blind=True)  # same prompts _warm_agents cached

            def tick(i: int, n: int, record: CycleRecord) -> None:
                app.call_from_thread(self._board_tick, record)

            def valuation(i: int, n: int, value: DailyValuation) -> None:
                app.call_from_thread(self._board_valuation, value)

            with FDClient() as raw:
                result = backtest_fund(fund, start, end, CachedDataClient(raw),
                                       universe, on_cycle=tick, on_valuation=valuation)

            path = save_result(result)  # where `aihf backtest` saves too; the mandate picker reads it
            app.call_from_thread(self._finish, result, path)
        except Exception as exc:  # fail loud, in the UI
            app.call_from_thread(self._fail, exc)

    def _warm_market(self, spec: FundSpec, universe: list[str],
                     grid: list[str]) -> None:
        """Prefetch exactly the requests the engine will make, fanned out over
        (ticker, chunk-of-dates)."""
        app = self.app
        has_agents = any(
            issubclass(ALPHA_MODEL_REGISTRY[m.name], LLMAgent)
            for s in spec.strategies for m in s.models
        )
        chunks = [
            (ticker, grid[j:j + WARM_CHUNK])
            for ticker in universe
            for j in range(0, len(grid), WARM_CHUNK)
        ]
        bar = self.query_one("#warm-progress", ProgressBar)

        def prefetch(ticker: str, dates: list[str]) -> None:
            with FDClient() as raw:  # own client per task (requests isn't shared-safe)
                fd = CachedDataClient(raw)
                if has_agents:
                    fd.get_company_facts(ticker)
                for as_of in dates:
                    fd.get_prices(ticker, mark_lookback_start(as_of), as_of)
                    if has_agents:
                        fd.get_financial_metrics(ticker, as_of,
                                                 period="ttm", limit=20)
                    app.call_from_thread(bar.advance, 1)

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(prefetch, t, ds) for t, ds in chunks]
            for future in as_completed(futures):
                future.result()  # fail loud — bad data poisons every cycle

    def _warm_agents(self, spec: FundSpec, universe: list[str],
                     grid: list[str]) -> None:
        """Every agent replays the window, warming prompt caches and
        model-specific data (e.g. PEAD's earnings history).

        LLM agents run blind, as they do in the backtest itself: a warm with
        a different prompt would fill the cache with entries the backtest
        never looks up."""
        app = self.app
        display = {n: DISPLAY_NAMES.get(n, n) for n in agent_names(spec)}

        def warm(agent_name: str) -> None:
            who = display[agent_name]
            cls = ALPHA_MODEL_REGISTRY[agent_name]  # own instance per thread
            model = cls(blind=True) if issubclass(cls, LLMAgent) else cls()
            with FDClient() as raw:
                fd = CachedDataClient(raw)
                for as_of in grid:
                    for ticker in universe:
                        app.call_from_thread(
                            self._roster_update, who, "working",
                            f"{ticker} · {as_of}",
                        )
                        try:
                            model.predict(ticker, as_of, fd)
                        except Exception:
                            pass  # best-effort warm; backtest_fund is the truth
            app.call_from_thread(self._roster_update, who, "done", None)

        names = list(display)
        with ThreadPoolExecutor(max_workers=min(8, len(names))) as pool:
            for future in as_completed([pool.submit(warm, n) for n in names]):
                future.result()

    # ---- UI-thread updates ------------------------------------------------

    def _begin_warm(self, spec: FundSpec, universe: list[str],
                    n_grid: int) -> None:
        self.query_one("#phase-line", Static).update(Text.assemble(
            ("Loading market data", f"bold {BRIGHT}"),
            (f"  ·  {len(universe)} stocks × {n_grid} "
             f"{spec.rebalance} cycles", MUTED),
        ))
        bar = self.query_one("#warm-progress", ProgressBar)
        bar.update(total=len(universe) * n_grid, progress=0)
        bar.remove_class("hidden")

    def _begin_agents(self, spec: FundSpec) -> None:
        self.query_one("#phase-line", Static).update(Text.assemble(
            ("Agents replaying history", f"bold {BRIGHT}"),
            ("  ·  point-in-time: each date sees only what was filed by then",
             MUTED),
        ))
        self._roster_order = [
            DISPLAY_NAMES.get(n, n) for n in agent_names(self._spec or spec)
        ]
        self._roster_state = {n: ("pending", None) for n in self._roster_order}
        roster = self.query_one("#roster", Static)
        roster.update(self._render_roster())
        roster.remove_class("hidden")

    def _roster_update(self, who: str, status: str, label: str | None) -> None:
        self._roster_state[who] = (status, label)
        self.query_one("#roster", Static).update(self._render_roster())

    def _render_roster(self) -> Table:
        return roster_table(self._roster_order, self._roster_state)

    def _begin_replay(self, spec: FundSpec, closes: dict[str, float],
                      n_cycles: int) -> None:
        self._closes = closes
        self._dates = []
        self._nav = []
        self._n_cycles = n_cycles
        self._tape = []
        self.query_one("#phase-line", Static).update(Text.assemble(
            ("Replaying the fund", f"bold {BRIGHT}"),
            ("  ·  daily valuations and next-close execution",
             MUTED),
        ))
        box_widget = self.query_one("#curve-box", Vertical)
        box_widget.border_title = "equity curve"
        box_widget.border_subtitle = (
            f"[{GREEN}]██[/] fund   [{CYAN}]──[/] {spec.benchmark}"
        )
        tape_box = self.query_one("#tape-box", Vertical)
        tape_box.border_title = "trades (newest first)"
        self.query_one("#stats", StatTiles).remove_class("hidden")
        box_widget.remove_class("hidden")
        tape_box.remove_class("hidden")

    def _board_tick(self, record: CycleRecord) -> None:
        for fill in record.fills:
            self._tape.append((record.execution_as_of or record.as_of, fill,
                               record.positions.get(fill.ticker, 0)))
        self.query_one("#tape", Static).update(tape_table(self._tape))

    def _board_valuation(self, value: DailyValuation) -> None:
        assert self._spec is not None
        self._dates.append(value.as_of)
        self._nav.append(value.nav)
        capital = self._spec.capital
        benchmark_curve = [capital * self._closes[d] / self._closes[self._dates[0]]
                           for d in self._dates]
        metrics = performance_metrics(capital, self._dates, self._nav, benchmark_curve, [])
        self._update_stats(value.nav, metrics.total_return_pct, metrics.benchmark_return_pct,
                           metrics.excess_return_pct, metrics.sharpe_ratio, metrics.max_drawdown_pct)
        curve_widget = self.query_one("#curve", Static)
        width = curve_widget.content_size.width or 80
        curve_widget.update(Group(*render_area_chart(
            self._nav, benchmark_curve, capital, min(width, 100))))
        self.query_one("#cycle-line", Static).update(Text(
            f"session {len(self._nav)}/{self._n_cycles} · {value.as_of}", style=MUTED))

    def _update_stats(self, nav: float, fund_return: float,
                      benchmark_return: float, excess: float,
                      sharpe: float, max_dd: float) -> None:
        """One row of running tallies, live during the replay and refreshed
        with the engine's authoritative numbers at the end."""
        assert self._spec is not None
        self.query_one("#stats", StatTiles).update(
            self._spec.benchmark, nav, fund_return, benchmark_return, excess, sharpe, max_dd)

    def _finish(self, result: FundBacktestResult, path: Path) -> None:
        self._phase = "done"
        m = result.metrics
        # The graph is the trophy: stay on the run pane, land the header and
        # receipt around it, and let the stat tiles carry the final numbers.
        self.query_one("#warm-progress", ProgressBar).add_class("hidden")
        self.query_one("#roster", Static).add_class("hidden")
        self.query_one("#phase-line", Static).update(Text.assemble(
            ("BACKTEST RESULTS  ", f"bold {BRIGHT}"),
            (result.fund, f"bold {CYAN}"),
            (f"  {result.start} → {result.end} · {result.rebalance} "
             f"rebalance · {m.n_cycles} executed cycles · {m.n_orders} orders · "
             f"{m.annualized_return_pct:+.1%} annualized",
             MUTED),
        ))
        self._update_stats(
            result.nav[-1],
            m.total_return_pct, m.benchmark_return_pct,
            m.excess_return_pct, m.sharpe_ratio, m.max_drawdown_pct,
        )
        self.query_one("#result-summary", Static).update(
            Text.assemble(("✓ ", f"bold {GREEN}"),
                          ("Saved backtest record to ", TEXT),
                          (str(path), f"bold {BRIGHT}")))
        self.query_one("#result-summary", Static).remove_class("hidden")
        card = score(result.records)
        scorecard = self.query_one("#scorecard", Static)
        scorecard.update(Group(analyst_table(card), strategy_table(card)))
        scorecard.remove_class("hidden")
        menu = self.query_one("#bt-done-menu", OptionList)
        menu.remove_class("hidden")
        menu.focus()

    def _fail(self, exc: Exception) -> None:
        self._phase = "failed"
        self.query_one("#phase-line", Static).update(Text.assemble(
            ("✗ ", f"bold {RED}"),
            (f"{type(exc).__name__}: {exc}", RED),
        ))
        self.notify(str(exc), title="Backtest failed", severity="error")
