"""Terminal screens: paper trade a fund a session at a time, or backtest one over history."""

from __future__ import annotations

import json
import os
import shutil
from concurrent.futures import as_completed, ThreadPoolExecutor
from datetime import date as _date
from datetime import datetime, timedelta
from math import isfinite
from pathlib import Path
from typing import Literal

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

from hedge_fund.backtesting import backtest_fund, FundBacktestResult
from hedge_fund.backtesting.fund import (
    build_schedule,
    DailyValuation,
    performance_metrics,
)
from hedge_fund.brokers import Fill
from hedge_fund.data import CachedDataClient, FDClient
from hedge_fund.data.sessions import previous_day
from hedge_fund.fund import (
    custom_strategy,
    discover_funds,
    Fund,
    FundSpec,
    load_strategy,
    normalize_universe,
    SavedFund,
    StrategySpec,
)
from hedge_fund.llm import make_llm, provider_for, ThesisStream
from hedge_fund.models import Signal
from hedge_fund.paper import (
    deploy,
    DeployedFund,
    Ledger,
    LedgerError,
    list_deployed,
    load_deployed,
    next_session,
    NothingDue,
    redo,
    tick,
    validate_fund_name,
)
from hedge_fund.pipeline import (
    CycleRecord,
    DecisionRecord,
    FundState,
    is_rebalance_session,
    SessionRecord,
)
from hedge_fund.pipeline.stages import _MARK_LOOKBACK_DAYS
from hedge_fund.signals import ALPHA_MODEL_REGISTRY, get_investment_approach, LLMAgent
from hedge_fund.tui.keys import (
    apply_credentials,
    ENV_PATH,
    masked,
    missing_key,
    PROVIDER_ENV_VARS,
    save_credential,
)
from hedge_fund.tui.shared import (
    _agent_names,
    _BACKTEST_WEEKS,
    _BOARD_REFRESH,
    _DEFAULT_MODEL_LABEL,
    _fund_label,
    _render_area_chart,
    _SHORT_NAMES,
    _strategy_kind,
    _valid_date,
    _WARM_CHUNK,
    DEFAULT_CAPITAL,
    DEFAULT_RISK,
    DISPLAY_NAMES,
    ensure_mandates_dir,
    is_supported,
    load_api_models,
    MANDATES_DIR,
    MODE_LABELS,
    PAPER_DIR,
    RESEARCH_DIR,
    strategy_description,
    STRATEGY_DIR,
    UNIVERSE_PRESETS,
    VERSION,
)

# The palette, mirrored from app.tcss (rich styles can't read CSS variables).
GREEN = "#2bd97c"
CYAN = "#22d3ee"
RED = "#f87171"
TEXT = "#d9e6e0"
BRIGHT = "#f2f7f4"
MUTED = "#5f7268"

_CUSTOM = "custom"  # sentinel value in the strategy list for "build your own"


