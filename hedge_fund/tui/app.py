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
constants and the equity-curve renderable live in `hedge_fund.tui.shared`, shared
with the non-interactive CLI (`hedge_fund/run.py`).
"""

from __future__ import annotations

import json
import os
import time
from math import sqrt
from statistics import mean, stdev
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
from textual.screen import ModalScreen, Screen
from textual.timer import Timer
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

from hedge_fund.backtesting import FundBacktestResult, backtest_fund, rebalance_grid
from hedge_fund.backtesting.fund import _PERIODS_PER_YEAR
from hedge_fund.brokers import Fill, SimBroker
from hedge_fund.data import CachedDataClient, FDClient
from hedge_fund.fund import (
    Fund,
    FundSpec,
    StrategySpec,
    load_spec,
    load_strategy,
    normalize_universe,
)
from hedge_fund.models import Signal
from hedge_fund.pipeline import CycleRecord, run_cycle
from hedge_fund.pipeline.run_cycle import _MARK_LOOKBACK_DAYS
from hedge_fund.tui.shared import (
    DEFAULT_CAPITAL,
    DEFAULT_RISK,
    DISPLAY_NAMES,
    FUNDS_DIR,
    STRATEGY_DIR,
    UNIVERSE_PRESETS,
    VERSION,
    _BACKTEST_WEEKS,
    _BOARD_REFRESH,
    _CYCLE_DWELL,
    _DEFAULT_MODEL_LABEL,
    _SHORT_NAMES,
    _WARM_CHUNK,
    _agent_names,
    _fund_label,
    _render_area_chart,
    _strategy_kind,
    _valid_date,
    ensure_mandates_dir,
    is_supported,
    load_api_models,
)
from hedge_fund.llm import ThesisStream, make_llm, provider_for
from hedge_fund.tui.keys import (
    ENV_PATH,
    PROVIDER_ENV_VARS,
    apply_credentials,
    masked,
    missing_key,
    save_credential,
)
from hedge_fund.signals import ALPHA_MODEL_REGISTRY, LLMAgent

# The palette, mirrored from app.tcss (rich styles can't read CSS variables).
GREEN = "#2bd97c"
CYAN = "#22d3ee"
RED = "#f87171"
TEXT = "#d9e6e0"
BRIGHT = "#f2f7f4"
MUTED = "#5f7268"

_CUSTOM = "custom"  # sentinel value in the strategy list for "build your own"


class HomeScreen(Screen):
    """The clean landing: wordmark, two verbs, the reasoning-model picker.
    Run an existing fund (→ pick a saved fund) or build a new one. Backtest
    is a side option once a fund is in hand, not a top-level verb.
    """

    BINDINGS = [
        Binding("m", "pick_model", "switch model"),
        Binding("k", "set_key", "api key"),
        Binding("escape", "quit_app", "quit"),
    ]

    def compose(self) -> ComposeResult:
        wordmark = "A I   H E D G E   F U N D"
        with Vertical(id="home"):
            yield Static(Text(wordmark, style=f"bold {BRIGHT}"), id="wordmark")
            yield Static(Text("━" * len(wordmark)), id="rule")
            yield OptionList(
                Option(
                    Text.assemble(
                        ("Run an existing fund\n", "bold"),
                        ("pick a saved fund and run it as of today", MUTED)),
                    id="run"),
                None,
                Option(
                    Text.assemble(
                        ("Build a new fund\n", "bold"),
                        ("compose agents into strategies from scratch", MUTED)),
                    id="build"),
                id="home-menu",
            )
            yield Static("", id="model-line")
        yield Footer()

    def on_mount(self) -> None:
        # Same seam as the CLI picker: HEDGE_FUND_LLM_MODEL steers every agent built
        # downstream. Honor a preset from the shell — even an unlisted one, so
        # a model newer than the registry still works — otherwise pin the
        # default, so what the screen shows is what the agents use.
        models = load_api_models()
        preset = os.environ.get("HEDGE_FUND_LLM_MODEL")
        known = {mid for _, mid, _ in models}
        self._model_id = preset if preset in known else next(
            (mid for label, mid, _ in models if label == _DEFAULT_MODEL_LABEL),
            models[0][1],
        )
        os.environ["HEDGE_FUND_LLM_MODEL"] = self._model_id
        self._show_model()
        self.query_one("#home-menu", OptionList).focus()

    def action_pick_model(self) -> None:
        self.app.push_screen(ModelPickerScreen(self._model_id), self._set_model)

    def _set_model(self, model_id: str | None) -> None:
        if model_id is None:
            return
        self._model_id = model_id
        os.environ["HEDGE_FUND_LLM_MODEL"] = model_id
        self._show_model()

    def action_set_key(self) -> None:
        """Set the key for the selected model's provider, before a run needs
        it. Replacing a key that already works is allowed on purpose."""
        provider = provider_for(self._model_id)
        if provider is None:
            self.notify("Model is not in the registry — set its key by hand.",
                        severity="warning")
            return
        env_var = PROVIDER_ENV_VARS.get(provider)
        if env_var is None:
            self.notify(f"No key is needed for {provider}.")
            return
        self.app.push_screen(KeyPromptScreen(provider, env_var),
                             lambda _: self._show_model())

    def action_quit_app(self) -> None:
        self.app.exit()

    def _show_model(self) -> None:
        label = next((name for name, mid, _ in load_api_models()
                      if mid == self._model_id), self._model_id)
        self.query_one("#model-line", Static).update(
            Text.assemble(
                ("agents reason with  ", MUTED),
                (label, f"bold {GREEN}"),
                (f"  {self._model_id}", MUTED),
                ("   ·  m to switch", MUTED),
            )
        )

    @on(OptionList.OptionSelected, "#home-menu")
    def _choose(self, event: OptionList.OptionSelected) -> None:
        if event.option.id == "run":
            self.app.push_screen(FundSelectScreen())
        elif event.option.id == "build":
            self.app.push_screen(BuilderScreen())


class KeyPromptScreen(ModalScreen[bool]):
    """Ask for the one key a provider needs, and offer to remember it.

    Returns True if a key is now in the environment. The input is masked and
    the value is never echoed back — the confirmation shows a masked form.
    """

    BINDINGS = [Binding("escape", "cancel", "cancel")]

    def __init__(self, provider: str, env_var: str) -> None:
        super().__init__()
        self._provider = provider
        self._env_var = env_var

    def compose(self) -> ComposeResult:
        with Vertical(id="keyprompt"):
            yield Static(Text.assemble(
                (f"{self._provider} API key needed", f"bold {BRIGHT}")),
                id="key-q")
            yield Static(Text.assemble(
                ("The fund cannot run without it. Paste it below and it "
                 "is saved to\n", MUTED),
                (str(ENV_PATH), TEXT),
                ("\nwhich is owner-read-only and loaded automatically on "
                 "every start.", MUTED)),
                id="key-blurb")
            yield Input(password=True, placeholder=self._env_var, id="key-input")
            yield Static(Text.assemble(
                ("enter", f"bold {GREEN}"), ("  save and continue   ", MUTED),
                ("esc", f"bold {BRIGHT}"), ("  cancel", MUTED)),
                classes="hint")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#key-input", Input).focus()

    @on(Input.Submitted, "#key-input")
    def _save(self, event: Input.Submitted) -> None:
        key = event.value.strip()
        if not key:
            self.notify("No key entered", severity="warning")
            return
        path = save_credential(self._env_var, key)
        self.notify(f"Saved {self._env_var} ({masked(key)}) to {path}")
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


def _demand_run_keys(app, resume) -> bool:
    """True if every key a run needs is in the environment: the data key
    first, then the selected model's LLM key. Otherwise open the prompt for
    the first missing one; each save calls ``resume``, which should re-enter
    this gate so the next missing key is asked for in turn. Ask here, not
    deep inside a worker thread: a run that dies on a missing credential has
    already spent minutes of warming."""
    if not os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        app.push_screen(
            KeyPromptScreen("Financial Datasets",
                            "FINANCIAL_DATASETS_API_KEY"),
            lambda saved: resume() if saved else None)
        return False
    provider = provider_for(os.environ.get("HEDGE_FUND_LLM_MODEL", ""))
    env_var = missing_key(provider) if provider else None
    if env_var is None:
        return True
    app.push_screen(KeyPromptScreen(provider, env_var),
                    lambda saved: resume() if saved else None)
    return False


class ModelPickerScreen(ModalScreen[str | None]):
    """Every model in the repo's registry, grouped by provider.

    Providers v2 has no client for are shown but not selectable — listing
    them is honest about what exists, and disabling them stops a run from
    dying halfway through on a model id ChatAnthropic will reject.
    """

    BINDINGS = [Binding("escape", "cancel", "cancel")]

    def __init__(self, current: str) -> None:
        super().__init__()
        self._current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="picker"):
            yield Static(Text("Agents reason with", style=f"bold {BRIGHT}"),
                         id="picker-q")
            yield OptionList(*self._options(), id="picker-list")
            yield Static(Text("enter to pick · esc to cancel", style=MUTED),
                         classes="hint")
        yield Footer()

    def _options(self) -> list[Option | None]:
        options: list[Option | None] = []
        for provider, models in self._by_provider().items():
            reachable = is_supported(provider)
            head = Text(provider.upper(), style=f"bold {BRIGHT}")
            if not reachable:
                head.append("   no client in v2 yet", style=MUTED)
            options.append(Option(head, disabled=True))
            for name, model_id, _ in models:
                row = Text()
                row.append(" ✓ " if model_id == self._current else "   ",
                           style=f"bold {GREEN}")
                row.append(f"{name:<18}", style=TEXT if reachable else MUTED)
                row.append(model_id, style=MUTED)
                options.append(Option(
                    row, id=model_id if reachable else None,
                    disabled=not reachable))
            options.append(None)
        return options[:-1] if options else options

    def _by_provider(self) -> dict[str, list[tuple[str, str, str]]]:
        """Registry order preserved, reachable providers first — what you can
        actually pick should not sit below what you cannot."""
        groups: dict[str, list[tuple[str, str, str]]] = {}
        for entry in load_api_models():
            groups.setdefault(entry[2], []).append(entry)
        return dict(sorted(groups.items(),
                           key=lambda kv: not is_supported(kv[0])))

    def on_mount(self) -> None:
        picker = self.query_one("#picker-list", OptionList)
        picker.highlighted = next(
            (i for i, opt in enumerate(picker._options)
             if opt.id == self._current), 1)
        picker.focus()

    @on(OptionList.OptionSelected, "#picker-list")
    def _pick(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class FundSelectScreen(Screen):
    """'Run an existing fund', master-detail: fund slots on the left, the
    highlighted fund's latest stats and its backtest history (newest first)
    on the right. Enter runs the fund as of today. Refreshes on resume.
    """

    BINDINGS = [
        Binding("escape", "back", "back"),
        Binding("d", "delete", "delete fund"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._summaries: dict[tuple[str, float], dict | None] = {}

    def compose(self) -> ComposeResult:
        with Horizontal(id="select"):
            with Vertical(id="select-rail"):
                yield Static(Text("YOUR FUNDS", style=MUTED), classes="rail-title")
                yield OptionList(id="select-menu")
            with VerticalScroll(id="select-detail"):
                yield Static("", id="detail-body")
        yield Footer()

    def on_mount(self) -> None:
        self._populate()

    def on_screen_resume(self) -> None:
        self._populate()

    def action_back(self) -> None:
        self.app.pop_screen()

    def _populate(self) -> None:
        # Slots carry the mandate's path, not just its name: a file's stem and
        # the fund's name need not match (example.yaml holds "example-fund"),
        # and delete has to remove the right file.
        self._slots = _saved_funds()
        menu = self.query_one("#select-menu", OptionList)
        menu.clear_options()
        if not self._slots:
            self.query_one("#detail-body", Static).update(
                Text("No funds yet — go back and build one first.", style=MUTED))
            return
        for i, (_, spec) in enumerate(self._slots):
            menu.add_option(Option(
                _slot_card(i, spec, _last_score(spec.name)), id=f"fund:{i}"))
        # Options added after mount leave `highlighted` unset — pin it so the
        # detail pane fills in and Enter works without an arrow press first.
        menu.highlighted = 0
        menu.focus()
        self._show_detail(0)

    @on(OptionList.OptionHighlighted, "#select-menu")
    def _hover(self, event: OptionList.OptionHighlighted) -> None:
        oid = (event.option.id or "") if event.option else ""
        if oid.startswith("fund:"):
            self._show_detail(int(oid.split(":")[1]))

    @on(OptionList.OptionSelected, "#select-menu")
    def _choose(self, event: OptionList.OptionSelected) -> None:
        oid = event.option.id or ""
        if oid.startswith("fund:"):
            _, spec = self._slots[int(oid.split(":")[1])]
            self.app.push_screen(RunScreen(spec))

    def action_delete(self) -> None:
        menu = self.query_one("#select-menu", OptionList)
        if not self._slots or menu.highlighted is None:
            return
        # Remember what was asked for: the list repopulates on resume, so the
        # highlighted index is not trustworthy by the time the callback fires.
        self._pending_delete = self._slots[menu.highlighted]
        path, spec = self._pending_delete
        self.app.push_screen(
            ConfirmDeleteScreen(path, spec, self._history(spec.name)),
            self._finish_delete,
        )

    def _finish_delete(self, scope: str | None) -> None:
        """Callback from the confirm screen: None cancelled, otherwise the
        blast radius the user picked."""
        if scope is None:
            return
        path, spec = self._pending_delete
        gone = _delete_fund(path, spec.name, with_history=(scope == "all"))
        self._summaries.clear()  # the cache is keyed on paths that just went
        self._populate()
        self.notify(f"Deleted {spec.name} — {gone} "
                    f"{'file' if gone == 1 else 'files'} removed")

    def _show_detail(self, i: int) -> None:
        spec = self._slots[i][1]
        self.query_one("#detail-body", Static).update(
            _fund_detail(spec, self._history(spec.name)))

    def _history(self, name: str) -> list[dict]:
        """Everything this fund has done — runs and backtests — newest first,
        as light summaries. Cached by (path, mtime) so arrowing the list stays
        instant."""
        out: list[dict] = []
        for pattern in (f"{name}-run-*.json", f"{name}-backtest*.json"):
            for p in FUNDS_DIR.glob(pattern):
                mtime = p.stat().st_mtime
                key = (str(p), mtime)
                if key not in self._summaries:
                    self._summaries[key] = _summarize(p, mtime)
                summ = self._summaries[key]
                if summ is not None:
                    out.append(summ)
        out.sort(key=lambda s: s["mtime"], reverse=True)
        return out


def _saved_funds() -> list[tuple[Path, FundSpec]]:
    """Every saved mandate as (file, spec). The path travels with the spec
    because the two names can differ — example.yaml holds "example-fund"."""
    return [(p, load_spec(p)) for p in sorted(FUNDS_DIR.glob("*.yaml"))]


def _delete_fund(path: Path, name: str, *, with_history: bool) -> int:
    """Remove a fund's mandate, and its receipts too when asked. Returns how
    many files went, so the caller can say so."""
    targets = [path, *(_receipts(name) if with_history else [])]
    for target in targets:
        target.unlink(missing_ok=True)
    return len(targets)


class ConfirmDeleteScreen(ModalScreen[str | None]):
    """Deleting is the only irreversible thing this app does, so it gets a
    screen of its own: the exact files at stake, and two keys for the two
    blast radii — the mandate alone, or the mandate and its history.
    """

    BINDINGS = [
        Binding("escape", "cancel", "cancel"),
        Binding("enter", "delete_mandate", "delete the mandate", priority=True),
        Binding("ctrl+d", "delete_all", "delete mandate + history",
                priority=True),
    ]

    def __init__(self, path: Path, spec: FundSpec, history: list[dict]) -> None:
        super().__init__()
        self._path = path
        self._spec = spec
        self._runs = sum(1 for h in history if h["kind"] == "run")
        self._backtests = sum(1 for h in history if h["kind"] == "backtest")

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm"):
            yield Static(Text.assemble(
                ("Delete ", f"bold {BRIGHT}"),
                (self._spec.name, f"bold {RED}"),
                ("?", f"bold {BRIGHT}")), id="confirm-q")
            yield Static(self._manifest(), id="confirm-files")
            yield Static(Text.assemble(
                ("enter", f"bold {GREEN}"), ("   delete the mandate\n", MUTED),
                ("ctrl+d", f"bold {RED}"),
                ("  delete the mandate and its history\n", MUTED),
                ("esc", f"bold {BRIGHT}"), ("     cancel", MUTED)),
                id="confirm-keys")
        yield Footer()

    def _manifest(self) -> Text:
        """What is on the table, named exactly — a count is easy to misread
        when the thing being counted cannot be recovered."""
        lines = Text()
        lines.append(f"{self._path.name}\n", style=TEXT)
        lines.append("  the mandate — strategies, staff, risk, capital\n\n",
                     style=MUTED)
        if self._runs or self._backtests:
            lines.append(
                f"{self._runs} {'run' if self._runs == 1 else 'runs'}"
                f"  ·  {self._backtests} "
                f"{'backtest' if self._backtests == 1 else 'backtests'}\n",
                style=CYAN)
            lines.append("  saved receipts — kept unless you press ctrl+d",
                         style=MUTED)
        else:
            lines.append("No saved runs or backtests.", style=MUTED)
        return lines

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_delete_mandate(self) -> None:
        self.dismiss("mandate")

    def action_delete_all(self) -> None:
        self.dismiss("all")


def _summarize(path: Path, mtime: float) -> dict | None:
    """One saved receipt — a run's CycleRecord or a backtest's result — as the
    light summary the history pane renders. None if the file is unreadable."""
    try:
        d = json.loads(path.read_text())
        universe = d.get("universe", [])
        if "metrics" in d:  # a backtest
            m = d["metrics"]
            return {
                "kind": "backtest", "mtime": mtime, "universe": universe,
                "start": d.get("start", ""), "end": d.get("end", ""),
                "benchmark": d.get("benchmark", "SPY"),
                "total": m["total_return_pct"],
                "annualized": m["annualized_return_pct"],
                "sharpe": m["sharpe_ratio"], "maxdd": m["max_drawdown_pct"],
                "benchret": m["benchmark_return_pct"],
                "excess": m["excess_return_pct"], "n_cycles": m["n_cycles"],
            }
        return {  # a single cycle
            "kind": "run", "mtime": mtime, "universe": universe,
            "as_of": d["as_of"], "nav": d["nav"],
            "n_orders": len(d.get("orders", [])),
        }
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def _receipts(name: str) -> list[Path]:
    """Every saved receipt for a fund — runs and backtests — newest first."""
    paths = [*FUNDS_DIR.glob(f"{name}-run-*.json"),
             *FUNDS_DIR.glob(f"{name}-backtest*.json")]
    return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)


def _last_universe(name: str) -> list[str] | None:
    """The tickers this fund was last pointed at — the ticker inputs prefill
    from it, so a returning user just presses enter."""
    for path in _receipts(name):
        summary = _summarize(path, 0.0)
        if summary and summary["universe"]:
            return summary["universe"]
    return None


def _last_score(name: str) -> tuple[float, float, str] | None:
    """The fund's most recent BACKTEST result, if any: (total return, excess
    return, benchmark). A quiet scoreboard on each slot — runs have no return
    to show, only a NAV."""
    files = list(FUNDS_DIR.glob(f"{name}-backtest*.json"))
    if not files:
        return None
    newest = max(files, key=lambda p: p.stat().st_mtime)
    summary = _summarize(newest, 0.0)
    if summary is None or summary["kind"] != "backtest":
        return None
    return (summary["total"], summary["excess"], summary["benchmark"])


def _slot_card(index: int, spec: FundSpec, score: tuple | None) -> Text:
    """One slot in the left rail: number + name + last-score arrow on top, a
    short mandate line beneath. Spare on purpose — the detail pane carries the
    full stats."""
    n = len(spec.strategies)
    card = Text()
    card.append(f" {index + 1:02d}  ", style=f"bold {CYAN}")
    # Bold but uncoloured on purpose: the name inherits the option list's
    # colour, so the highlighted row can turn it green (see app.tcss).
    card.append(spec.name, style="bold")
    if score is not None:
        total, _, _ = score
        up = total >= 0
        card.append(f"   {'▲' if up else '▼'} {total:+.1%}",
                    style=f"bold {GREEN if up else RED}")
    card.append(f"\n     {n} {'strategy' if n == 1 else 'strategies'}"
                f"  ·  {spec.rebalance}", style=MUTED)
    return card


def _fund_detail(spec: FundSpec, history: list[dict]) -> Group:
    """The right pane: the fund's identity, its latest backtest stats, then
    everything it has done — runs and backtests, newest first, each with the
    tickers it was pointed at."""
    staff = ", ".join(s.title for s in spec.strategies)
    parts: list = [
        Text(spec.name, style=f"bold {BRIGHT}"),
        Text(f"{staff}  ·  {spec.rebalance}  ·  ${spec.capital:,.0f}", style=MUTED),
    ]

    if not history:
        parts.append(Text("\nNo runs yet — this fund has never traded.", style=MUTED))
        parts.append(Text("\nEnter to run it as of today · ctrl+b to backtest "
                          "over history", style=MUTED))
        return Group(*parts)

    # The headline stats come from the most recent BACKTEST (a single run has
    # no return to show, only a book).
    latest = next((h for h in history if h["kind"] == "backtest"), None)
    if latest is not None:
        # A universe is only present on newer receipts — join what exists so an
        # older backtest doesn't render a dangling separator.
        facts = [f"{latest['start']} → {latest['end']}",
                 f"{latest['n_cycles']} cycles"]
        if latest["universe"]:
            facts.append(" ".join(latest["universe"]))
        parts.append(Text("\nLATEST BACKTEST", style=f"bold {BRIGHT}"))
        parts.append(Text("  ·  ".join(facts), style=MUTED))
        parts.append(_stat_list(latest))

    parts.append(Text("\nRUNS & BACKTESTS", style=f"bold {BRIGHT}"))
    # Three columns, not four. The kind and the number are pinned with no_wrap
    # so a narrow pane can never drop the result — the tickers ride along in
    # the middle column and are the only thing allowed to ellipsize.
    log = Table(box=None, show_header=False, padding=(0, 1), pad_edge=False,
                expand=True)
    log.add_column(no_wrap=True)                          # kind
    log.add_column(overflow="ellipsis", no_wrap=True)     # when · tickers
    log.add_column(justify="right", no_wrap=True)         # headline number
    for h in history[:12]:
        tickers = _short_tickers(h["universe"])
        if h["kind"] == "backtest":
            up = h["total"] >= 0
            when = Text(f"{h['start']} → {h['end']}", style=MUTED)
            if h["universe"]:
                when.append(f"  {tickers}", style=CYAN)
            log.add_row(
                Text("backtest", style=MUTED), when,
                Text(f"{h['total']:+.1%}", style=GREEN if up else RED),
            )
        else:
            when = Text(h["as_of"], style=MUTED)
            if h["universe"]:
                when.append(f"  {tickers}", style=CYAN)
            log.add_row(
                Text("run", style=MUTED), when,
                Text(f"NAV ${h['nav']:,.0f}", style=BRIGHT),
            )
    parts.append(log)
    return Group(*parts)


def _short_tickers(universe: list[str], limit: int = 2) -> str:
    """A run's tickers, short enough for a one-line log row: the first few,
    then a count of the rest. The full list is on the run's own report."""
    if not universe:
        return "—"
    if len(universe) <= limit:
        return " ".join(universe)
    return f"{' '.join(universe[:limit])} +{len(universe) - limit}"


