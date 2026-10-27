"""The fund wizard: name, strategies, capital, cadence (and, for paper, tickers)."""

from __future__ import annotations

from datetime import datetime, time, tzinfo
from math import isfinite
from pathlib import Path
from typing import Literal

from rich.console import Group
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    ContentSwitcher,
    Footer,
    Input,
    Label,
    OptionList,
    SelectionList,
    Static,
)
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection

from hedge_fund import paths
from hedge_fund.data.bars import bars_per_day
from hedge_fund.data.sessions import NEW_YORK
from hedge_fund.fund import (
    custom_strategy,
    format_interval,
    FundSpec,
    load_strategy,
    MIN_INTERVAL_SECONDS,
    normalize_universe,
    save_spec,
    StrategySpec,
    TradingWindow,
)
from hedge_fund.fund.spec import EARLIEST_WINDOW, LATEST_WINDOW
from hedge_fund.paper import deploy, validate_fund_name
from hedge_fund.signals import ALPHA_MODEL_REGISTRY, get_horizon_days, get_investment_approach, LLMAgent
from hedge_fund.tui.backtest import BacktestScreen
from hedge_fund.tui.funds import (
    ConfirmWipeScreen,
    fund_name_taken,
    newest_paper_universe,
    short_tickers,
    wipe_fund,
)
from hedge_fund.tui.palette import BRIGHT, GREEN, MUTED, RED, TEXT
from hedge_fund.tui.shared import (
    cadence_identity,
    DEFAULT_CAPITAL,
    DEFAULT_RISK,
    DISPLAY_NAMES,
    horizon_label,
    MODE_LABELS,
    SHORT_NAMES,
    strategy_description,
    STRATEGY_DIR,
    strategy_kind,
    UNIVERSE_PRESETS,
)

CUSTOM = "custom"  # sentinel value in the strategy list for "build your own"


_NEWS_SENTENCE = (
    "Analysts are asked again at every bar and see new headlines as they land (the news "
    "feed refreshes about every 10 minutes); a bar with nothing new re-marks the book and "
    "fills what is pending, at no extra model cost."
)


_WINDOW_NOTE = f"anywhere inside US extended hours ({EARLIEST_WINDOW}–{LATEST_WINDOW})"


_FAST_SECONDS = 10  # under this, one price request per ticker (~1s each) may not fit in a bar