class HomeScreen(Screen):
    """The clean landing: wordmark, the two modes, the reasoning-model picker.
    Paper trading runs a fund on real market days; backtesting replays one
    over history. Building a fund lives inside each mode, not up here.
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
                        ("Paper trading\n", "bold"),
                        ("run a fund on real market days", MUTED)),
                    id="paper"),
                None,
                Option(
                    Text.assemble(
                        ("Backtesting\n", "bold"),
                        ("test a fund over history", MUTED)),
                    id="backtest"),
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
        if event.option.id == "paper":
            self.app.push_screen(PaperScreen())
        elif event.option.id == "backtest":
            self.app.push_screen(FundSelectScreen())


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
                row.append(f"{name:<18}", style=None if reachable else MUTED)
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
    """'Backtest a mandate', master-detail: mandate slots on the left, the
    highlighted mandate's latest backtest stats and its backtest history
    (newest first) on the right. Enter opens the backtest window picker.
    Refreshes on resume.
    """

    BINDINGS = [
        Binding("escape", "back", "back"),
        Binding("d", "delete", "delete mandate"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._summaries: dict[tuple[str, float], dict | None] = {}

    def compose(self) -> ComposeResult:
        with Horizontal(id="select"):
            with Vertical(id="select-rail"):
                yield Static(Text("YOUR MANDATES", style=MUTED), classes="rail-title")
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
                Text("No funds yet — build one under Paper trading and it shows up here too.",
                     style=MUTED))
            return
        for i, entry in enumerate(self._slots):
            if entry.spec is None:
                menu.add_option(Option(Text(f"{entry.path.name} — Unavailable\n{entry.error}", style=MUTED),
                                       id=f"unavailable:{i}", disabled=True))
            else:
                menu.add_option(Option(
                    _slot_card(i, entry.spec, _last_score(entry.spec.name)), id=f"fund:{i}"))
        # Options added after mount leave `highlighted` unset — pin it so the
        # detail pane fills in and Enter works without an arrow press first.
        first = next((i for i, entry in enumerate(self._slots) if entry.spec is not None), None)
        menu.highlighted = first
        menu.focus()
        if first is not None:
            self._show_detail(first)
        else:
            self.query_one("#detail-body", Static).update(
                Text("Saved mandates are unavailable. Recreate them in the builder or update their configurations.", style=MUTED))

    @on(OptionList.OptionHighlighted, "#select-menu")
    def _hover(self, event: OptionList.OptionHighlighted) -> None:
        oid = (event.option.id or "") if event.option else ""
        if oid.startswith("fund:"):
            self._show_detail(int(oid.split(":")[1]))

    @on(OptionList.OptionSelected, "#select-menu")
    def _choose(self, event: OptionList.OptionSelected) -> None:
        oid = event.option.id or ""
        if oid.startswith("fund:"):
            spec = self._slots[int(oid.split(":")[1])].spec
            if spec is None:
                return
            self.app.push_screen(BacktestScreen(spec))

    def action_delete(self) -> None:
        menu = self.query_one("#select-menu", OptionList)
        if not self._slots or menu.highlighted is None:
            return
        # Remember what was asked for: the list repopulates on resume, so the
        # highlighted index is not trustworthy by the time the callback fires.
        entry = self._slots[menu.highlighted]
        if entry.spec is None:
            return
        self._pending_delete = (entry.path, entry.spec)
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
        spec = self._slots[i].spec
        if spec is None:
            return
        self.query_one("#detail-body", Static).update(
            _fund_detail(spec, self._history(spec.name)))

    def _history(self, name: str) -> list[dict]:
        """Every backtest of this mandate, newest first, as light summaries.
        Cached by (path, mtime) so arrowing the list stays instant."""
        out: list[dict] = []
        for p in _receipts(name):
            mtime = p.stat().st_mtime
            key = (str(p), mtime)
            if key not in self._summaries:
                self._summaries[key] = _summarize(p, mtime)
            summ = self._summaries[key]
            if summ is not None:
                out.append(summ)
        out.sort(key=lambda s: s["mtime"], reverse=True)
        return out


def _saved_funds() -> list[SavedFund]:
    """Valid and unavailable saved mandates, shared by both pickers."""
    return discover_funds(MANDATES_DIR)


def _fund_name_taken(name: str) -> bool:
    """A name is taken if a saved definition or a paper fund already owns it;
    the builder refuses both so one name means one fund everywhere."""
    return (MANDATES_DIR / f"{name}.yaml").exists() or (PAPER_DIR / name).exists()


def _newest_paper_universe() -> list[str] | None:
    """The tickers of the most recently created paper fund — the builder's
    ticker step prefills from it, so a returning user just presses enter."""
    newest: DeployedFund | None = None
    for directory in list_deployed(PAPER_DIR):
        try:
            deployed = load_deployed(directory)
        except ValueError:
            continue
        if newest is None or deployed.created > newest.created:
            newest = deployed
    return newest.universe if newest else None


def _delete_fund(path: Path, name: str, *, with_history: bool) -> int:
    """Remove a mandate, and its backtest results too when asked. Returns how
    many files went, so the caller can say so. Paper funds deployed from it
    are untouched: they carry their own snapshot of the mandate."""
    targets = [path, *(_receipts(name) if with_history else [])]
    for target in targets:
        target.unlink(missing_ok=True)
    return len(targets)


def _wipe_fund(name: str) -> None:
    """Remove everything that answers to *name*: the saved definition, its
    backtest results, and the paper fund — ledger, book, events — if one was
    deployed. Called only after the user has said yes to `ConfirmWipeScreen`,
    whether to delete the fund or to let a new one take its name."""
    (MANDATES_DIR / f"{name}.yaml").unlink(missing_ok=True)
    for receipt in _receipts(name):
        receipt.unlink(missing_ok=True)
    shutil.rmtree(PAPER_DIR / name, ignore_errors=True)


def _wipe_manifest(name: str, then: str) -> Text:
    """What wiping *name* destroys, named exactly, and what *then* follows."""
    lines = Text()
    if (MANDATES_DIR / f"{name}.yaml").exists():
        lines.append(f"{name}.yaml\n", style=TEXT)
        lines.append("  the saved definition — strategies, staff, risk, capital\n", style=MUTED)
    backtests = len(_receipts(name))
    if backtests:
        lines.append(f"{backtests} {'backtest' if backtests == 1 else 'backtests'}\n", style=CYAN)
        lines.append("  saved results\n", style=MUTED)
    directory = PAPER_DIR / name
    if directory.exists():
        try:
            sessions = len(Ledger(directory).records())
            what = f"{sessions} {'session' if sessions == 1 else 'sessions'} of ledger"
        except (LedgerError, OSError, ValueError):
            what = "its ledger"
        lines.append("paper fund\n", style=RED)
        lines.append(f"  {what}, the book, and every event — the track record\n", style=MUTED)
    lines.append(f"\n{then} None of this can be recovered.", style=MUTED)
    return lines


class ConfirmWipeScreen(ModalScreen[bool]):
    """Everything with a name is about to go — because the user pressed `d`
    on the fund, or gave the builder a name that already belongs to one.
    The irreversible things in this app all look the same: what goes, named
    exactly, and one key to say yes.
    """

    BINDINGS = [
        Binding("escape", "cancel", "keep it"),
        Binding("enter", "confirm", "yes", priority=True),
    ]

    def __init__(self, name: str, *, replacing: bool = False) -> None:
        super().__init__()
        self._name = name
        self._replacing = replacing

    def compose(self) -> ComposeResult:
        verb = "Replace" if self._replacing else "Delete"
        then = "The new fund takes the name." if self._replacing else "The name is free again."
        yes = ("replace it — the new fund starts from nothing" if self._replacing else "delete it")
        no = "keep it and pick another name" if self._replacing else "keep it"
        with Vertical(id="confirm"):
            yield Static(Text.assemble(
                (f"{verb} ", f"bold {BRIGHT}"), (self._name, f"bold {RED}"), ("?", f"bold {BRIGHT}")),
                id="confirm-q")
            yield Static(_wipe_manifest(self._name, then), id="confirm-files")
            yield Static(Text.assemble(
                ("enter", f"bold {RED}"), (f"  {yes}\n", MUTED),
                ("esc", f"bold {BRIGHT}"), (f"    {no}", MUTED)),
                id="confirm-keys")
        yield Footer()

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)


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
        if self._backtests:
            lines.append(
                f"{self._backtests} "
                f"{'backtest' if self._backtests == 1 else 'backtests'}\n",
                style=CYAN)
            lines.append("  saved results — kept unless you press ctrl+d",
                         style=MUTED)
        else:
            lines.append("No saved backtests.", style=MUTED)
        lines.append("\n\nPaper funds deployed from this mandate keep their own copy.",
                     style=MUTED)
        return lines

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_delete_mandate(self) -> None:
        self.dismiss("mandate")

    def action_delete_all(self) -> None:
        self.dismiss("all")


def _summarize(path: Path, mtime: float) -> dict | None:
    """One saved backtest result as the light summary the history pane
    renders. None if the file is unreadable or not a backtest."""
    try:
        d = json.loads(path.read_text())
        if not isinstance(d, dict) or "metrics" not in d:
            return None
        m = d["metrics"]
        return {
            "kind": "backtest", "mtime": mtime, "fund": d.get("fund", ""),
            "universe": d.get("universe", []),
            "start": d.get("start", ""), "end": d.get("end", ""),
            "benchmark": d.get("benchmark", "SPY"),
            "total": m["total_return_pct"],
            "annualized": m["annualized_return_pct"],
            "sharpe": m["sharpe_ratio"], "maxdd": m["max_drawdown_pct"],
            "benchret": m["benchmark_return_pct"],
            "excess": m["excess_return_pct"], "n_cycles": m["n_cycles"],
        }
    except (json.JSONDecodeError, KeyError, OSError, TypeError, UnicodeError):
        return None


def _receipts(name: str) -> list[Path]:
    """Every saved backtest of a mandate, newest first. Filenames start with
    the mandate's name, but names can be prefixes of each other, so the
    result's own `fund` field is what decides."""
    paths = []
    for p in RESEARCH_DIR.glob(f"{name}-*.json"):
        summary = _summarize(p, 0.0)
        if summary is not None and summary["fund"] == name:
            paths.append(p)
    return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)


def _last_universe(name: str) -> list[str] | None:
    """The tickers this mandate was last backtested over — the ticker inputs
    prefill from it, so a returning user just presses enter."""
    for path in _receipts(name):
        summary = _summarize(path, 0.0)
        if summary and summary["universe"]:
            return summary["universe"]
    return None