def _stat_list(bt: dict) -> Table:
    """The headline backtest numbers as a label/value list.

    These used to be a six-column table, which truncated its own headers
    ("Ann…", "Shar…") in the detail pane. Reading down instead of across
    keeps every label a whole word at any terminal width.
    """
    table = Table(box=None, show_header=False, padding=(0, 1), pad_edge=False)
    table.add_column(style=MUTED, width=14)
    table.add_column(justify="right", min_width=8)
    table.add_row("Total return", Text(
        f"{bt['total']:+.1%}",
        style=f"bold {GREEN if bt['total'] >= 0 else RED}"))
    table.add_row("Annualized", Text(f"{bt['annualized']:+.1%}", style=TEXT))
    table.add_row("Sharpe", Text(
        f"{bt['sharpe']:.2f}",
        style=(GREEN if bt["sharpe"] > 1
               else "yellow" if bt["sharpe"] > 0 else RED)))
    table.add_row("Max drawdown", Text(f"{bt['maxdd']:.1%}", style=RED))
    table.add_row(bt["benchmark"], Text(f"{bt['benchret']:+.1%}", style=TEXT))
    table.add_row("Excess", Text(
        f"{bt['excess']:+.1%}",
        style=f"bold {GREEN if bt['excess'] >= 0 else RED}"))
    return table


