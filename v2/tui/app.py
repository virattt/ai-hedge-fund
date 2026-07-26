"""The Textual app: home → builder → backtest, on the unchanged v2 engine.

Three screens:

- HomeScreen      — the brand moment: wordmark, two verbs, the model picker.
- BuilderScreen   — the fund wizard as a two-pane app: a step rail that shows
                    where you are (and what you chose), the active step on
                    the right. Esc rewinds one step.
- BacktestScreen  — pick a fund, pick a window, then warm → replay, with the
                    equity curve drawing live.

The engine is untouched: composing a FundSpec writes the same YAML the CLI
reads, and the replay is `backtest_fund` with an `on_cycle` hook. The warm
phase only warms disk caches (market data, then every agent across the
window); the sequential `backtest_fund` afterward is the source of truth
(determinism and fail-loud live in the engine, not the UI). Presentation
constants and the equity-curve renderable live in `v2.tui.shared`, shared
with the non-interactive CLI (`v2/run.py`).
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as _date
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from rich import box
from rich.console import Group
from rich.table import Table
from rich.terminal_theme import TerminalTheme
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    ContentSwitcher,
    Footer,
    Input,
    Label,
    OptionList,
    ProgressBar,
    SelectionList,
    Static,
)
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection

from v2.backtesting import FundBacktestResult, backtest_fund, rebalance_grid
from v2.data import CachedDataClient, FDClient
from v2.fund import Fund, FundSpec, StrategySpec, load_spec, load_strategy
from v2.pipeline import CycleRecord
from v2.pipeline.run_cycle import _MARK_LOOKBACK_DAYS
from v2.tui.shared import (
    DEFAULT_CAPITAL,
    DEFAULT_RISK,
    DISPLAY_NAMES,
    FUNDS_DIR,
    STRATEGY_DIR,
    UNIVERSE_PRESETS,
    VERSION,
    _BACKTEST_WEEKS,
    _CYCLE_DWELL,
    _DEFAULT_MODEL_LABEL,
    _MODELS,
    _SHORT_NAMES,
    _WARM_CHUNK,
    _agent_names,
    _fund_label,
    _render_chart,
    _strategy_kind,
    _valid_date,
)
from v2.signals import ALPHA_MODEL_REGISTRY, LLMAgent

# The palette, mirrored from app.tcss (rich styles can't read CSS variables).
GREEN = "#2bd97c"
CYAN = "#22d3ee"
RED = "#f87171"
TEXT = "#d9e6e0"
BRIGHT = "#f2f7f4"
MUTED = "#5f7268"

_CUSTOM = "custom"  # sentinel value in the strategy list for "build your own"


class HomeScreen(Screen):
    """Wordmark, two verbs, and the reasoning-model picker."""

    BINDINGS = [
        Binding("m", "cycle_model", "switch model"),
        Binding("escape", "quit_app", "quit"),
    ]

    def compose(self) -> ComposeResult:
        wordmark = "A I   H E D G E   F U N D"
        with Vertical(id="home"):
            yield Static(Text(wordmark, style=f"bold {BRIGHT}"), id="wordmark")
            yield Static(Text("━" * len(wordmark)), id="rule")
            yield Static(
                Text(
                    "design a fund · staff it with AI · time-travel it through history",
                    style=MUTED,
                ),
                id="tagline",
            )
            yield OptionList(
                Option(
                    Text.assemble(
                        ("Build a fund\n", "bold"),
                        ("compose agents into strategies; save a mandate", MUTED),
                    ),
                    id="build",
                ),
                None,
                Option(
                    Text.assemble(
                        ("Backtest a fund\n", "bold"),
                        ("time-travel a saved fund against its benchmark", MUTED),
                    ),
                    id="backtest",
                ),
                id="home-menu",
            )
            yield Static("", id="model-line")
        yield Footer()

    def on_mount(self) -> None:
        # Same seam as the CLI picker: V2_LLM_MODEL steers every agent built
        # downstream. Honor a preset from the shell; otherwise pin the default
        # so what the screen shows is what the agents use.
        preset = os.environ.get("V2_LLM_MODEL")
        self._model_index = next(
            (i for i, (_, mid) in enumerate(_MODELS) if mid == preset),
            next(i for i, (label, _) in enumerate(_MODELS)
                 if label == _DEFAULT_MODEL_LABEL),
        )
        os.environ["V2_LLM_MODEL"] = _MODELS[self._model_index][1]
        self._show_model()
        self.query_one("#home-menu", OptionList).focus()

    def action_cycle_model(self) -> None:
        self._model_index = (self._model_index + 1) % len(_MODELS)
        os.environ["V2_LLM_MODEL"] = _MODELS[self._model_index][1]
        self._show_model()

    def action_quit_app(self) -> None:
        self.app.exit()

    def _show_model(self) -> None:
        label, model_id = _MODELS[self._model_index]
        self.query_one("#model-line", Static).update(
            Text.assemble(
                ("agents reason with  ", MUTED),
                (label, f"bold {GREEN}"),
                (f"  {model_id}", MUTED),
            )
        )

    @on(OptionList.OptionSelected, "#home-menu")
    def _choose(self, event: OptionList.OptionSelected) -> None:
        if event.option.id == "build":
            self.app.push_screen(BuilderScreen())
        else:
            self.app.push_screen(BacktestScreen())


class BuilderScreen(Screen):
    """The fund wizard: a step rail on the left, the active step on the right.

    Five steps, Esc rewinds one, and the output is a FundSpec YAML — the same
    mandate the engine reads. The rail shows where you are and what you've
    already chosen at every step.
    """

    STEP_IDS = ["step-name", "step-stocks", "step-strategies",
                "step-capital", "step-cadence"]
    STEP_TITLES = ["Name", "Stocks", "Strategies", "Capital", "Cadence"]
    CADENCES = ["daily", "weekly", "monthly"]

    BINDINGS = [
        Binding("escape", "back", "back"),
        Binding("enter", "confirm_list", "continue", priority=True),
        Binding("a", "toggle_all", "toggle all"),
    ]

    def __init__(self) -> None:
        super().__init__()
        # Library sorted like the CLI: discretionary pods first, then by name.
        self._library = sorted(
            (load_strategy(p) for p in STRATEGY_DIR.glob("*.yaml")),
            key=lambda s: (_strategy_kind(s) == "systematic", s.name),
        )
        self._step = 0
        self._state: dict = {}
        self._built: tuple[FundSpec, Path] | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="builder"):
            with Vertical(id="rail"):
                yield Static(Text("BUILD A FUND", style=MUTED), classes="rail-title")
                for i in range(len(self.STEP_IDS)):
                    yield Static("", id=f"rail-{i}", classes="rail-step")
            with ContentSwitcher(initial="step-name", id="panes"):
                with Vertical(id="step-name", classes="pane"):
                    yield Label("Name your fund", classes="q")
                    yield Input(value="ai-hedge-fund", id="name-input")
                with Vertical(id="step-stocks", classes="pane"):
                    yield Label("Pick your stocks", classes="q")
                    yield Input(
                        placeholder=f"e.g. {', '.join(UNIVERSE_PRESETS[:5])}",
                        id="stocks-input",
                    )
                    yield Static("", id="stocks-preview")
                with Vertical(id="step-strategies", classes="pane"):
                    yield Label("Select your strategies", classes="q")
                    yield SelectionList(
                        Selection(
                            Text.assemble(
                                ("Build your own      ", "bold"),
                                ("pick individual agents", MUTED),
                            ),
                            _CUSTOM,
                        ),
                        *(
                            Selection(self._strategy_prompt(s), i)
                            for i, s in enumerate(self._library)
                        ),
                        id="strategy-list",
                    )
                    yield Static(
                        Text("space to toggle · a for all · enter to continue",
                             style=MUTED),
                        classes="hint",
                    )
                with Vertical(id="step-agents", classes="pane"):
                    yield Label("Staff your desk", classes="q")
                    yield SelectionList(
                        *(
                            Selection(self._agent_prompt(key, cls), key)
                            for key, cls in ALPHA_MODEL_REGISTRY.items()
                        ),
                        id="agent-list",
                    )
                    yield Static(
                        Text("space to toggle · a for all · enter to continue",
                             style=MUTED),
                        classes="hint",
                    )
                with Vertical(id="step-capital", classes="pane"):
                    yield Label("Starting capital ($)", classes="q")
                    yield Input(
                        value=f"{DEFAULT_CAPITAL:.0f}", type="number",
                        id="capital-input",
                    )
                with Vertical(id="step-cadence", classes="pane"):
                    yield Label("Rebalance cadence", classes="q")
                    yield OptionList(
                        Option(Text.assemble(
                            ("daily     ", "bold"),
                            ("news-speed — the most cycles", MUTED))),
                        Option(Text.assemble(
                            ("weekly    ", "bold"),
                            ("the fundamentals default", MUTED))),
                        Option(Text.assemble(
                            ("monthly   ", "bold"),
                            ("slow-turn — the fewest LLM calls", MUTED))),
                        id="cadence-list",
                    )
                with Vertical(id="step-done", classes="pane"):
                    yield Static("", id="done-summary")
                    yield OptionList(
                        Option("Backtest it now", id="go-backtest"),
                        None,
                        Option("Back to home", id="go-home"),
                        id="done-menu",
                    )
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_rail()
        self.query_one("#name-input", Input).focus()

    # ---- step plumbing ----------------------------------------------------

    def _pane(self) -> str:
        return self.query_one("#panes", ContentSwitcher).current or "step-name"

    def _goto(self, pane_id: str) -> None:
        self.query_one("#panes", ContentSwitcher).current = pane_id
        if pane_id in self.STEP_IDS:
            self._step = self.STEP_IDS.index(pane_id)
        focus = {
            "step-name": "#name-input",
            "step-stocks": "#stocks-input",
            "step-strategies": "#strategy-list",
            "step-agents": "#agent-list",
            "step-capital": "#capital-input",
            "step-cadence": "#cadence-list",
            "step-done": "#done-menu",
        }[pane_id]
        self.query_one(focus).focus()
        if pane_id == "step-cadence":
            picked = self._state.get("rebalance", "weekly")
            self.query_one("#cadence-list", OptionList).highlighted = (
                self.CADENCES.index(picked)
            )
        self._refresh_rail()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        # The list steps own Enter (confirm) and 'a' (toggle all); everywhere
        # else those keys belong to the focused widget (Inputs, OptionLists).
        if action in ("confirm_list", "toggle_all"):
            return self._pane() in ("step-strategies", "step-agents")
        return True

    def action_back(self) -> None:
        pane = self._pane()
        if pane == "step-name":
            self.app.pop_screen()
        elif pane == "step-agents":
            self._goto("step-strategies")
        elif pane == "step-done":
            self._goto("step-cadence")
        else:
            self._goto(self.STEP_IDS[self._step - 1])

    # ---- the five steps ---------------------------------------------------

    @on(Input.Submitted, "#name-input")
    def _submit_name(self, event: Input.Submitted) -> None:
        self._state["name"] = (
            event.value.strip().replace(" ", "-").lower() or "ai-hedge-fund"
        )
        self._goto("step-stocks")

    @on(Input.Changed, "#stocks-input")
    def _preview_stocks(self, event: Input.Changed) -> None:
        universe = self._parse_tickers(event.value)
        preview = self.query_one("#stocks-preview", Static)
        if universe:
            preview.update(Text(" · ".join(universe), style=f"bold {CYAN}"))
        else:
            preview.update("")

    @on(Input.Submitted, "#stocks-input")
    def _submit_stocks(self, event: Input.Submitted) -> None:
        universe = self._parse_tickers(event.value)
        if not universe:
            self.notify("Enter at least one ticker.", severity="error")
            return
        self._state["universe"] = universe
        self._goto("step-strategies")

    def action_toggle_all(self) -> None:
        picker_id = {"step-strategies": "#strategy-list",
                     "step-agents": "#agent-list"}[self._pane()]
        picker = self.query_one(picker_id, SelectionList)
        if len(picker.selected) == picker.option_count:
            picker.deselect_all()
        else:
            picker.select_all()

    def action_confirm_list(self) -> None:
        if self._pane() == "step-strategies":
            picked = list(self.query_one("#strategy-list", SelectionList).selected)
            if not picked:
                self.notify("Select at least one strategy.", severity="error")
                return
            self._state["strategies"] = [
                self._library[i] for i in picked if i != _CUSTOM
            ]
            if _CUSTOM in picked:
                self._goto("step-agents")
                return
        else:  # step-agents
            keys = list(self.query_one("#agent-list", SelectionList).selected)
            if not keys:
                self.notify("Pick at least one agent.", severity="error")
                return
            self._state["strategies"] = self._state["strategies"] + [
                StrategySpec(name="custom", models=[{"name": k} for k in keys])
            ]
        self._goto("step-capital")

    @on(Input.Submitted, "#capital-input")
    def _submit_capital(self, event: Input.Submitted) -> None:
        try:
            self._state["capital"] = float(event.value or DEFAULT_CAPITAL)
        except ValueError:
            self.notify("Enter a number.", severity="error")
            return
        self._goto("step-cadence")

    @on(OptionList.OptionSelected, "#cadence-list")
    def _submit_cadence(self, event: OptionList.OptionSelected) -> None:
        self._state["rebalance"] = self.CADENCES[event.option_index]
        self._finish_build()

    # ---- finish -----------------------------------------------------------

    def _finish_build(self) -> None:
        # Equal capital slices; master risk defaults. Power users edit the YAML.
        spec = FundSpec(
            name=self._state["name"],
            universe=self._state["universe"],
            strategies=[s.model_dump() for s in self._state["strategies"]],
            risk=DEFAULT_RISK,
            capital=self._state["capital"],
            rebalance=self._state["rebalance"],
        )
        FUNDS_DIR.mkdir(exist_ok=True)
        path = FUNDS_DIR / f"{spec.name}.yaml"
        path.write_text(yaml.safe_dump(spec.model_dump(), sort_keys=False))
        self._built = (spec, path)

        staff = ", ".join(s.title for s in self._state["strategies"])
        self.query_one("#done-summary", Static).update(Group(
            Text.assemble(("✓ ", f"bold {GREEN}"), ("Saved fund to ", TEXT),
                          (str(path), f"bold {BRIGHT}")),
            Text(""),
            Text.assemble(
                (spec.name, f"bold {BRIGHT}"),
                (f"  ·  {len(spec.universe)} stocks  ·  {staff}  ·  "
                 f"${spec.capital:,.0f}  ·  {spec.rebalance}", MUTED),
            ),
        ))
        self._goto("step-done")

    @on(OptionList.OptionSelected, "#done-menu")
    def _after_build(self, event: OptionList.OptionSelected) -> None:
        assert self._built is not None
        if event.option.id == "go-backtest":
            self.app.switch_screen(BacktestScreen(spec=self._built[0]))
        else:
            self.app.pop_screen()

    # ---- rendering --------------------------------------------------------

    def _refresh_rail(self) -> None:
        chosen = {
            0: self._state.get("name"),
            1: self._short_universe(),
            2: self._short_strategies(),
            3: (f"${self._state['capital']:,.0f}"
                if "capital" in self._state else None),
            4: self._state.get("rebalance"),
        }
        active = self._step if self._pane() != "step-done" else -1
        for i, title in enumerate(self.STEP_TITLES):
            row = Text()
            if chosen[i] is not None and i != active:
                row.append("✓ ", f"bold {GREEN}")
                row.append(f"{title}\n", TEXT)
                row.append(f"  {chosen[i]}", MUTED)
            elif i == active:
                row.append("› ", f"bold {GREEN}")
                row.append(title, f"bold {BRIGHT}")
            else:
                row.append("  ")
                row.append(title, MUTED)
            self.query_one(f"#rail-{i}", Static).update(row)

    def _short_universe(self) -> str | None:
        universe = self._state.get("universe")
        if not universe:
            return None
        head = ", ".join(universe[:3])
        return head + (", …" if len(universe) > 3 else "")

    def _short_strategies(self) -> str | None:
        strategies = self._state.get("strategies")
        if not strategies or self._pane() == "step-agents":
            return None
        names = ", ".join(s.title for s in strategies[:2])
        return names + (", …" if len(strategies) > 2 else "")

    @staticmethod
    def _parse_tickers(raw: str) -> list[str]:
        universe: list[str] = []
        for ticker in raw.replace(",", " ").upper().split():
            if ticker not in universe:
                universe.append(ticker)
        return universe

    @staticmethod
    def _strategy_prompt(strategy: StrategySpec) -> Text:
        staff = ", ".join(
            _SHORT_NAMES.get(m.name, m.name) for m in strategy.models
        )
        return Text.assemble((f"{strategy.title:<20}", "bold"), (staff, MUTED))

    @staticmethod
    def _agent_prompt(key: str, cls: type) -> Text:
        name = DISPLAY_NAMES.get(key, key)
        tag = "" if issubclass(cls, LLMAgent) else "  quant"
        return Text.assemble((f"{name:<24}", "bold"), (tag, MUTED))


class BacktestScreen(Screen):
    """Pick a fund → pick a window → warm → replay with a live equity curve.

    Warm-then-replay: threads only warm the disk caches (market data first,
    then every agent across the whole window); the sequential `backtest_fund`
    afterward is the source of truth.
    """

    BINDINGS = [Binding("escape", "back", "back")]

    def __init__(self, spec: FundSpec | None = None) -> None:
        super().__init__()
        self._spec = spec  # preselected by the builder's "Backtest it now"
        self._preselected = spec is not None
        self._specs: list[FundSpec] = []
        self._phase = "pick"
        self._roster_order: list[str] = []
        self._roster_state: dict[str, tuple[str, str | None]] = {}
        self._closes: dict[str, float] = {}
        self._dates: list[str] = []
        self._nav: list[float] = []
        self._n_cycles = 0

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial="bt-pick", id="bt-panes"):
            with Vertical(id="bt-pick", classes="pane"):
                yield Label("Which fund?", classes="q")
                yield OptionList(id="fund-list")
                yield Static("", id="no-funds", classes="hint")
            with Vertical(id="bt-dates", classes="pane"):
                yield Label("Time-travel window", classes="q")
                yield Static(Text("from (YYYY-MM-DD)", style=MUTED))
                yield Input(id="start-input")
                yield Static(Text("to (YYYY-MM-DD)", style=MUTED))
                yield Input(id="end-input")
            with VerticalScroll(id="bt-run", classes="pane"):
                yield Static("", id="phase-line")
                yield ProgressBar(id="warm-progress", show_eta=False,
                                  classes="hidden")
                yield Static("", id="roster", classes="hidden")
                with Horizontal(id="stats", classes="hidden"):
                    yield Static("", id="stat-nav")
                    yield Static("", id="stat-return")
                    yield Static("", id="stat-bench")
                    yield Static("", id="stat-dd")
                with Vertical(id="curve-box", classes="hidden"):
                    yield Static("", id="curve")
                yield Static("", id="cycle-line")
            with Vertical(id="bt-done", classes="pane"):
                yield Static("", id="result-summary")
                yield OptionList(
                    Option("Back to home", id="bt-home"),
                    id="bt-done-menu",
                )
        yield Footer()

    def on_mount(self) -> None:
        if self._spec is not None:
            self._begin_dates()
            return
        paths = sorted(FUNDS_DIR.glob("*.yaml"))
        self._specs = [load_spec(p) for p in paths]
        fund_list = self.query_one("#fund-list", OptionList)
        if not self._specs:
            self.query_one("#no-funds", Static).update(
                Text("No funds yet — build one first. Esc to go back.",
                     style=MUTED)
            )
            return
        fund_list.add_options([Option(_fund_label(s)) for s in self._specs])
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
        self._begin_dates()

    def _begin_dates(self) -> None:
        self._phase = "dates"
        today = _date.today()
        start = self.query_one("#start-input", Input)
        end = self.query_one("#end-input", Input)
        if not start.value:
            start.value = (today - timedelta(weeks=_BACKTEST_WEEKS)).isoformat()
        if not end.value:
            end.value = today.isoformat()
        self.query_one("#bt-panes", ContentSwitcher).current = "bt-dates"
        start.focus()

    @on(Input.Submitted, "#start-input")
    def _submit_start(self, event: Input.Submitted) -> None:
        self.query_one("#end-input", Input).focus()

    @on(Input.Submitted, "#end-input")
    def _submit_end(self, event: Input.Submitted) -> None:
        start = self.query_one("#start-input", Input).value.strip()
        end = event.value.strip()
        for value in (start, end):
            ok = _valid_date(value)
            if ok is not True:
                self.notify(ok, severity="error")
                return
        if end <= start:
            self.notify(f"End must be after {start}.", severity="error")
            return
        assert self._spec is not None
        self._phase = "run"
        self.query_one("#bt-panes", ContentSwitcher).current = "bt-run"
        self.query_one("#phase-line", Static).update(
            Text("Building the trading grid…", style=MUTED)
        )
        self._run(self._spec, start, end)

    @on(OptionList.OptionSelected, "#bt-done-menu")
    def _after_done(self, event: OptionList.OptionSelected) -> None:
        self.app.pop_screen()

    # ---- the worker (everything below the UI runs off-thread) -------------

    @work(thread=True, exclusive=True)
    def _run(self, spec: FundSpec, start: str, end: str) -> None:
        app = self.app
        try:
            with FDClient() as raw:
                bars = CachedDataClient(raw).get_prices(spec.benchmark, start, end)
            closes = {b.time[:10]: b.close for b in bars
                      if start <= b.time[:10] <= end}
            if not closes:
                raise ValueError(
                    f"no {spec.benchmark} bars in [{start}, {end}] — "
                    "cannot build the trading grid"
                )
            grid = rebalance_grid(sorted(closes), spec.rebalance)

            app.call_from_thread(self._begin_warm, spec, len(grid))
            self._warm_market(spec, grid)
            app.call_from_thread(self._begin_agents, spec)
            self._warm_agents(spec, grid)
            app.call_from_thread(self._begin_replay, spec, closes, len(grid))

            fund = Fund(spec)

            def tick(i: int, n: int, record: CycleRecord) -> None:
                started = time.time()
                app.call_from_thread(self._board_tick, record)
                dwell = _CYCLE_DWELL - (time.time() - started)
                if dwell > 0:
                    time.sleep(dwell)

            with FDClient() as raw:
                result = backtest_fund(fund, start, end, CachedDataClient(raw),
                                       on_cycle=tick)

            FUNDS_DIR.mkdir(exist_ok=True)
            stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            path = FUNDS_DIR / f"{spec.name}-backtest-{stamp}.json"
            path.write_text(result.model_dump_json(indent=2))
            app.call_from_thread(self._finish, result, path)
        except Exception as exc:  # fail loud, in the UI
            app.call_from_thread(self._fail, exc)

    def _warm_market(self, spec: FundSpec, grid: list[str]) -> None:
        """Prefetch exactly the requests the engine will make, fanned out over
        (ticker, chunk-of-dates)."""
        app = self.app
        has_agents = any(
            issubclass(ALPHA_MODEL_REGISTRY[m.name], LLMAgent)
            for s in spec.strategies for m in s.models
        )
        chunks = [
            (ticker, grid[j:j + _WARM_CHUNK])
            for ticker in spec.universe
            for j in range(0, len(grid), _WARM_CHUNK)
        ]
        bar = self.query_one("#warm-progress", ProgressBar)

        def prefetch(ticker: str, dates: list[str]) -> None:
            with FDClient() as raw:  # own client per task (requests isn't shared-safe)
                fd = CachedDataClient(raw)
                if has_agents:
                    fd.get_company_facts(ticker)
                for as_of in dates:
                    lookback = (
                        _date.fromisoformat(as_of)
                        - timedelta(days=_MARK_LOOKBACK_DAYS)
                    ).isoformat()
                    fd.get_prices(ticker, lookback, as_of)
                    if has_agents:
                        fd.get_financial_metrics(ticker, as_of,
                                                 period="ttm", limit=20)
                    app.call_from_thread(bar.advance, 1)

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(prefetch, t, ds) for t, ds in chunks]
            for future in as_completed(futures):
                future.result()  # fail loud — bad data poisons every cycle

    def _warm_agents(self, spec: FundSpec, grid: list[str]) -> None:
        """Every agent replays the window, warming prompt caches and
        model-specific data (e.g. PEAD's earnings history)."""
        app = self.app
        display = {n: DISPLAY_NAMES.get(n, n) for n in _agent_names(spec)}

        def warm(agent_name: str) -> None:
            who = display[agent_name]
            model = ALPHA_MODEL_REGISTRY[agent_name]()  # own instance per thread
            with FDClient() as raw:
                fd = CachedDataClient(raw)
                for as_of in grid:
                    for ticker in spec.universe:
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

    def _begin_warm(self, spec: FundSpec, n_grid: int) -> None:
        self.query_one("#phase-line", Static).update(Text.assemble(
            ("Loading market data", f"bold {BRIGHT}"),
            (f"  ·  {len(spec.universe)} stocks × {n_grid} "
             f"{spec.rebalance} cycles", MUTED),
        ))
        bar = self.query_one("#warm-progress", ProgressBar)
        bar.update(total=len(spec.universe) * n_grid, progress=0)
        bar.remove_class("hidden")

    def _begin_agents(self, spec: FundSpec) -> None:
        self.query_one("#phase-line", Static).update(Text.assemble(
            ("Agents replaying history", f"bold {BRIGHT}"),
            ("  ·  point-in-time: each date sees only what was filed by then",
             MUTED),
        ))
        self._roster_order = [
            DISPLAY_NAMES.get(n, n) for n in _agent_names(self._spec or spec)
        ]
        self._roster_state = {n: ("pending", None) for n in self._roster_order}
        roster = self.query_one("#roster", Static)
        roster.update(self._render_roster())
        roster.remove_class("hidden")

    def _roster_update(self, who: str, status: str, label: str | None) -> None:
        self._roster_state[who] = (status, label)
        self.query_one("#roster", Static).update(self._render_roster())

    def _render_roster(self) -> Table:
        """The v1 roster look, ported from run.py `_Roster._render`."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column()
        for name in self._roster_order:
            status, label = self._roster_state[name]
            row = Text()
            if status == "done":
                row.append("✓ ", f"bold {GREEN}")
                row.append(f"{name:<24}", "bold")
                row.append("Done", GREEN)
            elif status == "working":
                row.append("⋯ ", "yellow")
                row.append(f"{name:<24}", "bold")
                symbol, _, as_of = (label or "").partition(" · ")
                row.append("[", CYAN)
                row.append(symbol, CYAN)
                if as_of:
                    row.append(" · ", CYAN)
                    row.append(as_of, RED)  # the point-in-time cursor
                row.append("] ", CYAN)
                row.append("Analyzing", "yellow")
            else:
                row.append("⋯ ", MUTED)
                row.append(f"{name:<24}", MUTED)
                row.append("queued", MUTED)
            table.add_row(row)
        return table

    def _begin_replay(self, spec: FundSpec, closes: dict[str, float],
                      n_cycles: int) -> None:
        self._closes = closes
        self._dates = []
        self._nav = []
        self._n_cycles = n_cycles
        self.query_one("#phase-line", Static).update(Text.assemble(
            ("Replaying the fund", f"bold {BRIGHT}"),
            ("  ·  one run_cycle per rebalance date, off the warm cache",
             MUTED),
        ))
        box_widget = self.query_one("#curve-box", Vertical)
        box_widget.border_title = "equity curve"
        box_widget.border_subtitle = (
            f"[{GREEN}]──[/] fund   [{CYAN}]──[/] {spec.benchmark}"
        )
        self.query_one("#stats", Horizontal).remove_class("hidden")
        box_widget.remove_class("hidden")

    def _board_tick(self, record: CycleRecord) -> None:
        """One cycle landed: update the stat tiles, redraw the curve.
        Same math as run.py `_BacktestBoard._render`."""
        assert self._spec is not None
        self._dates.append(record.as_of)
        self._nav.append(record.nav)

        capital = self._spec.capital
        nav = self._nav[-1]
        fund_return = nav / capital - 1
        benchmark_return = (
            self._closes[self._dates[-1]] / self._closes[self._dates[0]] - 1
        )
        curve = [capital] + self._nav
        peak = curve[0]
        max_dd = 0.0
        for value in curve:
            if value > peak:
                peak = value
            max_dd = max(max_dd, (peak - value) / peak)

        def tile(label: str, value: str, style: str) -> Text:
            return Text.assemble(
                (f"{label}\n", MUTED), (value, f"bold {style}"),
                justify="center",
            )

        self.query_one("#stat-nav", Static).update(
            tile("PORTFOLIO", f"${nav:,.0f}", BRIGHT))
        self.query_one("#stat-return", Static).update(
            tile("RETURN", f"{fund_return:+.2%}",
                 GREEN if fund_return >= 0 else RED))
        self.query_one("#stat-bench", Static).update(
            tile(self._spec.benchmark, f"{benchmark_return:+.2%}",
                 GREEN if benchmark_return >= 0 else RED))
        self.query_one("#stat-dd", Static).update(
            tile("MAX DRAWDOWN", f"{max_dd:.2%}", RED))

        benchmark_curve = [capital] + [
            capital * self._closes[d] / self._closes[self._dates[0]]
            for d in self._dates
        ]
        curve_widget = self.query_one("#curve", Static)
        width = curve_widget.content_size.width or 80
        curve_widget.update(Group(
            *_render_chart(curve, benchmark_curve, capital, min(width, 100))
        ))
        self.query_one("#cycle-line", Static).update(Text(
            f"cycle {len(self._nav)}/{self._n_cycles} · {self._dates[-1]}",
            style=MUTED,
        ))

    def _finish(self, result: FundBacktestResult, path: Path) -> None:
        self._phase = "done"
        m = result.metrics
        table = Table(box=box.SQUARE, header_style="bold",
                      border_style="#1f2b25")
        for header in ("Total Return", "Annualized", "Sharpe", "Max Drawdown",
                       f"{result.benchmark} Return", "Excess"):
            table.add_column(header, justify="right")
        total_tone = f"bold {GREEN}" if m.total_return_pct >= 0 else f"bold {RED}"
        sharpe_tone = (GREEN if m.sharpe_ratio > 1
                       else "yellow" if m.sharpe_ratio > 0 else RED)
        excess_tone = f"bold {GREEN}" if m.excess_return_pct >= 0 else f"bold {RED}"
        table.add_row(
            Text(f"{m.total_return_pct:+.1%}", style=total_tone),
            f"{m.annualized_return_pct:+.1%}",
            Text(f"{m.sharpe_ratio:.2f}", style=sharpe_tone),
            Text(f"{m.max_drawdown_pct:.1%}", style=RED),
            f"{m.benchmark_return_pct:+.1%}",
            Text(f"{m.excess_return_pct:+.1%}", style=excess_tone),
        )
        self.query_one("#result-summary", Static).update(Group(
            Text.assemble(
                ("BACKTEST RESULTS  ", f"bold {BRIGHT}"),
                (result.fund, f"bold {CYAN}"),
                (f"  {result.start} → {result.end} · {result.rebalance} "
                 f"rebalance · {m.n_cycles} cycles · {m.n_orders} orders",
                 MUTED),
            ),
            Text(""),
            table,
            Text(""),
            Text.assemble(("✓ ", f"bold {GREEN}"),
                          ("Saved backtest record to ", TEXT),
                          (str(path), f"bold {BRIGHT}")),
        ))
        self.query_one("#bt-panes", ContentSwitcher).current = "bt-done"
        self.query_one("#bt-done-menu", OptionList).focus()

    def _fail(self, exc: Exception) -> None:
        self._phase = "failed"
        self.query_one("#phase-line", Static).update(Text.assemble(
            ("✗ ", f"bold {RED}"),
            (f"{type(exc).__name__}: {exc}", RED),
        ))
        self.notify(str(exc), title="Backtest failed", severity="error")


# Reused rich renderables (the equity curve, the roster) speak in ANSI color
# names — "green", "red", "cyan". This theme lands those on the brand palette
# instead of Textual's defaults, so one green exists app-wide.
_ANSI_THEME = TerminalTheme(
    (11, 16, 14),  # background
    (217, 230, 224),  # foreground
    [
        (11, 16, 14),  # black
        (248, 113, 113),  # red — losses
        (43, 217, 124),  # green — the accent
        (251, 191, 36),  # yellow — in-flight work
        (56, 189, 248),  # blue
        (192, 132, 252),  # magenta
        (34, 211, 238),  # cyan — data
        (217, 230, 224),  # white
    ],
    [
        (95, 114, 104),  # bright black
        (248, 113, 113),
        (43, 217, 124),
        (251, 191, 36),
        (56, 189, 248),
        (192, 132, 252),
        (34, 211, 238),
        (242, 247, 244),
    ],
)


class HedgeFundApp(App):
    """The v2 terminal app. One screen stack: Home → Builder / Backtest."""

    TITLE = "AI Hedge Fund"
    SUB_TITLE = f"v{VERSION}"
    CSS_PATH = "app.tcss"
    ansi_theme_dark = _ANSI_THEME

    # Textual 8.x deliberately unbinds ctrl+c from quit (it copies inside a
    # focused Input, else just hints how to quit). Users reflexively hit
    # ctrl+c to leave, so restore it: priority=True so it fires before the
    # system binding AND any focused widget, quitting from anywhere.
    BINDINGS = [Binding("ctrl+c", "quit", "quit", priority=True, show=False)]

    def on_mount(self) -> None:
        self.push_screen(HomeScreen())