def _last_score(name: str) -> tuple[float, float, str] | None:
    """The mandate's most recent backtest result, if any: (total return,
    excess return, benchmark). A quiet scoreboard on each slot."""
    for path in _receipts(name):
        summary = _summarize(path, 0.0)
        if summary:
            return (summary["total"], summary["excess"], summary["benchmark"])
    return None


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
    card.append("\n     " + ", ".join(MODE_LABELS[s.blend.mode] for s in spec.strategies), style=MUTED)
    return card


def _fund_detail(spec: FundSpec, history: list[dict]) -> Group:
    """The right pane: the mandate's identity, its latest backtest stats, then
    every backtest, newest first, each with the tickers it was run over."""
    staff = ", ".join(s.title for s in spec.strategies)
    parts: list = [
        Text(spec.name, style=f"bold {BRIGHT}"),
        Text(f"{staff}  ·  {spec.rebalance}  ·  ${spec.capital:,.0f}", style=MUTED),
    ]
    parts.extend(Text(f"{s.title}: {strategy_description(s)}", style=MUTED) for s in spec.strategies)

    if not history:
        parts.append(Text("\nNo backtests yet.", style=MUTED))
        parts.append(Text("\nEnter to backtest this mandate over history",
                          style=MUTED))
        return Group(*parts)

    latest = history[0]
    facts = [f"{latest['start']} → {latest['end']}",
             f"{latest['n_cycles']} cycles"]
    if latest["universe"]:
        facts.append(" ".join(latest["universe"]))
    parts.append(Text("\nLATEST BACKTEST", style=f"bold {BRIGHT}"))
    parts.append(Text("  ·  ".join(facts), style=MUTED))
    parts.append(_stat_list(latest))

    parts.append(Text("\nBACKTESTS", style=f"bold {BRIGHT}"))
    # Three columns, not four. The kind and the number are pinned with no_wrap
    # so a narrow pane can never drop the result — the tickers ride along in
    # the middle column and are the only thing allowed to ellipsize.
    log = Table(box=None, show_header=False, padding=(0, 1), pad_edge=False,
                expand=True)
    log.add_column(no_wrap=True)                          # kind
    log.add_column(overflow="ellipsis", no_wrap=True)     # when · tickers
    log.add_column(justify="right", no_wrap=True)         # headline number
    for h in history[:12]:
        up = h["total"] >= 0
        when = Text(f"{h['start']} → {h['end']}", style=MUTED)
        if h["universe"]:
            when.append(f"  {_short_tickers(h['universe'])}", style=CYAN)
        log.add_row(
            Text("backtest", style=MUTED), when,
            Text(f"{h['total']:+.1%}", style=GREEN if up else RED),
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
    elif signal.metadata.get("signal") in ("bullish", "bearish", "neutral"):
        word = signal.metadata["signal"]
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
        text = desk.signal.reasoning or ""
    elif desk.stream is not None:
        text = desk.stream.thesis
    else:
        text = ""
    return Text(" ".join(text.split()), style=TEXT)


def _report_nav(record: CycleRecord | DecisionRecord, prefix: str = "") -> list[Option]:
    """The report's left rail: every signal as ONE line, then the book.

    A thesis runs paragraphs — rendering them inline made a table where a
    single signal filled the screen. Here each signal is a scannable row and
    the full thesis goes to the detail pane, so the fund's thinking stays
    navigable on a default-size terminal.

    *prefix* namespaces the option ids when one rail carries two records
    (a session that executed one decision and made the next).
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
            options.append(Option(row, id=f"{prefix}sig:{si}:{sj}"))

    options.append(Option(Text(""), disabled=True))
    options.append(Option(Text("THE BOOK", style=f"bold {BRIGHT}"), disabled=True))
    if record.clamps:
        options.append(Option(
            Text(f" Risk limits ({len(record.clamps)})", style=TEXT), id=f"{prefix}sec:risk"))
    if isinstance(record, CycleRecord):
        options.append(Option(
            Text(f" Orders ({len(record.orders)})", style=TEXT), id=f"{prefix}sec:orders"))
    options.append(Option(Text(" Portfolio" if isinstance(record, CycleRecord) else " Proposed allocations", style=TEXT), id=f"{prefix}sec:portfolio"))
    return options


def _report_detail(record: CycleRecord | DecisionRecord, oid: str) -> Group | None:
    """The right pane for one rail option (id without any prefix)."""
    if oid.startswith("sig:"):
        _, si, sj = oid.split(":")
        return _signal_detail(record, int(si), int(sj))
    if oid == "sec:risk":
        return _risk_detail(record)
    if oid == "sec:orders" and isinstance(record, CycleRecord):
        return _orders_detail(record)
    if oid == "sec:portfolio":
        return (_portfolio_detail(record) if isinstance(record, CycleRecord)
                else _proposal_detail(record))
    return None


# One session may carry two records: the decision executed at this close and
# the decision made at it. The rail shows both, namespaced by these prefixes.
_EXECUTED = "x:"
_DECIDED = "d:"


def _session_nav(record: SessionRecord) -> list[Option]:
    """The rail for a whole session: the executed cycle first (that is what
    moved the book), then the decision made at this close, then — when the
    session did neither — just the marked book."""
    options: list[Option] = []
    if record.executed is not None:
        options.append(Option(Text.assemble(
            ("EXECUTED", f"bold {GREEN}"),
            (f"  decided {record.executed.as_of}", MUTED)), disabled=True))
        options.extend(_report_nav(record.executed, _EXECUTED))
    if record.decision is not None:
        if options:
            options.append(Option(Text(""), disabled=True))
        options.append(Option(Text.assemble(
            ("DECIDED", f"bold {CYAN}"),
            ("  executes next session", MUTED)), disabled=True))
        options.extend(_report_nav(record.decision, _DECIDED))
    if not options:
        options.append(Option(Text("THE BOOK", style=f"bold {BRIGHT}"), disabled=True))
        options.append(Option(Text(" Portfolio", style=TEXT), id="book"))
    return options


def _session_detail(record: SessionRecord, oid: str) -> Group | None:
    if oid.startswith(_EXECUTED) and record.executed is not None:
        return _report_detail(record.executed, oid[len(_EXECUTED):])
    if oid.startswith(_DECIDED) and record.decision is not None:
        return _report_detail(record.decision, oid[len(_DECIDED):])
    if oid == "book":
        return _session_book(record)
    return None


def _session_book(record: SessionRecord) -> Group:
    """The marked book at a session's close, for sessions that only valued."""
    head = [
        Text("PORTFOLIO", style=f"bold {BRIGHT}"),
        Text(f"marked at the {record.session} close · no orders this session", style=MUTED),
    ]
    if not record.positions:
        return Group(*head, Text("flat — no positions", style=MUTED))
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
        table.add_row(ticker, side, f"{shares:+d}",
                      Text(f"${value:+,.0f}", style=tone),
                      Text(f"{value / record.nav:+.1%}", style=tone))
    return Group(*head, Text(""), table)


def _first_selectable(nav: OptionList) -> int | None:
    for i in range(nav.option_count):
        if not nav.get_option_at_index(i).disabled:
            return i
    return None


def _signal_detail(record: CycleRecord | DecisionRecord, si: int, sj: int) -> Group:
    """One analyst's full view: who, what, and the whole written thesis."""
    sr = record.strategies[si]
    signal = sr.signals[sj]
    _, word, tone = _verdict(signal)
    confidence = signal.metadata.get("confidence")
    jev = signal.metadata.get("provider_metadata", {}).get("jev")
    header = Text()
    header.append(signal.ticker, style=f"bold {CYAN}")
    header.append("  ·  ", style=MUTED)
    header.append(DISPLAY_NAMES.get(signal.model_name, signal.model_name),
                  style=f"bold {BRIGHT}")
    facts = Text()
    facts.append(word, style=f"bold {tone}")
    if confidence is not None:
        label = "investment conviction" if jev else "confidence"
        facts.append(f"  ·  {confidence:.0f}% {label}", style=MUTED)
    facts.append(f"  ·  conviction {signal.value:+.2f}", style=MUTED)
    facts.append(f"  ·  {sr.name}", style=MUTED)
    return Group(
        header,
        facts,
        Text(""),
        Text(signal.reasoning or "no thesis recorded",
             style=TEXT if signal.reasoning else MUTED),
        *([Text(""), _jev_details(jev)] if jev else []),
    )


def _jev_details(metadata: dict) -> Text:
    """Explain saved typed answers in the existing detail pane."""
    answers = metadata["response"]["answers"]
    probabilities = answers["direction"]["probabilities"]
    details = Text("Jev answer-option probabilities\n", style=MUTED)
    details.append("  ·  ".join(
        f"{direction.capitalize()} {probabilities[direction]:.1%}"
        for direction in ("bullish", "bearish", "neutral")), style=TEXT)
    details.append("\nThese describe the supplied answer options, not investment returns.\n\n")
    details.append("Jev native answer confidence\n")
    details.append("\n".join(
        f"{label}: {answers[name]['confidence']:.1%}"
        for name, label in (
            ("direction", "Direction"),
            ("bullish_strength", "Bullish strength"),
            ("bearish_strength", "Bearish strength"),
        )), style=TEXT)
    return details


def _risk_detail(record: CycleRecord | DecisionRecord) -> Group:
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


def _proposal_detail(record: DecisionRecord) -> Group:
    return Group(
        Text("PROPOSED ALLOCATIONS", style=f"bold {BRIGHT}"),
        Text("Targets only; no orders or fills have occurred.", style=MUTED),
        *(Text(f"{ticker}: {weight:+.2%}", style=TEXT)
          for ticker, weight in sorted(record.final_weights.items())),
        *(Text(f"{strategy.name}: zero exposure — {strategy.flat_reason.replace('_', ' ')}", style=MUTED)
          for strategy in record.strategies if strategy.flat_reason),
    )


def _portfolio_detail(record: CycleRecord) -> Group:
    target_net = record.equity_before * sum(record.final_weights.values())
    actual_net = sum(shares * record.marks[ticker] for ticker, shares in record.positions.items())
    details = [
        Text("PORTFOLIO", style=f"bold {BRIGHT}"),
        Text(f"Target net ${target_net:+,.2f} · Actual net ${actual_net:+,.2f} · Difference ${actual_net - target_net:+,.2f}", style=MUTED),
    ]
    if any(s.blend.mode == "dollar_neutral" for s in record.spec.strategies):
        details.append(Text("Dollar-neutral rules apply to strategy targets. Whole-share holdings can differ; other strategies can add net exposure.", style=MUTED))
    if record.risk_scale_factor is not None and record.risk_scale_factor < 1:
        details.append(Text(f"Risk limits scaled all strategy targets to {record.risk_scale_factor:.1%} of their requested exposure.", style=MUTED))
    for strategy in record.strategies:
        if strategy.flat_reason:
            details.append(Text(f"{strategy.name}: zero exposure — {_FLAT_REASONS[strategy.flat_reason]}. Allocated capital remains unused.", style=MUTED))
    if not record.positions:
        return Group(*details, Text("flat — no positions", style=MUTED))
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
    return Group(*details, Text(""), table)


def _book_summary(record: CycleRecord | SessionRecord) -> Text:
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


class _PaperSnapshot:
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
        try:
            self.records = self.ledger.records()
            self.state = self.ledger.replay(self.deployed.spec.capital)
        except LedgerError as exc:
            self.error = str(exc)

    @property
    def spec(self) -> FundSpec:
        return self.deployed.spec

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
        return performance_metrics(self.spec.capital, dates, nav, bench, cycles)

    def status(self) -> Text:
        """One line: the same facts as `aihf paper status`."""
        line = Text()
        if self.error:
            line.append("✗ LEDGER ERROR  ", style=f"bold {RED}")
            line.append(self.error, style=RED)
            return line
        if self.halted:
            line.append("■ HALTED  ", style=f"bold {RED}")
            line.append(self.halted, style=RED)
            return line
        if self.last_session is None:
            line.append("● NEW  ", style=f"bold {CYAN}")
            line.append("no sessions yet", style=MUTED)
        else:
            line.append("● LIVE  ", style=f"bold {GREEN}")
            line.append(f"last session {self.last_session}", style=TEXT)
        return line

    def badge(self) -> Text:
        """The state as a colored glyph and a quiet word, for a header line.
        The reason behind a halt or an error is told where there is room."""
        glyph, word, tone = (
            ("✗", "ledger error", RED) if self.error else
            ("■", "halted", RED) if self.halted else
            ("●", "new", CYAN) if self.last_session is None else
            ("●", "live", GREEN))
        return Text.assemble((f"{glyph} ", tone), (word, MUTED))


def _paper_slot(index: int, snap: _PaperSnapshot) -> Text:
    """One fund in the paper rail: number, name, and how it is doing. One
    line; everything else about the fund belongs to the detail pane."""
    card = Text()
    card.append(f" {index + 1:02d}  ", style=MUTED)
    card.append(snap.deployed.name, style=TEXT)
    if snap.error:
        card.append("   ✗ ledger", style=RED)
    elif snap.halted:
        card.append("   ■ halted", style=RED)
    elif snap.records:
        ret = snap.nav / snap.spec.capital - 1
        card.append(f"   {ret:+.1%}", style=GREEN if ret >= 0 else RED)
        card.append("  ● live", style=GREEN)
    else:
        card.append("   ● new", style=CYAN)
    return card


_PERIOD_WORD = {"daily": "day", "weekly": "week", "monthly": "month"}

# The reason the app's `h` writes to the kill switch. The ledger wants one for
# `aihf paper status` and the event log; the app does not ask, so it is not shown.
_APP_HALT = "halted in the app"

_FLAT_REASONS = {
    "no_eligible_positions": "no eligible positions",
    "missing_long_side": "no eligible longs to balance the shorts",
    "missing_short_side": "no eligible shorts to balance the longs",
}


def _flat_line(decision: DecisionRecord) -> str:
    """Why a decision has no targets, in the blender's own words. A
    dollar-neutral desk with conviction but no short to balance it is the
    common case, and "no conviction" would be the wrong story to tell."""
    reasons = [(s.name, _FLAT_REASONS[s.flat_reason]) for s in decision.strategies if s.flat_reason]
    if not reasons:
        return "flat — no conviction cleared the bar"
    if len(decision.strategies) == 1:
        return f"flat — {reasons[0][1]}"
    return "flat — " + "; ".join(f"{name}: {why}" for name, why in reasons)


def _weights_line(decision: DecisionRecord, limit: int = 6) -> Text:
    """A decision's non-zero targets on one line, largest first."""
    targets = sorted(((t, w) for t, w in decision.final_weights.items() if w),
                     key=lambda x: -abs(x[1]))
    if not targets:
        return Text(_flat_line(decision), style=MUTED)
    line = Text()
    for i, (ticker, weight) in enumerate(targets[:limit]):
        if i:
            line.append("  ·  ", style=MUTED)
        line.append(ticker, style=TEXT)
        line.append(f" {weight:+.0%}", style=GREEN if weight > 0 else RED)
    if len(targets) > limit:
        line.append(f"  ·  +{len(targets) - limit} more", style=MUTED)
    return line


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


def _next_run_rows(snap: _PaperSnapshot) -> list[tuple[str, Text | str]]:
    """What the next run will do, from the ledger alone — no network on a
    highlight. Two steps: what happens to the pending decision, then
    whether a new one is made. The exact date is resolved when the user
    asks to run."""
    if snap.halted:
        rows: list[tuple[str, Text | str]] = [("Halted", Text("r to resume before it can run", style=RED))]
        if snap.halted not in (_APP_HALT, "halted"):  # a reason given from the CLI
            rows.append(("", Text(snap.halted, style=MUTED)))
        return rows
    rows: list[tuple[str, Text | str]] = []
    if snap.pending is not None:
        rows.append(("First", Text.assemble(
            "execute the ", (snap.pending.as_of, BRIGHT), " decision")))
        rows.append(("", _weights_line(snap.pending)))
    elif snap.last_session is None:
        rows.append(("First", "mark the book at the latest completed close"))
    else:
        rows.append(("First", "mark the book"))
    cadence = snap.spec.rebalance
    if snap.last_session is None:
        rows.append(("Then", "make the first decision"))
    elif cadence == "daily":
        rows.append(("Then", "make a new decision"))
    else:
        rows.append(("Then", f"make a new decision if it opens a new {_PERIOD_WORD[cadence]}"))
    return rows


def _paper_detail(snap: _PaperSnapshot, width: int = 60) -> Group:
    """The right pane, top to bottom: who the fund is, what the next run
    does, how it has done, its last few sessions. One bold line (the name);
    color only where it means something — gains, losses, state."""
    spec = snap.spec
    staff = ", ".join(s.title for s in spec.strategies)
    parts: list = [
        Text.assemble((snap.deployed.name, f"bold {BRIGHT}"), "   ", snap.badge()),
        Text(f"{staff} · {spec.rebalance} · ${spec.capital:,.0f} · {' '.join(snap.deployed.universe)}",
             style=MUTED),
        Text(""),
    ]
    if snap.error:
        parts.append(Text(snap.error, style=RED))
        return Group(*parts)
    parts += [_section("NEXT RUN"), _facts(_next_run_rows(snap))]
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
        ])]
        if n >= 2:  # one point is a flat block, not a curve
            parts.append(Text(""))
            parts.extend(_render_area_chart(nav, bench, spec.capital, width))
        parts += [Text(""), _section("SESSIONS")]
        navs = [spec.capital, *(r.nav for r in snap.records)]
        shown = min(n, 3)
        for i in range(n - 1, n - 1 - shown, -1):
            parts.append(Text(" ").append_text(_session_row(snap.records[i], navs[i])))
        if n > shown:
            parts.append(Text(f"   … {n - shown} more · s for all", style=MUTED))
    return Group(*parts)