def _roster_table(order: list[str], state: dict[str, tuple[str, str | None]]) -> Table:
    """The v1 roster look: one row per agent, working (yellow) → done (green).

    A working row's label is "TICKER" or "TICKER · date"; the date, when
    present, is tinted red as the point-in-time cursor (used by the backtest
    warm; the run-today roster has no date).
    """
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column()
    for name in order:
        status, label = state[name]
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
                row.append(as_of, RED)
            row.append("] ", CYAN)
            row.append("Analyzing", "yellow")
        else:
            row.append("⋯ ", MUTED)
            row.append(f"{name:<24}", MUTED)
            row.append("queued", MUTED)
        table.add_row(row)
    return table


# One glyph and one colour per call, in one place: the live board knows only
# the word the stream has decoded, the report has a whole Signal, and they must
# never disagree about what bearish looks like.
_VERDICT_STYLE = {
    "bullish": ("▲", GREEN),
    "bearish": ("▼", RED),
    "neutral": ("–", "yellow"),
    "abstain": ("·", MUTED),
}


def _verdict(signal: Signal) -> tuple[str, str, str]:
    """A signal's verdict as (glyph, word, colour) — one vocabulary, used by
    both the browser's list and its detail pane."""
    if signal.metadata.get("abstained") is True:
        word = "abstain"
    elif signal.value > 0:
        word = "bullish"
    elif signal.value < 0:
        word = "bearish"
    else:
        word = "neutral"
    glyph, colour = _VERDICT_STYLE[word]
    return (glyph, word.upper(), colour)