class BuilderScreen(Screen):
    """The fund wizard: a step rail on the left, the active step on the right.
    Esc rewinds one step. The output is a FundSpec YAML — the same definition
    the engine reads — and, in paper mode, a deployed fund ready to run.

    Backtest mode asks four things (name, strategies, capital, cadence) and
    offers to backtest the result; what it trades is chosen per run. Paper
    mode adds the tickers as a fifth step, because a paper fund trades the
    same universe every session, and ends with "Run its first session" (or
    "Start running" for a minute fund). Choosing the minute cadence opens two
    sub-steps under Cadence, the interval and the trading window, the way
    "Build your own" opens the agent picker under Strategies.
    """

    CADENCES = ["minute", "daily", "weekly", "monthly"]
    CADENCE_TAGLINES = {
        "minute": "intraday — set the interval and trading window",
        "daily": "one decision at each close",
        "weekly": "the fundamentals default",
        "monthly": "slow-turn — one decision a month",
    }

    BINDINGS = [
        Binding("escape", "back", "back"),
        Binding("enter", "confirm_list", "continue", priority=True),
        Binding("a", "toggle_all", "toggle all"),
    ]

    def __init__(self, mode: Literal["paper", "backtest"] = "backtest") -> None:
        super().__init__()
        self.mode = mode
        self.STEP_IDS = ["step-name", "step-strategies", "step-capital", "step-cadence"]
        self.STEP_TITLES = ["Name", "Strategies", "Capital", "Cadence"]
        if mode == "paper":
            self.STEP_IDS.append("step-tickers")
            self.STEP_TITLES.append("Tickers")
        # Library sorted like the CLI: discretionary pods first, then by name.
        self._library = sorted(
            (load_strategy(p) for p in STRATEGY_DIR.glob("*.yaml")),
            key=lambda s: (strategy_kind(s) == "systematic", s.name),
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
                with Vertical(id="step-strategies", classes="pane"):
                    yield Label("Select your strategies", classes="q")
                    yield SelectionList(
                        Selection(
                            Text.assemble(
                                ("Build your own      ", "bold"),
                                ("pick individual agents", MUTED),
                            ),
                            CUSTOM,
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
                with VerticalScroll(id="step-capital", classes="pane"):
                    yield Static("", id="strategy-summary")
                    yield Label("Starting capital ($)", classes="q")
                    yield Input(
                        value=f"{DEFAULT_CAPITAL:.0f}", type="number",
                        id="capital-input",
                    )
                with Vertical(id="step-cadence", classes="pane"):
                    yield Label("Rebalance cadence", classes="q")
                    yield OptionList(
                        *(Option(Text.assemble((f"{cadence:<10}", "bold"),
                                               (self.CADENCE_TAGLINES[cadence], MUTED)))
                          for cadence in self.CADENCES),
                        id="cadence-list",
                    )
                with VerticalScroll(id="step-interval", classes="pane"):
                    yield Label("Interval between sessions (minutes)", classes="q")
                    yield Input(value="1", id="interval-input")
                    yield Static("", id="interval-line")
                    yield Static(Text(_NEWS_SENTENCE, style=MUTED), classes="hint")
                with VerticalScroll(id="step-window", classes="pane"):
                    yield Label("Trading window (ET)", classes="q")
                    with Horizontal(id="window-inputs"):
                        yield Input(value=TradingWindow().start, id="window-start-input")
                        yield Static(Text("  to  ", style=MUTED), classes="window-sep")
                        yield Input(value=TradingWindow().end, id="window-end-input")
                    yield Static("", id="window-line")
                    yield Static(
                        Text(f"New York time, {_WINDOW_NOTE}. The first and last bar fall exactly on these.",
                             style=MUTED),
                        classes="hint",
                    )
                with Vertical(id="step-tickers", classes="pane"):
                    yield Label("What does it trade?", classes="q")
                    yield Input(
                        placeholder=f"e.g. {', '.join(UNIVERSE_PRESETS[:5])}",
                        id="tickers-input",
                    )
                    yield Static(
                        Text("the same tickers every session · enter to build", style=MUTED),
                        classes="hint",
                    )
                with VerticalScroll(id="step-done", classes="pane"):
                    yield Static("", id="done-summary")
                    if self.mode == "paper":
                        yield OptionList(
                            Option("▶  Run its first session", id="go-run"),
                            None,
                            Option("Back", id="go-back"),
                            id="done-menu",
                        )
                    else:
                        yield OptionList(
                            Option("▶  Backtest it", id="go-backtest"),
                            None,
                            Option("Back", id="go-back"),
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
            "step-strategies": "#strategy-list",
            "step-agents": "#agent-list",
            "step-capital": "#capital-input",
            "step-cadence": "#cadence-list",
            "step-interval": "#interval-input",
            "step-window": "#window-start-input",
            "step-tickers": "#tickers-input",
            "step-done": "#done-menu",
        }[pane_id]
        self.query_one(focus).focus()
        if pane_id == "step-cadence":
            picked = self._state.get("rebalance", "weekly")
            self.query_one("#cadence-list", OptionList).highlighted = (
                self.CADENCES.index(picked)
            )
        if pane_id == "step-interval":
            self._refresh_interval_line()
        if pane_id == "step-window":
            self._refresh_window_line()
        if pane_id == "step-tickers":
            tickers = self.query_one("#tickers-input", Input)
            if not tickers.value:
                last = newest_paper_universe()
                if last:
                    tickers.value = ", ".join(last)
        if pane_id == "step-capital":
            self.query_one("#strategy-summary", Static).update(Group(*(
                Text(f"{s.title}: {strategy_description(s)}", style=MUTED)
                for s in self._state.get("strategies", [])
            )))
        self._refresh_rail()

        # Wrapped summaries can move controls below the viewport during layout.
        self.call_after_refresh(self.query_one(focus).scroll_visible, animate=False)

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
        elif pane == "step-capital" and self._state.get("custom_selected"):
            self._goto("step-agents")
        elif pane == "step-interval":
            self._goto("step-cadence")
        elif pane == "step-window":
            self._goto("step-interval")
        elif pane in ("step-tickers", "step-done") and self._state.get("rebalance") == "minute" \
                and (pane == "step-tickers" or self.mode == "backtest"):
            self._goto("step-window")
        elif pane == "step-done":
            self._goto(self.STEP_IDS[-1])
        else:
            self._goto(self.STEP_IDS[self._step - 1])

    # ---- the steps --------------------------------------------------------

    @on(Input.Submitted, "#name-input")
    def _submit_name(self, event: Input.Submitted) -> None:
        name = (
            event.value.strip().replace(" ", "-").lower() or "ai-hedge-fund"
        )
        try:
            validate_fund_name(name)
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return
        if fund_name_taken(name) and self._state.get("replace") != name:
            # Taken. Offer to replace it; nothing is removed until the new
            # fund is fully specified, so backing out of the wizard is free.
            self.app.push_screen(
                ConfirmWipeScreen(name, replacing=True),
                lambda ok: self._accept_name(name, replace=True) if ok else None)
            return
        self._accept_name(name, replace=self._state.get("replace") == name)

    def _accept_name(self, name: str, *, replace: bool) -> None:
        self._state["name"] = name
        self._state["replace"] = name if replace else None
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
            self._state["library_strategies"] = [
                self._library[i] for i in picked if i != CUSTOM
            ]
            self._state["custom_selected"] = CUSTOM in picked
            self._state["strategies"] = list(self._state["library_strategies"])
            if CUSTOM in picked:
                self._goto("step-agents")
                return
        else:  # step-agents
            keys = list(self.query_one("#agent-list", SelectionList).selected)
            if not keys:
                self.notify("Pick at least one agent.", severity="error")
                return
            self._state["strategies"] = self._state["library_strategies"] + [custom_strategy(keys)]
        self._goto("step-capital")

    @on(Input.Submitted, "#capital-input")
    def _submit_capital(self, event: Input.Submitted) -> None:
        try:
            capital = float(event.value or DEFAULT_CAPITAL)
            if not isfinite(capital) or capital <= 0:
                raise ValueError("capital must be positive")
            self._state["capital"] = capital
        except ValueError:
            self.notify("Enter a positive starting capital.", severity="error")
            return
        self._goto("step-cadence")

    @on(OptionList.OptionSelected, "#cadence-list")
    def _submit_cadence(self, event: OptionList.OptionSelected) -> None:
        self._state["rebalance"] = self.CADENCES[event.option_index]
        if self._state["rebalance"] == "minute":
            self._goto("step-interval")
        else:
            self._after_cadence()

    def _after_cadence(self) -> None:
        if self.mode == "paper":
            self._goto("step-tickers")
        else:
            self._finish_build()

    # ---- the minute sub-steps: interval, then window ------------------------

    def _window_draft(self) -> TradingWindow:
        """The window as typed, or the default while it does not parse yet."""
        try:
            return TradingWindow(start=self.query_one("#window-start-input", Input).value.strip(),
                                 end=self.query_one("#window-end-input", Input).value.strip())
        except ValueError:
            return self._state.get("window") or TradingWindow()

    @on(Input.Changed, "#interval-input")
    def _refresh_interval_line(self) -> None:
        text = self.query_one("#interval-input", Input).value
        try:
            minutes = parse_interval(text)
        except ValueError as exc:
            line = Text(str(exc), style=RED)
        else:
            line = Text(interval_line(minutes, self._window_draft()), style=TEXT)
            caveat = fast_caveat(minutes)
            if caveat:
                line.append(f"\n{caveat}", style=MUTED)
        self.query_one("#interval-line", Static).update(line)

    @on(Input.Submitted, "#interval-input")
    def _submit_interval(self, event: Input.Submitted) -> None:
        try:
            self._state["interval"] = parse_interval(event.value)
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return
        self._goto("step-window")

    @on(Input.Changed, "#window-start-input")
    @on(Input.Changed, "#window-end-input")
    def _refresh_window_line(self) -> None:
        start = self.query_one("#window-start-input", Input).value.strip()
        end = self.query_one("#window-end-input", Input).value.strip()
        try:
            window = TradingWindow(start=start, end=end)
        except ValueError as exc:
            line = Text(_first_reason(exc), style=RED)
        else:
            line = Text("\n".join(window_lines(window, self._state.get("interval", 1.0))), style=TEXT)
        self.query_one("#window-line", Static).update(line)

    @on(Input.Submitted, "#window-start-input")
    def _submit_window_start(self) -> None:
        self.query_one("#window-end-input", Input).focus()

    @on(Input.Submitted, "#window-end-input")
    def _submit_window_end(self) -> None:
        start = self.query_one("#window-start-input", Input).value.strip()
        end = self.query_one("#window-end-input", Input).value.strip()
        try:
            self._state["window"] = TradingWindow(start=start, end=end)
        except ValueError as exc:
            self.notify(_first_reason(exc), severity="error")
            return
        self._after_cadence()

    @on(Input.Submitted, "#tickers-input")
    def _submit_tickers(self, event: Input.Submitted) -> None:
        try:
            self._state["universe"] = normalize_universe(event.value.replace(",", " ").split())
        except ValueError:
            self.notify("Enter at least one ticker.", severity="error")
            return
        self._finish_build()

    # ---- finish -----------------------------------------------------------

    def _finish_build(self) -> None:
        # Equal capital slices; master risk defaults. Power users edit the YAML.
        intraday = self._state["rebalance"] == "minute"
        spec = FundSpec(
            schema_version=2,
            name=self._state["name"],
            strategies=[s.model_dump() for s in self._state["strategies"]],
            risk=DEFAULT_RISK,
            capital=self._state["capital"],
            rebalance=self._state["rebalance"],
            **({"interval": self._state["interval"], "window": self._state["window"]} if intraday else {}),
        )
        # The user said yes to replacing the fund that held this name: clear
        # it now, at the last moment, so an abandoned wizard costs nothing.
        replaced = self._state.get("replace") == spec.name
        if replaced:
            wipe_fund(spec.name)
        # Otherwise both modes refuse to overwrite: the name was checked on
        # the way in, but something may have taken it since. Paper mode needs
        # both the saved definition and the fund directory to be free.
        if self.mode == "paper" and (paths.PAPER_DIR / spec.name).exists():
            self.notify("A paper fund with that name already exists. Choose a different name.",
                        severity="error")
            self._goto("step-name")
            return
        try:
            path = save_spec(spec, paths.MANDATES_DIR)
        except FileExistsError:
            self.notify("A fund with that name already exists. Choose a different name.",
                        severity="error")
            self._goto("step-name")
            return
        self._built = (spec, path)

        staff = ", ".join(s.title for s in self._state["strategies"])
        identity = Text.assemble(
            (spec.name, f"bold {BRIGHT}"),
            (f"  ·  {staff}  ·  ${spec.capital:,.0f}  ·  {cadence_identity(spec)}", MUTED),
        )
        if replaced:
            self.notify(f"Replaced the previous {spec.name}.", severity="warning")
        if self.mode == "paper":
            universe = self._state["universe"]
            directory = deploy(spec.name, spec, universe, root=paths.PAPER_DIR)
            menu = self.query_one("#done-menu", OptionList)
            menu.clear_options()
            menu.add_options([
                Option("▶  Run its first session", id="go-run"),
                None,
                Option("Back", id="go-back"),
            ])
            menu.highlighted = 0
            first = (
                f"Its first session marks the book at the {'current bar' if intraday else 'latest completed close'} and "
                f"makes the first decision; the {'next bar' if intraday else 'session after'} executes it. "
                "Run it a session at a time, or leave a runner on it from the paper screen (space)."
            )
            self.query_one("#done-summary", Static).update(Group(
                Text.assemble((spec.name, f"bold {GREEN}"), (" is live.", f"bold {BRIGHT}")),
                Text(""),
                identity,
                Text(" ".join(universe), style=MUTED),
                Text(""),
                Text.assemble(("✓ ", f"bold {GREEN}"), ("Ledger and book at ", MUTED),
                              (str(directory), MUTED)),
                Text.assemble(("✓ ", f"bold {GREEN}"), ("Definition saved to ", MUTED),
                              (str(path), MUTED)),
                Text(""),
                Text(first, style=MUTED),
            ))
        else:
            self.query_one("#done-summary", Static).update(Group(
                Text.assemble(("✓ ", f"bold {GREEN}"), ("Saved fund to ", TEXT),
                              (str(path), f"bold {BRIGHT}")),
                Text(""),
                identity,
                Text(""),
                Text("Pick the tickers and the window when you backtest it.", style=MUTED),
                *(Text(f"{s.title}: {strategy_description(s)}", style=MUTED) for s in spec.strategies),
            ))
        self._goto("step-done")

    @on(OptionList.OptionSelected, "#done-menu")
    def _after_build(self, event: OptionList.OptionSelected) -> None:
        # Imported here, not at the top: the paper screen opens this builder.
        from hedge_fund.tui.paper import PaperScreen
        assert self._built is not None
        spec = self._built[0]
        if event.option.id == "go-backtest":
            self.app.switch_screen(BacktestScreen(spec))
        elif event.option.id == "go-run":
            self.app.switch_screen(PaperScreen(select=spec.name, run=True))
        else:
            self.app.pop_screen()

    # ---- rendering --------------------------------------------------------

    def _refresh_rail(self) -> None:
        chosen = {
            0: self._state.get("name"),
            1: self._short_strategies(),
            2: (f"${self._state['capital']:,.0f}"
                if "capital" in self._state else None),
            3: self._short_cadence(),
            4: (short_tickers(self._state["universe"], 3)
                if "universe" in self._state else None),
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

    def _short_strategies(self) -> str | None:
        strategies = self._state.get("strategies")
        if not strategies or self._pane() == "step-agents":
            return None
        names = ", ".join(s.title for s in strategies[:2])
        return names + (", …" if len(strategies) > 2 else "")

    def _short_cadence(self) -> str | None:
        cadence = self._state.get("rebalance")
        if cadence != "minute":
            return cadence
        if self._pane() in ("step-interval", "step-window") or "window" not in self._state:
            return None  # still being set
        seconds = int(round(self._state["interval"] * 60))
        return f"every {format_interval(seconds)}\n  {self._state['window'].label}"

    @staticmethod
    def _strategy_prompt(strategy: StrategySpec) -> Text:
        staff = ", ".join(
            SHORT_NAMES.get(m.name, m.name) for m in strategy.models
        )
        return Text.assemble((f"{strategy.title:<20}", "bold"), (f"{MODE_LABELS[strategy.blend.mode]} · {staff}", MUTED))

    @staticmethod
    def _agent_prompt(key: str, cls: type) -> Text:
        name = DISPLAY_NAMES.get(key, key)
        tag = "" if issubclass(cls, LLMAgent) else "  quant"
        horizon = horizon_label(get_horizon_days(key))
        return Text.assemble((f"{name:<24}", "bold"),
                             (f"{MODE_LABELS[get_investment_approach(key)]} · {horizon} view{tag}", MUTED))


def parse_interval(text: str) -> float:
    """Minutes between bars from what was typed; ValueError says what is wrong."""
    try:
        minutes = float(text.strip())
    except ValueError:
        raise ValueError("Enter the interval in minutes: 1, 5, or 0.5 for every 30 seconds.") from None
    if not isfinite(minutes) or minutes <= 0:
        raise ValueError("Enter the interval in minutes: 1, 5, or 0.5 for every 30 seconds.")
    if round(minutes * 60) < MIN_INTERVAL_SECONDS:
        raise ValueError(
            f"The shortest interval is {MIN_INTERVAL_SECONDS}s: sessions are stamped to the second. "
            "Enter 0.0167 for every second."
        )
    return minutes


def interval_line(minutes: float, window: TradingWindow) -> str:
    """`every 1m · 09:30–16:00 ET · 391 sessions a day`"""
    seconds = int(round(minutes * 60))
    return f"every {format_interval(seconds)} · {window.label} · {bars_per_day(seconds, window):,} sessions a day"


def fast_caveat(minutes: float) -> str | None:
    """What a very short interval costs: a price request per ticker takes
    about a second, so bars the fetch cannot reach in time are skipped and
    logged as gaps. None at intervals that comfortably fit."""
    seconds = int(round(minutes * 60))
    if seconds >= _FAST_SECONDS:
        return None
    return (f"Under {_FAST_SECONDS}s a bar may not fit its price requests (about a second per ticker); "
            "bars the fund cannot reach in time are skipped and logged as gaps.")


def window_lines(window: TradingWindow, minutes: float = 1.0, *,
                  today: datetime | None = None, local_zone: tzinfo | None = None) -> list[str]:
    """The window as it will run, plus the same hours in the user's own zone
    when that differs from New York (times are always stored in ET)."""
    lines = [interval_line(minutes, window)]
    today = today or datetime.now(NEW_YORK)
    local = local_zone or datetime.now().astimezone().tzinfo
    start_ny = datetime.combine(today.date(), time(*map(int, window.start.split(":"))), tzinfo=NEW_YORK)
    end_ny = datetime.combine(today.date(), time(*map(int, window.end.split(":"))), tzinfo=NEW_YORK)
    start_local, end_local = start_ny.astimezone(local), end_ny.astimezone(local)
    if (start_local.hour, start_local.minute) != (start_ny.hour, start_ny.minute) \
            or (end_local.hour, end_local.minute) != (end_ny.hour, end_ny.minute):
        day_shift = (end_local.date() - end_ny.date()).days
        suffix = {1: " (the next day)", -1: " (the day before)"}.get(day_shift, "")
        lines.append(f"that is {start_local:%H:%M}–{end_local:%H:%M} {start_local:%Z} where you are{suffix}")
    return lines


def _first_reason(exc: Exception) -> str:
    """A pydantic ValidationError's first message, without the field frame."""
    errors = getattr(exc, "errors", None)
    if callable(errors):
        details = errors()
        if details:
            return str(details[0]["msg"]).removeprefix("Value error, ")
    return str(exc)