def _session_row(record: SessionRecord, prev_nav: float) -> Text:
    """One session in the fund's history rail: date, day change, what happened."""
    change = record.nav / prev_nav - 1 if prev_nav else 0.0
    row = Text()
    row.append(f" {record.session}", style=TEXT)
    row.append(f"  {change:+.2%}", style=GREEN if change >= 0 else RED)
    if record.executed is not None:
        n = len(record.executed.fills)
        row.append(f"  {n} {'fill' if n == 1 else 'fills'}", style=MUTED)
    if record.decision is not None:
        row.append("  decided", style=MUTED)
    return row


def _session_overview(record: SessionRecord) -> Group:
    """The detail pane for a highlighted session: what it did to the book,
    in a few lines. Enter opens the full report."""
    parts: list = [
        Text.assemble((record.session, f"bold {BRIGHT}"),
                      ("  ·  rebalance session" if record.rebalance else "  ·  valuation only", MUTED)),
        _book_summary(record),
        Text(""),
    ]
    if record.executed is not None:
        x = record.executed
        parts.append(Text.assemble(
            ("EXECUTED  ", f"bold {GREEN}"),
            (f"decision from {x.as_of} · {len(x.orders)} orders · {len(x.fills)} fills", MUTED)))
        for fill in x.fills[:8]:
            tone = GREEN if fill.side == "buy" else RED
            parts.append(Text.assemble(
                (f"  {fill.side.upper():<4} ", f"bold {tone}"),
                (f"{fill.quantity:,} {fill.ticker}", TEXT),
                (f" @ ${fill.price:,.2f}", MUTED)))
        if len(x.fills) > 8:
            parts.append(Text(f"  … {len(x.fills) - 8} more", style=MUTED))
        parts.append(Text(""))
    if record.decision is not None:
        d = record.decision
        n_signals = sum(len(sr.signals) for sr in d.strategies)
        parts.append(Text.assemble(
            ("DECIDED  ", f"bold {CYAN}"),
            (f"{n_signals} signals · executes at the next session's close", MUTED)))
        targets = sorted(((t, w) for t, w in d.final_weights.items() if w), key=lambda x: -abs(x[1]))
        for ticker, weight in targets[:8]:
            parts.append(Text.assemble(
                (f"  {ticker:<6}", f"bold {CYAN}"),
                (f"{weight:+.1%}", GREEN if weight > 0 else RED)))
        if not targets:
            parts.append(Text(f"  {_flat_line(d)}", style=MUTED))
        parts.append(Text(""))
    parts.append(Text("enter for the full report", style=MUTED))
    return Group(*parts)