class _Desk:
    """One analyst's live state on the run board.

    Written by that analyst's own worker thread, read by the repaint timer.
    Every write is a single attribute assignment, so the worst a frame can show
    is the previous ticker's line — never a torn one. That is why the worker
    does not marshal each token onto the UI thread: at token rate it would
    flood the message pump, and the timer already paints faster than an eye.
    """

    def __init__(self, who: str) -> None:
        self.who = who
        self.status = "queued"
        self.ticker: str | None = None
        self.stream: ThesisStream | None = None
        self.signal: Signal | None = None

    def begin(self, ticker: str) -> None:
        self.status = "working"
        self.ticker = ticker
        self.signal = None
        self.stream = ThesisStream()

    def feed(self, text: str) -> None:
        if self.stream is not None:
            self.stream.feed(text)

    def settle(self, signal: Signal) -> None:
        """The real Signal, once predict() has returned. It supersedes the
        streamed reading — and it is the *only* thing a cache hit produces,
        since a cached answer never goes to the provider and streams nothing.
        """
        self.signal = signal

    def finish(self) -> None:
        self.status = "done"
        self.ticker = None
        self.stream = None
        self.signal = None


def _desk_table(desks: list[_Desk]) -> Table:
    """The live run board: one row per analyst, thesis typing itself out.

    The call arrives before the prose does — agents answer signal and
    confidence first — so a row shows its verdict the moment it is decodable
    and fills the reasoning in after. Rows move in parallel, which is the point
    of the view: two analysts reaching opposite calls on the same name, at once.
    """
    table = Table(show_header=False, box=None, padding=(0, 1),
                  expand=True, pad_edge=False)
    # Only the thesis flexes. `ratio` is what makes that true: given plain
    # widths and expand=True, rich shrinks every column proportionally when the
    # terminal is narrow, and the verdict degrades to "▲…" — which is the one
    # cell that must always be legible.
    table.add_column(width=1)                                     # status glyph
    table.add_column(width=20, no_wrap=True)                      # analyst
    table.add_column(width=5, no_wrap=True)                       # ticker
    table.add_column(width=14, no_wrap=True)                      # verdict
    table.add_column(ratio=1, overflow="ellipsis", no_wrap=True)  # thesis, live

    for desk in desks:
        if desk.status == "done":
            table.add_row(Text("✓", f"bold {GREEN}"), Text(desk.who, "bold"),
                          Text(""), Text("Done", GREEN), Text(""))
        elif desk.status == "queued":
            table.add_row(Text("⋯", MUTED), Text(desk.who, MUTED), Text(""),
                          Text(""), Text("queued", MUTED))
        else:
            table.add_row(
                Text("⋯", "yellow"),
                Text(desk.who, "bold"),
                Text(desk.ticker or "", CYAN),
                _live_verdict(desk),
                _live_thesis(desk),
            )
    return table


def _live_verdict(desk: _Desk) -> Text:
    """The call: from the finished Signal when predict() has returned, else
    from the stream as far as it has decoded, else nothing yet."""
    if desk.signal is not None:
        glyph, word, colour = _verdict(desk.signal)
        confidence = desk.signal.metadata.get("confidence")
        label = f"{word} {confidence:.0f}%" if isinstance(confidence, float) else word
        return Text.assemble((f"{glyph} ", colour), (label, f"bold {colour}"))
    stream = desk.stream
    if stream is None or stream.signal is None:
        return Text("thinking", MUTED)
    glyph, colour = _VERDICT_STYLE.get(stream.signal, ("·", MUTED))
    return Text.assemble((f"{glyph} ", colour),
                         (stream.verdict() or "", f"bold {colour}"))


def _live_thesis(desk: _Desk) -> Text:
    """The reasoning so far, on one line. Whitespace is collapsed because the
    row is a single line and a newline inside the thesis would eat it."""
    if desk.signal is not None:
        text = desk.signal.reasoning
    elif desk.stream is not None:
        text = desk.stream.thesis
    else:
        text = ""
    return Text(" ".join(text.split()), style=TEXT)


def _report_nav(record: CycleRecord) -> list[Option]:
    """The report's left rail: every signal as ONE line, then the book.

    A thesis runs paragraphs — rendering them inline made a table where a
    single signal filled the screen. Here each signal is a scannable row and
    the full thesis goes to the detail pane, so the fund's thinking stays
    navigable on a default-size terminal.
    """
    options: list[Option] = []
    spec_by_name = {s.name: s for s in record.spec.strategies}
    for si, sr in enumerate(record.strategies):
        strategy = spec_by_name[sr.name]
        # Title and capital slice, nothing else — the strategy's kind and
        # neutrality are on the mandate, not worth a line in a 38-cell rail.
        # A blank row above every group but the first separates it from the
        # signals of the strategy before it.
        if si:
            options.append(Option(Text(""), disabled=True))
        options.append(Option(
            Text.assemble((strategy.title, f"bold {BRIGHT}"),
                          (f" ({sr.slice:.0%})", MUTED)),
            disabled=True,
        ))
        for sj, s in enumerate(sr.signals):
            glyph, _, tone = _verdict(s)
            confidence = s.metadata.get("confidence")
            row = Text()
            row.append(f" {s.ticker:<6}", style=f"bold {CYAN}")
            row.append(f"{_SHORT_NAMES.get(s.model_name, s.model_name):<15}",
                       style=TEXT)
            row.append(f"{glyph} ", style=f"bold {tone}")
            row.append(f"{confidence:.0f}%" if confidence is not None else "  —",
                       style=tone)
            options.append(Option(row, id=f"sig:{si}:{sj}"))

    options.append(Option(Text(""), disabled=True))
    options.append(Option(Text("THE BOOK", style=f"bold {BRIGHT}"), disabled=True))
    if record.clamps:
        options.append(Option(
            Text(f" Risk limits ({len(record.clamps)})", style=TEXT), id="sec:risk"))
    options.append(Option(
        Text(f" Orders ({len(record.orders)})", style=TEXT), id="sec:orders"))
    options.append(Option(Text(" Portfolio", style=TEXT), id="sec:portfolio"))
    return options


def _signal_detail(record: CycleRecord, si: int, sj: int) -> Group:
    """One analyst's full view: who, what, and the whole written thesis."""
    sr = record.strategies[si]
    signal = sr.signals[sj]
    _, word, tone = _verdict(signal)
    confidence = signal.metadata.get("confidence")
    header = Text()
    header.append(signal.ticker, style=f"bold {CYAN}")
    header.append("  ·  ", style=MUTED)
    header.append(DISPLAY_NAMES.get(signal.model_name, signal.model_name),
                  style=f"bold {BRIGHT}")
    facts = Text()
    facts.append(word, style=f"bold {tone}")
    if confidence is not None:
        facts.append(f"  ·  {confidence:.0f}% confidence", style=MUTED)
    facts.append(f"  ·  conviction {signal.value:+.2f}", style=MUTED)
    facts.append(f"  ·  {sr.name}", style=MUTED)
    return Group(
        header,
        facts,
        Text(""),
        Text(signal.reasoning or "no thesis recorded",
             style=TEXT if signal.reasoning else MUTED),
    )


def _risk_detail(record: CycleRecord) -> Group:
    table = Table(box=box.SQUARE, header_style="bold", border_style="#1f2b25")
    table.add_column("Scope", style=f"bold {CYAN}")
    table.add_column("Requested", justify="right")
    table.add_column("Allowed", justify="right")
    table.add_column("Limit", style="dim")
    for c in record.clamps:
        table.add_row(
            c.ticker or "whole book",
            Text(f"{c.before:+.2f}", style="yellow"),
            Text(f"{c.after:+.2f}", style="bold"),
            c.limit,
        )
    return Group(
        Text.assemble(("RISK LIMITS  ", f"bold {BRIGHT}"),
                      ("hard caps the agents cannot override", MUTED)),
        Text(""),
        table,
    )