# ---- running a session ----------------------------------------------------

def _next_weekday(after: str) -> str:
    """The first Monday–Friday strictly after *after* (YYYY-MM-DD). Holidays
    are not consulted; this is a hint, not a schedule."""
    day = _date.fromisoformat(after) + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day.isoformat()


def _run_plan(name: str, state: FundState, due: str | None, spec: FundSpec) -> Text:
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
        body.append_text(_weights_line(state.pending))
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


def _resolve_next_session(directory: Path) -> tuple[DeployedFund, FundState, str | None]:
    """Load the fund, replay its ledger, and ask the market which session is
    due. The one place the confirm modal touches the network."""
    deployed = load_deployed(directory)
    state = Ledger(directory).replay(deployed.spec.capital)
    with FDClient() as raw:
        due = next_session(CachedDataClient(raw), deployed.spec.benchmark, state.last_session)
    return deployed, state, due


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
            (f" through {due}?" if due else
             f" again through {state.last_session}?" if self._verdict == "redo" else "?",
             f"bold {BRIGHT}")))
        self.query_one("#run-body", Static).update(_run_plan(deployed.name, state, due, deployed.spec))
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


class PaperScreen(Screen):
    """Paper trading. The fund list is the home of the fund: every deployed
    fund on the left, the highlighted one's state and its next run on the
    right. Enter runs it (through the approval step); `s` opens its history;
    `h`/`r` work the kill switch; the last row builds a new fund.
    """

    BINDINGS = [
        Binding("escape", "back", "back"),
        Binding("enter", "run", "run next session", priority=True),
        Binding("s", "sessions", "sessions"),
        Binding("h", "halt", "halt"),
        Binding("r", "resume", "resume"),
        Binding("d", "delete", "delete"),
    ]

    def __init__(self, select: str | None = None, run: bool = False) -> None:
        super().__init__()
        self._snaps: list[_PaperSnapshot | None] = []
        self._select = select   # highlight this fund on first paint
        self._run_on_mount = run  # ...and open its approval step right away

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
        if self._run_on_mount:
            self._run_on_mount = False
            self.call_after_refresh(self.action_run)

    def on_screen_resume(self) -> None:
        current = self._current()
        self._populate(current.deployed.name if current else None)

    # ---- the list ---------------------------------------------------------

    def _populate(self, select: str | None) -> None:
        menu = self.query_one("#paper-menu", OptionList)
        menu.clear_options()
        self._snaps = []
        for i, directory in enumerate(list_deployed(PAPER_DIR)):
            try:
                snap = _PaperSnapshot(directory)
            except ValueError as exc:
                self._snaps.append(None)
                menu.add_option(Option(
                    Text(f" {directory.name} — Unavailable\n     {exc}", style=MUTED), disabled=True))
                continue
            self._snaps.append(snap)
            menu.add_option(Option(_paper_slot(i, snap), id=f"paper:{i}"))
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

    def _current(self) -> _PaperSnapshot | None:
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
                detail.update(_paper_detail(snap, min(width, 100)))
        elif oid == "build":
            blurb = Text()
            if not self._snaps:
                blurb.append("No funds yet.\n\n", style=f"bold {BRIGHT}")
            blurb.append(
                "Build a fund here and it starts paper trading at once: pick its "
                "strategies, capital, cadence and tickers, and it gets a ledger, a "
                "book and a kill switch of its own under\n" + str(PAPER_DIR) + "\n\n"
                "Then run it a session at a time with enter, or from a scheduler with "
                "`aihf paper tick <name>`.", style=MUTED)
            detail.update(blurb)

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
        directory = snap.directory

        def resume() -> None:
            if _demand_run_keys(self.app, resume):
                self.app.push_screen(RunConfirmScreen(directory),
                                     lambda verdict: self._after_confirm(directory, verdict))
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
        snap.ledger.halt(_APP_HALT)
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
        _wipe_fund(name)
        self.notify(f"Deleted {name}", severity="warning")
        self._populate(None)