def _orders_detail(record: CycleRecord) -> Group:
    if not record.orders:
        return Group(
            Text("ORDERS", style=f"bold {BRIGHT}"),
            Text(""),
            Text("none — no conviction cleared the bar today", style=MUTED),
        )
    table = Table(box=box.SQUARE, header_style="bold", border_style="#1f2b25")
    table.add_column("Action", justify="center")
    table.add_column("Quantity", justify="right")
    table.add_column("Ticker", style=f"bold {CYAN}")
    table.add_column("Price", justify="right")
    for o in record.orders:
        tone = f"bold {GREEN}" if o.side == "buy" else f"bold {RED}"
        table.add_row(
            Text(o.side.upper(), style=tone),
            Text(f"{o.quantity:,}", style=tone),
            o.ticker,
            f"${o.price:,.2f}",
        )
    return Group(Text("ORDERS", style=f"bold {BRIGHT}"), Text(""), table)


def _portfolio_detail(record: CycleRecord) -> Group:
    if not record.positions:
        return Group(
            Text("PORTFOLIO", style=f"bold {BRIGHT}"),
            Text(""),
            Text("flat — no positions", style=MUTED),
        )
    table = Table(box=box.SQUARE, header_style="bold", border_style="#1f2b25")
    table.add_column("Ticker", style=f"bold {CYAN}")
    table.add_column("Side", justify="center")
    table.add_column("Shares", justify="right")
    table.add_column("Value", justify="right")
    table.add_column("Weight", justify="right")
    for ticker in sorted(record.positions):
        shares = record.positions[ticker]
        value = shares * record.marks[ticker]
        side = (Text("LONG", style=f"bold {GREEN}") if shares > 0
                else Text("SHORT", style=f"bold {RED}"))
        tone = GREEN if value >= 0 else RED
        table.add_row(
            ticker, side, f"{shares:+d}",
            Text(f"${value:+,.0f}", style=tone),
            Text(f"{value / record.nav:+.1%}", style=tone),
        )
    return Group(Text("PORTFOLIO", style=f"bold {BRIGHT}"), Text(""), table)


def _book_summary(record: CycleRecord) -> Text:
    """The always-visible bottom strip: what the book looks like after."""
    long_val = sum(max(s * record.marks[t], 0.0)
                   for t, s in record.positions.items())
    short_val = sum(min(s * record.marks[t], 0.0)
                    for t, s in record.positions.items())
    gross = (long_val - short_val) / record.nav
    net = (long_val + short_val) / record.nav
    summary = Text()
    summary.append(f"NAV ${record.nav:,.2f}", style=f"bold {BRIGHT}")
    summary.append(f"   Cash ${record.cash:,.0f}", style=CYAN)
    summary.append(f"   Gross {gross:.0%}   Net {net:+.0%}", style=MUTED)
    return summary


_TAPE_ROWS = 12


def _tape_table(tape: list[tuple[str, Fill, int]]) -> Table:
    """The running trade tape: every fill of the replay so far, newest first.
    Each row is one execution — date, ticker, side, size, price, notional —
    and the book it left behind (LONG/SHORT/FLAT that ticker)."""
    table = Table.grid(expand=True, padding=(0, 1))
    for justify in ("left", "left", "left", "right", "right", "right", "left"):
        table.add_column(justify=justify)

    if not tape:
        table.add_row(Text("no trades yet", style=MUTED))
        return table

    for as_of, fill, shares in list(reversed(tape))[:_TAPE_ROWS]:
        side = (Text("BUY ", style=f"bold {GREEN}") if fill.side == "buy"
                else Text("SELL", style=f"bold {RED}"))
        book = (Text(f"→ long {shares}", style=GREEN) if shares > 0
                else Text(f"→ short {-shares}", style=RED) if shares < 0
                else Text("→ flat", style=MUTED))
        table.add_row(
            Text(as_of, style=MUTED),
            Text(fill.ticker, style=f"bold {CYAN}"),
            side,
            f"{fill.quantity:,}",
            f"@ ${fill.price:,.2f}",
            Text(f"${fill.quantity * fill.price:,.0f}", style=TEXT),
            book,
        )
    if len(tape) > _TAPE_ROWS:
        table.add_row(Text(f"… {len(tape) - _TAPE_ROWS} earlier", style=MUTED))
    return table