class SessionsScreen(Screen):
    """One fund's history: the running numbers, the equity curve, and every
    session it has recorded. Enter on a session opens its full report.
    Running and the kill switch live on the fund list, not here.
    """

    BINDINGS = [Binding("escape", "back", "back")]

    def __init__(self, directory: Path) -> None:
        super().__init__()
        self._directory = directory
        self._snap: _PaperSnapshot | None = None
        self._shown: list[SessionRecord] = []  # newest first, as listed

    def compose(self) -> ComposeResult:
        with Vertical(id="pf"):
            yield Static("", id="pf-head")
            yield Static("", id="pf-status")
            with Horizontal(id="stats"):
                yield Static("", id="stat-nav")
                yield Static("", id="stat-return")
                yield Static("", id="stat-bench")
                yield Static("", id="stat-excess")
                yield Static("", id="stat-sharpe")
                yield Static("", id="stat-dd")
            with Vertical(id="curve-box"):
                yield Static("", id="curve")
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
            snap = _PaperSnapshot(self._directory)
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
            Text(f"{staff}  ·  {spec.rebalance}  ·  ${spec.capital:,.0f}"
                 f"  ·  {' '.join(snap.deployed.universe)}", style=MUTED),
        ))
        self.query_one("#pf-status", Static).update(snap.status())
        self._render_numbers(snap)
        self._render_sessions(snap)

    def _render_numbers(self, snap: _PaperSnapshot) -> None:
        curve_box = self.query_one("#curve-box", Vertical)
        curve_box.border_title = "equity curve"
        curve_box.border_subtitle = f"[{GREEN}]██[/] fund   [{CYAN}]──[/] {snap.spec.benchmark}"
        if not snap.records:
            self.query_one("#stats", Horizontal).add_class("hidden")
            self.query_one("#curve", Static).update(
                Text("The curve starts with the first session.", style=MUTED))
            return
        self.query_one("#stats", Horizontal).remove_class("hidden")
        m = snap.metrics()
        _update_stat_tiles(self, snap.spec.benchmark, snap.nav, m.total_return_pct,
                           m.benchmark_return_pct, m.excess_return_pct,
                           m.sharpe_ratio, m.max_drawdown_pct)
        _, nav, bench = snap.curves()
        curve_widget = self.query_one("#curve", Static)
        width = curve_widget.content_size.width or 80
        curve_widget.update(Group(*_render_area_chart(nav, bench, snap.spec.capital, min(width, 100))))

    def _render_sessions(self, snap: _PaperSnapshot) -> None:
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
        for i, record in enumerate(self._shown):
            index = len(snap.records) - 1 - i
            menu.add_option(Option(_session_row(record, navs[index]), id=f"s:{i}"))
        menu.highlighted = 0
        menu.focus()

    @on(OptionList.OptionHighlighted, "#pf-sessions")
    def _highlight(self, event: OptionList.OptionHighlighted) -> None:
        oid = (event.option.id or "") if event.option else ""
        if oid.startswith("s:"):
            record = self._shown[int(oid.split(":")[1])]
            self.query_one("#detail-pane", Static).update(_session_overview(record))
            self.query_one("#report-detail", VerticalScroll).scroll_home(animate=False)

    @on(OptionList.OptionSelected, "#pf-sessions")
    def _open(self, event: OptionList.OptionSelected) -> None:
        oid = event.option.id or ""
        if oid.startswith("s:") and self._snap is not None:
            record = self._shown[int(oid.split(":")[1])]
            self.app.push_screen(SessionReportScreen(self._snap.deployed.name, record))