class RunScreen(Screen):
    """Run a fund as of today — the primary verb. Warm the roster, run one
    cycle on today's data, then reveal the fund's thinking: signals, risk
    clamps, orders, and the target book. Backtest is the side option (ctrl+b),
    offered before a run and again from the finished report.
    """

    # ctrl+b, not plain b: the ticker Input owns letter keys (BABA, BRK.B),
    # and priority so the shortcut still fires while it has focus.
    BINDINGS = [
        Binding("escape", "back", "back"),
        Binding("ctrl+b", "backtest", "backtest instead", priority=True),
    ]

    def __init__(self, spec: FundSpec) -> None:
        super().__init__()
        self._spec = spec
        self._as_of = _date.today().isoformat()
        self._phase = "ready"
        self._universe: list[str] = []
        self._record: CycleRecord | None = None
        self._desks: list[_Desk] = []
        self._painter: Timer | None = None

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial="run-ready", id="run-panes"):
            with Vertical(id="run-ready", classes="pane"):
                yield Static("", id="run-hero")
                yield Label("What should it trade today?", classes="q")
                yield Input(
                    placeholder=f"e.g. {', '.join(UNIVERSE_PRESETS[:5])}",
                    id="run-tickers",
                )
                yield Static(
                    Text("enter to run · ctrl+b to backtest instead · esc to go back",
                         style=MUTED),
                    classes="hint",
                )
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
        spec = self._spec
        staff = ", ".join(s.title for s in spec.strategies)
        self.query_one("#run-hero", Static).update(Group(
            Text(spec.name, style=f"bold {BRIGHT}"),
            Text(f"{staff}  ·  {spec.rebalance}  ·  ${spec.capital:,.0f}",
                 style=MUTED),
        ))
        tickers = self.query_one("#run-tickers", Input)
        last = _last_universe(spec.name)
        if last:
            tickers.value = ", ".join(last)
        tickers.focus()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        # No leaving or switching mid-run; backtest is offered from ready
        # ("backtest instead") and from the finished report ("backtest it").
        if self._phase == "running":
            return action not in ("back", "backtest")
        if action == "backtest":
            return self._phase in ("ready", "done")
        return True

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_backtest(self) -> None:
        self.app.push_screen(BacktestScreen(spec=self._spec))

    @on(Input.Submitted, "#run-tickers")
    def _start(self, event: Input.Submitted) -> None:
        try:
            self._universe = normalize_universe(
                event.value.replace(",", " ").split())
        except ValueError:
            self.notify("Enter at least one ticker.", severity="error")
            return
        def resume() -> None:
            if _demand_run_keys(self.app, resume):
                self._begin()
        resume()

    def _begin(self) -> None:
        self._phase = "running"
        self.query_one("#run-panes", ContentSwitcher).current = "run-live"
        self.query_one("#run-phase", Static).update(Text.assemble(
            ("Agents analyzing as of ", f"bold {BRIGHT}"),
            (self._as_of, f"bold {RED}"),
            ("  ·  today's data → today's target book", MUTED),
        ))
        self._desks = [_Desk(DISPLAY_NAMES.get(n, n))
                       for n in _agent_names(self._spec)]
        self._paint_board()
        # The worker threads mutate their own desk; this redraws all of them on
        # one clock, so token rate never sets frame rate.
        self._painter = self.set_interval(_BOARD_REFRESH, self._paint_board)
        self._run()

    def _paint_board(self) -> None:
        self.query_one("#run-roster", Static).update(_desk_table(self._desks))

    @on(OptionList.OptionHighlighted, "#report-nav")
    def _browse(self, event: OptionList.OptionHighlighted) -> None:
        assert self._record is not None
        oid = (event.option.id or "") if event.option else ""
        detail = self.query_one("#detail-pane", Static)
        if oid.startswith("sig:"):
            _, si, sj = oid.split(":")
            detail.update(_signal_detail(self._record, int(si), int(sj)))
        elif oid == "sec:risk":
            detail.update(_risk_detail(self._record))
        elif oid == "sec:orders":
            detail.update(_orders_detail(self._record))
        elif oid == "sec:portfolio":
            detail.update(_portfolio_detail(self._record))
        self.query_one("#report-detail", VerticalScroll).scroll_home(animate=False)

    @work(thread=True, exclusive=True)
    def _run(self) -> None:
        app = self.app
        spec = self._spec
        as_of = self._as_of
        universe = self._universe
        try:
            desks = dict(zip(_agent_names(spec), self._desks, strict=True))

            def warm(agent_name: str) -> None:
                desk = desks[agent_name]
                cls = ALPHA_MODEL_REGISTRY[agent_name]  # own instance per thread
                # Only LLM agents have anything to stream; a quant model carries
                # no client and simply runs.
                model = (cls(llm=make_llm(on_token=desk.feed))
                         if issubclass(cls, LLMAgent) else cls())
                with FDClient() as raw:
                    fd = CachedDataClient(raw)
                    for ticker in universe:
                        desk.begin(ticker)
                        try:
                            desk.settle(model.predict(ticker, as_of, fd))
                        except Exception:
                            pass  # best-effort warm; run_cycle is the source of truth
                desk.finish()

            names = list(desks)
            with ThreadPoolExecutor(max_workers=min(8, len(names))) as pool:
                for future in as_completed([pool.submit(warm, n) for n in names]):
                    future.result()

            fund = Fund(spec)
            broker = SimBroker(cash=spec.capital)
            with FDClient() as raw:
                record = run_cycle(fund, as_of, broker, CachedDataClient(raw),
                                   universe)

            # Receipts, same shape as a backtest's: the run is recoverable,
            # and it's what the fund's history pane reads.
            FUNDS_DIR.mkdir(exist_ok=True)
            stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            path = FUNDS_DIR / f"{spec.name}-run-{stamp}.json"
            path.write_text(record.model_dump_json(indent=2))
            app.call_from_thread(self._show_report, record, path)
        except Exception as exc:  # fail loud, in the UI
            app.call_from_thread(self._fail, exc)

    def _stop_painting(self) -> None:
        """The board is only live while the analysts are. Leave the last frame
        on screen — it is the finished roster."""
        if self._painter is not None:
            self._painter.stop()
            self._painter = None
        self._paint_board()

    def _show_report(self, record: CycleRecord, path: Path) -> None:
        self._stop_painting()
        self._phase = "done"
        self._record = record
        n_signals = sum(len(sr.signals) for sr in record.strategies)
        self.query_one("#report-head", Static).update(Text.assemble(
            (record.fund, f"bold {BRIGHT}"),
            (f"  ·  {record.as_of}  ·  {n_signals} signals  ·  "
             f"{len(record.orders)} orders", MUTED),
        ))
        self.query_one("#report-foot", Static).update(Group(
            _book_summary(record),
            Text.assemble(("✓ ", f"bold {GREEN}"), ("Saved run to ", MUTED),
                          (str(path), MUTED)),
            Text.assemble(("▶ ", f"bold {GREEN}"),
                          ("Backtest this fund over history", f"bold {GREEN}"),
                          ("  ·  ctrl+b", MUTED)),
        ))
        self.refresh_bindings()  # phase changed: ctrl+b is offered again
        nav = self.query_one("#report-nav", OptionList)
        nav.clear_options()
        nav.add_options(_report_nav(record))
        self.query_one("#run-panes", ContentSwitcher).current = "run-report"
        # Land on the first signal (option 0 is a disabled strategy header).
        nav.highlighted = 1
        nav.focus()

    def _fail(self, exc: Exception) -> None:
        self._stop_painting()
        self._phase = "failed"
        self.query_one("#run-phase", Static).update(Text.assemble(
            ("✗ ", f"bold {RED}"), (f"{type(exc).__name__}: {exc}", RED)))
        self.notify(str(exc), title="Run failed", severity="error")


class BuilderScreen(Screen):
    """The fund wizard: a step rail on the left, the active step on the right.

    Four steps, Esc rewinds one, and the output is a FundSpec YAML — the same
    mandate the engine reads. No tickers here: a fund is its desk, and what it
    trades is chosen per run. The rail shows where you are and what you've
    already chosen at every step.
    """

    STEP_IDS = ["step-name", "step-strategies", "step-capital", "step-cadence"]
    STEP_TITLES = ["Name", "Strategies", "Capital", "Cadence"]
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
                        Option("▶  Run it as of today", id="go-run"),
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

    # ---- the four steps ---------------------------------------------------

    @on(Input.Submitted, "#name-input")
    def _submit_name(self, event: Input.Submitted) -> None:
        self._state["name"] = (
            event.value.strip().replace(" ", "-").lower() or "ai-hedge-fund"
        )
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
                (f"  ·  {staff}  ·  ${spec.capital:,.0f}  ·  {spec.rebalance}",
                 MUTED),
            ),
            Text(""),
            Text("Pick the tickers when you run it — a fund carries no watchlist.",
                 style=MUTED),
        ))
        self._goto("step-done")

    @on(OptionList.OptionSelected, "#done-menu")
    def _after_build(self, event: OptionList.OptionSelected) -> None:
        assert self._built is not None
        if event.option.id == "go-run":
            self.app.switch_screen(RunScreen(self._built[0]))
        else:
            self.app.pop_screen()

    # ---- rendering --------------------------------------------------------

    def _refresh_rail(self) -> None:
        chosen = {
            0: self._state.get("name"),
            1: self._short_strategies(),
            2: (f"${self._state['capital']:,.0f}"
                if "capital" in self._state else None),
            3: self._state.get("rebalance"),
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
        self._tape: list[tuple[str, Fill, int]] = []  # (as_of, fill, shares after)

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial="bt-pick", id="bt-panes"):
            with Vertical(id="bt-pick", classes="pane"):
                yield Label("Which fund?", classes="q")
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
                with Horizontal(id="stats", classes="hidden"):
                    yield Static("", id="stat-nav")
                    yield Static("", id="stat-return")
                    yield Static("", id="stat-bench")
                    yield Static("", id="stat-excess")
                    yield Static("", id="stat-sharpe")
                    yield Static("", id="stat-dd")
                with Vertical(id="curve-box", classes="hidden"):
                    yield Static("", id="curve")
                with Vertical(id="tape-box", classes="hidden"):
                    yield Static("", id="tape")
                yield Static("", id="cycle-line")
                yield Static("", id="result-summary", classes="hidden")
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
        assert self._spec is not None
        self._phase = "dates"
        today = _date.today()
        tickers = self.query_one("#bt-tickers", Input)
        start = self.query_one("#start-input", Input)
        end = self.query_one("#end-input", Input)
        if not tickers.value:
            last = _last_universe(self._spec.name)
            if last:
                tickers.value = ", ".join(last)
        if not start.value:
            start.value = (today - timedelta(weeks=_BACKTEST_WEEKS)).isoformat()
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
        try:
            universe = normalize_universe(
                self.query_one("#bt-tickers", Input).value.replace(",", " ").split())
        except ValueError:
            self.notify("Enter at least one ticker.", severity="error")
            self.query_one("#bt-tickers", Input).focus()
            return
        assert self._spec is not None

        def resume() -> None:
            if _demand_run_keys(self.app, resume):
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
        # "Back to home" means home: a ctrl+b backtest sits on top of the run
        # screen, so popping once would land on its stale ticker input.
        while not isinstance(self.app.screen, HomeScreen):
            self.app.pop_screen()

    # ---- the worker (everything below the UI runs off-thread) -------------

    @work(thread=True, exclusive=True)
    def _run(self, spec: FundSpec, start: str, end: str,
             universe: list[str]) -> None:
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

            app.call_from_thread(self._begin_warm, spec, universe, len(grid))
            self._warm_market(spec, universe, grid)
            app.call_from_thread(self._begin_agents, spec)
            self._warm_agents(spec, universe, grid)
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
                                       universe, on_cycle=tick)

            FUNDS_DIR.mkdir(exist_ok=True)
            stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            path = FUNDS_DIR / f"{spec.name}-backtest-{stamp}.json"
            path.write_text(result.model_dump_json(indent=2))
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
            (ticker, grid[j:j + _WARM_CHUNK])
            for ticker in universe
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

    def _warm_agents(self, spec: FundSpec, universe: list[str],
                     grid: list[str]) -> None:
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
        return _roster_table(self._roster_order, self._roster_state)

    def _begin_replay(self, spec: FundSpec, closes: dict[str, float],
                      n_cycles: int) -> None:
        self._closes = closes
        self._dates = []
        self._nav = []
        self._n_cycles = n_cycles
        self._tape = []
        self.query_one("#phase-line", Static).update(Text.assemble(
            ("Replaying the fund", f"bold {BRIGHT}"),
            ("  ·  one run_cycle per rebalance date, off the warm cache",
             MUTED),
        ))
        box_widget = self.query_one("#curve-box", Vertical)
        box_widget.border_title = "equity curve"
        box_widget.border_subtitle = (
            f"[{GREEN}]██[/] fund   [{CYAN}]──[/] {spec.benchmark}"
        )
        tape_box = self.query_one("#tape-box", Vertical)
        tape_box.border_title = "trades (newest first)"
        self.query_one("#stats", Horizontal).remove_class("hidden")
        box_widget.remove_class("hidden")
        tape_box.remove_class("hidden")

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

        # Running Sharpe, same math as the engine's final _metrics: per-cycle
        # returns over the curve, sample stdev, annualized by cadence.
        returns = [b / a - 1 for a, b in zip(curve, curve[1:])]
        if len(returns) > 1 and stdev(returns) > 0:
            sharpe = (mean(returns) / stdev(returns)
                      * sqrt(_PERIODS_PER_YEAR[self._spec.rebalance]))
        else:
            sharpe = 0.0
        self._update_stats(nav, fund_return, benchmark_return,
                           fund_return - benchmark_return, sharpe, max_dd)

        benchmark_curve = [capital] + [
            capital * self._closes[d] / self._closes[self._dates[0]]
            for d in self._dates
        ]
        curve_widget = self.query_one("#curve", Static)
        width = curve_widget.content_size.width or 80
        curve_widget.update(Group(
            *_render_area_chart(curve, benchmark_curve, capital, min(width, 100))
        ))
        for fill in record.fills:
            self._tape.append(
                (record.as_of, fill, record.positions.get(fill.ticker, 0)))
        self.query_one("#tape", Static).update(_tape_table(self._tape))
        self.query_one("#cycle-line", Static).update(Text(
            f"cycle {len(self._nav)}/{self._n_cycles} · {self._dates[-1]}",
            style=MUTED,
        ))

    def _update_stats(self, nav: float, fund_return: float,
                      benchmark_return: float, excess: float,
                      sharpe: float, max_dd: float) -> None:
        """One row of running tallies, live during the replay and refreshed
        with the engine's authoritative numbers at the end."""
        def tile(label: str, value: str, style: str) -> Text:
            return Text.assemble(
                (f"{label}\n", MUTED), (value, f"bold {style}"),
                justify="center",
            )

        assert self._spec is not None
        self.query_one("#stat-nav", Static).update(
            tile("PORTFOLIO", f"${nav:,.0f}", BRIGHT))
        self.query_one("#stat-return", Static).update(
            tile("RETURN", f"{fund_return:+.2%}",
                 GREEN if fund_return >= 0 else RED))
        self.query_one("#stat-bench", Static).update(
            tile(self._spec.benchmark, f"{benchmark_return:+.2%}",
                 GREEN if benchmark_return >= 0 else RED))
        self.query_one("#stat-excess", Static).update(
            tile("EXCESS", f"{excess:+.2%}",
                 GREEN if excess >= 0 else RED))
        self.query_one("#stat-sharpe", Static).update(
            tile("SHARPE", f"{sharpe:.2f}",
                 GREEN if sharpe > 1 else "yellow" if sharpe > 0 else RED))
        self.query_one("#stat-dd", Static).update(
            tile("MAX DRAWDOWN", f"{max_dd:.2%}", RED))

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
             f"rebalance · {m.n_cycles} cycles · {m.n_orders} orders · "
             f"{m.annualized_return_pct:+.1%} annualized",
             MUTED),
        ))
        self._update_stats(
            self._nav[-1] if self._nav else self._spec.capital,
            m.total_return_pct, m.benchmark_return_pct,
            m.excess_return_pct, m.sharpe_ratio, m.max_drawdown_pct,
        )
        self.query_one("#result-summary", Static).update(
            Text.assemble(("✓ ", f"bold {GREEN}"),
                          ("Saved backtest record to ", TEXT),
                          (str(path), f"bold {BRIGHT}")))
        self.query_one("#result-summary", Static).remove_class("hidden")
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
        # Saved keys become environment variables before any screen builds an
        # agent. Anything already exported wins — see hedge_fund/tui/keys.py.
        apply_credentials()
        ensure_mandates_dir()
        self.push_screen(HomeScreen())