def _update_stat_tiles(screen: Screen, benchmark: str, nav: float, fund_return: float,
                       benchmark_return: float, excess: float,
                       sharpe: float, max_dd: float) -> None:
    """One row of tallies, shared by the backtest board and the paper fund."""
    def tile(label: str, value: str, style: str) -> Text:
        return Text.assemble((f"{label}\n", MUTED), (value, f"bold {style}"), justify="center")

    screen.query_one("#stat-nav", Static).update(tile("PORTFOLIO", f"${nav:,.0f}", BRIGHT))
    screen.query_one("#stat-return", Static).update(
        tile("RETURN", f"{fund_return:+.2%}", GREEN if fund_return >= 0 else RED))
    screen.query_one("#stat-bench", Static).update(
        tile(benchmark, f"{benchmark_return:+.2%}", GREEN if benchmark_return >= 0 else RED))
    screen.query_one("#stat-excess", Static).update(
        tile("EXCESS", f"{excess:+.2%}", GREEN if excess >= 0 else RED))
    screen.query_one("#stat-sharpe", Static).update(
        tile("SHARPE", f"{sharpe:.2f}", GREEN if sharpe > 1 else "yellow" if sharpe > 0 else RED))
    screen.query_one("#stat-dd", Static).update(tile("MAX DRAWDOWN", f"{max_dd:.2%}", RED))


def _session_headline(name: str, record: SessionRecord) -> Text:
    """The report header for one session: what happened at this close."""
    facts = [f"session {record.session}"]
    if record.executed is not None:
        x = record.executed
        refreshed = x.refreshed_assessment.as_of if x.refreshed_assessment else x.as_of
        facts.append(f"executed the {x.as_of} decision (refreshed {refreshed})")
    if record.decision is not None:
        n_signals = sum(len(sr.signals) for sr in record.decision.strategies)
        facts.append(f"decided · {n_signals} signals · executes next session")
    if record.executed is None and record.decision is None:
        facts.append("valuation only")
    return Text.assemble((name, f"bold {BRIGHT}"), ("  ·  " + "  ·  ".join(facts), MUTED))


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
        self.query_one("#report-head", Static).update(_session_headline(self._name, self._record))
        self.query_one("#report-foot", Static).update(_book_summary(self._record))
        nav = self.query_one("#report-nav", OptionList)
        nav.add_options(_session_nav(self._record))
        nav.highlighted = _first_selectable(nav)
        nav.focus()

    def action_back(self) -> None:
        self.app.pop_screen()

    @on(OptionList.OptionHighlighted, "#report-nav")
    def _browse(self, event: OptionList.OptionHighlighted) -> None:
        oid = (event.option.id or "") if event.option else ""
        detail = _session_detail(self._record, oid)
        if detail is not None:
            self.query_one("#detail-pane", Static).update(detail)
            self.query_one("#report-detail", VerticalScroll).scroll_home(animate=False)


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
        self._desks: list[_Desk] = []
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
        detail = _session_detail(self._record, oid)
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
                data = CachedDataClient(raw)
                if self._redo:
                    if state.last_session is None:
                        raise NothingDue("no session recorded yet, nothing to run again")
                    # The board is told about the state going into the session,
                    # which is what `redo` will advance from.
                    due = state.last_session
                    state = ledger.replay(spec.capital, before=due)
                else:
                    due = next_session(data, spec.benchmark, state.last_session)
                    if due is None:  # the close slipped out from under the approval step
                        raise NothingDue(f"no completed {spec.benchmark} session after {state.last_session}")
                # The dates the analysts will be asked about: the refresh before
                # executing a pending decision, and the new decision itself.
                dates: list[str] = []
                if state.pending is not None and previous_day(due) != state.pending.as_of:
                    dates.append(previous_day(due))
                if is_rebalance_session(due, state.last_session, spec.rebalance):
                    dates.append(due)
                app.call_from_thread(self._begin_board, deployed, due, dates, state.pending)
                if dates:
                    self._warm(spec, deployed.universe, dates)
                record = redo(directory, data) if self._redo else tick(directory, data)
            app.call_from_thread(self._show_report, deployed, record)
        except Exception as exc:  # fail loud, in the UI
            app.call_from_thread(self._fail, exc)

    def _warm(self, spec: FundSpec, universe: list[str], dates: list[str]) -> None:
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
            (due, f"bold {RED}"),
            ("  ·  " + " · ".join(doing), MUTED),
        ))
        if not dates:
            return
        self._desks = [_Desk(DISPLAY_NAMES.get(n, n)) for n in _agent_names(deployed.spec)]
        self._paint_board()
        # The worker threads mutate their own desk; this redraws all of them on
        # one clock, so token rate never sets frame rate.
        self._painter = self.set_interval(_BOARD_REFRESH, self._paint_board)

    def _paint_board(self) -> None:
        self.query_one("#run-roster", Static).update(_desk_table(self._desks))

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
        self.query_one("#report-head", Static).update(_session_headline(deployed.name, record))
        self.query_one("#report-foot", Static).update(Group(
            _book_summary(record),
            Text.assemble(("✓ ", f"bold {GREEN}"), ("Recorded ", MUTED),
                          (str(Ledger(self._directory).path(record.session)), MUTED)),
        ))
        self.refresh_bindings()  # phase changed: esc is offered again
        nav = self.query_one("#report-nav", OptionList)
        nav.clear_options()
        nav.add_options(_session_nav(record))
        self.query_one("#run-panes", ContentSwitcher).current = "run-report"
        nav.highlighted = _first_selectable(nav)
        nav.focus()

    def _fail(self, exc: Exception) -> None:
        self._stop_painting()
        self._phase = "failed"
        phase = self.query_one("#run-phase", Static)
        if isinstance(exc, NothingDue):
            phase.update(Text.assemble(
                ("Nothing due  ", f"bold {BRIGHT}"), (f"{exc}", MUTED),
                ("\n\nThe fund is up to date. Run it again after the next close. esc to go back.", MUTED)))
        else:
            phase.update(Text.assemble(
                ("✗ ", f"bold {RED}"), (f"{type(exc).__name__}: {exc}", RED),
                ("\n\nesc to go back", MUTED)))
            self.notify(str(exc), title="Run failed", severity="error")
        self.refresh_bindings()


class BuilderScreen(Screen):
    """The fund wizard: a step rail on the left, the active step on the right.
    Esc rewinds one step. The output is a FundSpec YAML — the same definition
    the engine reads — and, in paper mode, a deployed fund ready to run.

    Backtest mode asks four things (name, strategies, capital, cadence) and
    offers to backtest the result; what it trades is chosen per run. Paper
    mode adds the tickers as a fifth step, because a paper fund trades the
    same universe every session, and ends with "Run its first session".
    """

    CADENCES = ["daily", "weekly", "monthly"]

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
            "step-tickers": "#tickers-input",
            "step-done": "#done-menu",
        }[pane_id]
        self.query_one(focus).focus()
        if pane_id == "step-cadence":
            picked = self._state.get("rebalance", "weekly")
            self.query_one("#cadence-list", OptionList).highlighted = (
                self.CADENCES.index(picked)
            )
        if pane_id == "step-tickers":
            tickers = self.query_one("#tickers-input", Input)
            if not tickers.value:
                last = _newest_paper_universe()
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
        if _fund_name_taken(name) and self._state.get("replace") != name:
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
                self._library[i] for i in picked if i != _CUSTOM
            ]
            self._state["custom_selected"] = _CUSTOM in picked
            self._state["strategies"] = list(self._state["library_strategies"])
            if _CUSTOM in picked:
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
        if self.mode == "paper":
            self._goto("step-tickers")
        else:
            self._finish_build()

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
        spec = FundSpec(
            schema_version=2,
            name=self._state["name"],
            strategies=[s.model_dump() for s in self._state["strategies"]],
            risk=DEFAULT_RISK,
            capital=self._state["capital"],
            rebalance=self._state["rebalance"],
        )
        # The user said yes to replacing the fund that held this name: clear
        # it now, at the last moment, so an abandoned wizard costs nothing.
        replaced = self._state.get("replace") == spec.name
        if replaced:
            _wipe_fund(spec.name)
        # Otherwise both modes refuse to overwrite: the name was checked on
        # the way in, but something may have taken it since. Paper mode needs
        # both the saved definition and the fund directory to be free.
        if self.mode == "paper" and (PAPER_DIR / spec.name).exists():
            self.notify("A paper fund with that name already exists. Choose a different name.",
                        severity="error")
            self._goto("step-name")
            return
        MANDATES_DIR.mkdir(parents=True, exist_ok=True)
        path = MANDATES_DIR / f"{spec.name}.yaml"
        try:
            with path.open("x") as output:
                output.write(yaml.safe_dump(spec.model_dump(), sort_keys=False))
        except FileExistsError:
            self.notify("A fund with that name already exists. Choose a different name.",
                        severity="error")
            self._goto("step-name")
            return
        self._built = (spec, path)

        staff = ", ".join(s.title for s in self._state["strategies"])
        identity = Text.assemble(
            (spec.name, f"bold {BRIGHT}"),
            (f"  ·  {staff}  ·  ${spec.capital:,.0f}  ·  {spec.rebalance}", MUTED),
        )
        if replaced:
            self.notify(f"Replaced the previous {spec.name}.", severity="warning")
        if self.mode == "paper":
            universe = self._state["universe"]
            directory = deploy(spec.name, spec, universe, root=PAPER_DIR)
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
                Text("Its first session marks the book at the latest completed close and "
                     "makes the first decision; the session after executes it.", style=MUTED),
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
            3: self._state.get("rebalance"),
            4: (_short_tickers(self._state["universe"], 3)
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

    @staticmethod
    def _strategy_prompt(strategy: StrategySpec) -> Text:
        staff = ", ".join(
            _SHORT_NAMES.get(m.name, m.name) for m in strategy.models
        )
        return Text.assemble((f"{strategy.title:<20}", "bold"), (f"{MODE_LABELS[strategy.blend.mode]} · {staff}", MUTED))

    @staticmethod
    def _agent_prompt(key: str, cls: type) -> Text:
        name = DISPLAY_NAMES.get(key, key)
        tag = "" if issubclass(cls, LLMAgent) else "  quant"
        return Text.assemble((f"{name:<24}", "bold"), (MODE_LABELS[get_investment_approach(key)] + tag, MUTED))


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
        entries = _saved_funds()
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
                fund_list.add_option(Option(Text(_fund_label(entry.spec))))
        fund_list.highlighted = _first_selectable(fund_list)
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
        assert self._spec is not None
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

            # Same artifact, same place as `aihf backtest`: research/ is where
            # backtests live, and the mandate picker's history reads it.
            RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            path = RESEARCH_DIR / f"{spec.name}-{result.start}-{result.end}-{stamp}.json"
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
        model-specific data (e.g. PEAD's earnings history).

        LLM agents run blind, as they do in the backtest itself: a warm with
        a different prompt would fill the cache with entries the backtest
        never looks up."""
        app = self.app
        display = {n: DISPLAY_NAMES.get(n, n) for n in _agent_names(spec)}

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
        self.query_one("#stats", Horizontal).remove_class("hidden")
        box_widget.remove_class("hidden")
        tape_box.remove_class("hidden")

    def _board_tick(self, record: CycleRecord) -> None:
        for fill in record.fills:
            self._tape.append((record.execution_as_of or record.as_of, fill,
                               record.positions.get(fill.ticker, 0)))
        self.query_one("#tape", Static).update(_tape_table(self._tape))

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
        curve_widget.update(Group(*_render_area_chart(
            self._nav, benchmark_curve, capital, min(width, 100))))
        self.query_one("#cycle-line", Static).update(Text(
            f"session {len(self._nav)}/{self._n_cycles} · {value.as_of}", style=MUTED))

    def _update_stats(self, nav: float, fund_return: float,
                      benchmark_return: float, excess: float,
                      sharpe: float, max_dd: float) -> None:
        """One row of running tallies, live during the replay and refreshed
        with the engine's authoritative numbers at the end."""
        assert self._spec is not None
        _update_stat_tiles(self, self._spec.benchmark, nav, fund_return,
                           benchmark_return, excess, sharpe, max_dd)

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
    """The v2 terminal app. One screen stack: Home → Backtest / Paper / Builder."""

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
