"""Run the AI hedge fund.

Usage::

    poetry run python -m v2.run
        No arguments: the interactive experience. Build a fund — pick stocks,
        pick strategies, set capital — and watch it run its first cycle; or
        backtest a saved fund and watch its equity curve draw against its
        benchmark.

    poetry run python -m v2.run v2/funds/example.yaml --date 2025-06-03
        With a mandate: run one cycle non-interactively. The full CycleRecord
        prints to stdout as JSON (pipe it anywhere); a short human summary
        goes to stderr. Add --out record.json to also write it to a file.

Either way the same engine runs underneath. The interactive builder is a
thin client: it only *composes a FundSpec* — the same machine-facing YAML a
chat LLM or the strategy generator will emit. Humans click, machines write,
the engine reads one thing.
"""

from __future__ import annotations

import argparse
import sys
import termios
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as _date
from datetime import datetime
from datetime import timedelta
from pathlib import Path

import warnings

# langchain's deprecated-global warning fires when the LLM client loads lazily
# inside the roster's worker threads — it would splatter across the live UI.
warnings.filterwarnings(
    "ignore", message="Importing verbose from langchain root module"
)

import questionary
import yaml
from dotenv import load_dotenv
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from v2.backtesting import FundBacktestResult, backtest_fund, rebalance_grid
from v2.brokers import SimBroker
from v2.data import CachedDataClient, FDClient
from v2.fund import Fund, FundSpec, StrategySpec, load_spec, load_strategy
from v2.pipeline import CycleRecord, run_cycle
from v2.pipeline.run_cycle import _MARK_LOOKBACK_DAYS
from v2.signals import ALPHA_MODEL_REGISTRY, LLMAgent

STRATEGY_DIR = Path(__file__).parent / "strategies"
FUNDS_DIR = Path(__file__).parent / "funds"

UNIVERSE_PRESETS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
                    "META", "TSLA", "JPM", "UNH", "XOM"]

DISPLAY_NAMES = {
    "buffett": "Warren Buffett",
    "munger": "Charlie Munger",
    "graham": "Benjamin Graham",
    "lynch": "Peter Lynch",
    "druckenmiller": "Stanley Druckenmiller",
    "pead": "post-earnings drift",
}

VERSION = "2.0.0"  # keep in sync with pyproject.toml

DEFAULT_RISK = {"max_position_pct": 0.25, "max_gross_exposure": 1.0}
DEFAULT_CAPITAL = 100_000.0
_BACKTEST_WEEKS = 78  # ~18 months of history for the one-command backtest
_REVEAL_DELAY = 0.7   # seconds between theses in the first-cycle reveal
_ROSTER_DWELL = 0.5  # min seconds a roster row lingers on a ticker (readable on warm cache)
_CYCLE_DWELL = 0.08  # min seconds per backtest tick, so the curve draws visibly

# Sentinel returned by a prompt when the user presses Esc to step back.
_BACK = object()

# The v1 selection look: green marks what you chose, nothing else shouts.
_CHECKBOX_STYLE = questionary.Style([
    ("checkbox-selected", "fg:green"),
    ("selected", "fg:green noinherit"),
    ("highlighted", "noinherit"),
    ("pointer", "noinherit"),
])
_CHECKBOX_INSTRUCTION = (
    "\n\nInstructions:\n"
    "1. Press Space to select/unselect.\n"
    "2. Press 'a' to select/unselect all.\n"
    "3. Press Enter when done.\n"
)

# Sentinel for "build your own" in the strategy checklist — lets someone pick
# exactly the agents they want (or just PEAD alone) instead of a library bundle.
_CUSTOM = object()
_CUSTOM_LABEL = "Build your own — pick individual agents"


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="python -m v2.run",
        description="Run the AI hedge fund. No arguments: build a fund "
        "interactively. With a mandate YAML: run one cycle and print the record.",
    )
    parser.add_argument("mandate", nargs="?",
                        help="path to a fund spec YAML, e.g. v2/funds/example.yaml "
                        "(omit for the interactive builder)")
    parser.add_argument(
        "--date",
        default=_date.today().isoformat(),
        help="as-of date YYYY-MM-DD (default: today); models only see data "
        "filed by this date",
    )
    parser.add_argument(
        "--backtest", action="store_true",
        help="backtest the mandate instead of running one cycle: one run_cycle "
        "per rebalance date from --start to --date, full result JSON on stdout",
    )
    parser.add_argument(
        "--start",
        help=f"backtest start date YYYY-MM-DD (default: {_BACKTEST_WEEKS} weeks "
        "before --date)",
    )
    parser.add_argument("--out", help="also write the record JSON to this file")
    args = parser.parse_args()

    if args.mandate is None:
        _interactive()
        return

    console = Console(stderr=True)  # status + summary on stderr; stdout stays pure JSON
    spec = load_spec(args.mandate)
    fund = Fund(spec)

    if args.backtest:
        start = args.start or (
            _date.fromisoformat(args.date) - timedelta(weeks=_BACKTEST_WEEKS)
        ).isoformat()
        with FDClient() as raw:
            fd = CachedDataClient(raw)
            with console.status(
                f"[cyan]{spec.name}: backtesting {start} → {args.date} "
                f"({spec.rebalance} rebalance vs {spec.benchmark})…",
                spinner="dots",
            ):
                result = backtest_fund(fund, start, args.date, fd)
        print(result.model_dump_json(indent=2))
        if args.out:
            Path(args.out).write_text(result.model_dump_json(indent=2))
        m = result.metrics
        console.print(
            f"[bold]{spec.name}[/] {result.start} → {result.end}  ·  "
            f"{m.n_cycles} cycles  ·  return {m.total_return_pct:+.1%} "
            f"vs {spec.benchmark} {m.benchmark_return_pct:+.1%}  ·  "
            f"sharpe {m.sharpe_ratio:.2f}  ·  max drawdown {m.max_drawdown_pct:.1%}"
        )
        return

    broker = SimBroker(cash=spec.capital)

    with FDClient() as raw:
        fd = CachedDataClient(raw)
        n_models = sum(len(staff) for _, staff in fund.strategies)
        with console.status(
            f"[cyan]{spec.name}: running one cycle as of {args.date} — "
            f"{len(spec.universe)} tickers x {n_models} models "
            f"across {len(fund.strategies)} strategies…",
            spinner="dots",
        ):
            record = run_cycle(fund, args.date, broker, fd)

    print(record.model_dump_json(indent=2))
    if args.out:
        Path(args.out).write_text(record.model_dump_json(indent=2))

    for sr in record.strategies:
        abstained = sum(1 for s in sr.signals if s.metadata.get("abstained") is True)
        console.print(
            f"[dim]  {sr.name} ({sr.slice:.0%} of capital): "
            f"{len(sr.signals)} signals ({abstained} abstained)[/]"
        )
    n_signals = sum(len(sr.signals) for sr in record.strategies)
    console.print(
        f"[bold]{spec.name}[/] @ {record.as_of}  ·  "
        f"{len(record.strategies)} strategies  ·  {n_signals} signals  ·  "
        f"{len(record.clamps)} risk clamps  ·  "
        f"{len(record.orders)} orders  ·  NAV ${record.nav:,.2f}"
    )
    if record.skipped:
        console.print(f"[dim]skipped: {', '.join(s.ticker for s in record.skipped)}[/]")


# ---------------------------------------------------------------------------
# The interactive experience (no arguments)
# ---------------------------------------------------------------------------

def _interactive() -> None:
    console = Console()
    console.print(Panel(
        f"[bold white]AI HEDGE FUND[/] · {VERSION}",
        border_style="cyan",
    ))

    # Two verbs, one fund: production and the research lab, side by side
    # (VISION.md). Esc at the menu leaves; Esc inside a flow returns here.
    while True:
        action = _ask(questionary.select(
            "What do you want to do?",
            choices=["Build a fund", "Backtest a fund"],
        ))
        if action is None or action is _BACK:
            return
        if action == "Build a fund":
            _build_fund(console)
            return
        if _backtest_saved_fund(console) is not _BACK:
            return


def _build_fund(console: Console) -> None:
    library = sorted(
        (load_strategy(p) for p in STRATEGY_DIR.glob("*.yaml")),
        key=lambda s: (_strategy_kind(s) == "systematic", s.name),
    )

    # The builder is a small state machine: each step reads/writes `state` and
    # returns _BACK when the user presses Esc, so we can rewind one step.
    state: dict = {}
    steps = [_step_name, _step_tickers, _step_strategies(library), _step_capital,
             _step_cadence]
    i = 0
    while i < len(steps):
        result = steps[i](console, state)
        if result is _BACK:
            i = max(0, i - 1)
            continue
        i += 1

    # Equal capital slices; power users edit the YAML (or soon: tell the LLM).
    spec = FundSpec(
        name=state["name"],
        universe=state["universe"],
        strategies=[s.model_dump() for s in state["strategies"]],
        risk=DEFAULT_RISK,
        capital=state["capital"],
        rebalance=state["rebalance"],
    )

    FUNDS_DIR.mkdir(exist_ok=True)
    path = FUNDS_DIR / f"{spec.name}.yaml"
    path.write_text(yaml.safe_dump(spec.model_dump(), sort_keys=False))

    console.print()
    console.print(f"  [green]✓[/] Saved fund to [bold]{path}[/]\n")

    run = _ask(questionary.confirm("Run your fund's first cycle now?", default=True))
    if run is _BACK or run is None:
        run = False
    if not run:
        console.print(f"\n  Later: [bold]poetry run python -m v2.run {path}[/]")
        return

    record = _run_with_roster(console, spec, _date.today().isoformat())
    _print_cycle(console, record)


def _backtest_saved_fund(console: Console):
    """The research lab's front door: pick a saved fund, choose the tickers to
    run (pre-filled from its universe, editable per run), pick a window, and
    backtest it. Same step machine as the builder — Esc rewinds one step, and
    Esc at the picker returns _BACK (back to the menu).
    """
    paths = sorted(FUNDS_DIR.glob("*.yaml"))
    if not paths:
        console.print(
            f"\n  No funds in [bold]{FUNDS_DIR}[/] yet — build one first.\n"
        )
        return _BACK
    specs = [load_spec(p) for p in paths]

    state: dict = {}
    steps = [_step_pick_fund(specs), _step_tickers,
             _step_backtest_start, _step_backtest_end]
    i = 0
    while i < len(steps):
        result = steps[i](console, state)
        if result is _BACK:
            if i == 0:
                return _BACK
            i -= 1
            continue
        i += 1

    # Backtest the picked fund with the tickers chosen for this run; the saved
    # YAML is untouched (model_copy is a shallow, unvalidated override and the
    # ticker step already upper-cased and de-duped the universe).
    spec = state["fund"].model_copy(update={"universe": state["universe"]})
    _run_backtest(console, spec, state["start"], state["end"])


def _step_pick_fund(specs):
    """Returns a step closure bound to the loaded fund specs."""
    def step(console: Console, state: dict):
        choice = _ask(questionary.select(
            "Which fund?",
            choices=[questionary.Choice(_fund_label(s), value=s) for s in specs],
        ))
        if choice is None:
            sys.exit(1)  # ctrl-c
        if choice is _BACK:
            return _BACK
        state["fund"] = choice
        # Seed the ticker step with the saved universe; the user can trim or
        # extend it for this run without editing the fund's YAML.
        state["universe"] = list(choice.universe)
    return step


def _step_backtest_start(console: Console, state: dict):
    default = state.get(
        "start", (_date.today() - timedelta(weeks=_BACKTEST_WEEKS)).isoformat()
    )
    raw = _ask(questionary.text(
        "Backtest from (YYYY-MM-DD):", default=default, validate=_valid_date,
    ))
    if raw is None:
        sys.exit(1)
    if raw is _BACK:
        return _BACK
    state["start"] = raw.strip()


def _step_backtest_end(console: Console, state: dict):
    def validate(text: str):
        ok = _valid_date(text)
        if ok is not True:
            return ok
        if text.strip() <= state["start"]:
            return f"Must be after {state['start']}."
        return True

    raw = _ask(questionary.text(
        "Backtest to (YYYY-MM-DD):",
        default=state.get("end", _date.today().isoformat()),
        validate=validate,
    ))
    if raw is None:
        sys.exit(1)
    if raw is _BACK:
        return _BACK
    state["end"] = raw.strip()
    console.print(f"\nWindow: [green]{state['start']} → {state['end']}[/]\n")


def _valid_date(text: str):
    try:
        _date.fromisoformat(text.strip())
        return True
    except ValueError:
        return "Use YYYY-MM-DD."


def _fund_label(spec: FundSpec) -> str:
    """One aligned line per fund: name, universe, cadence."""
    universe = ", ".join(spec.universe[:4])
    if len(spec.universe) > 4:
        universe += ", …"
    return f"{spec.name:<18} {universe} · {spec.rebalance}"


# ---------------------------------------------------------------------------
# Builder steps (each returns _BACK when the user presses Esc)
# ---------------------------------------------------------------------------

def _ask(question):
    """Run a questionary prompt with Esc bound to 'step back'.

    Esc exits the prompt returning the _BACK sentinel; Ctrl-C returns None
    (questionary's own behavior). The app's bindings are merged (not mutated —
    prompt_toolkit merges them into a read-only registry).

    The binding is EAGER so Esc responds instantly: Escape is a prefix of
    default multi-key bindings (Alt+Enter etc.), and a non-eager handler
    waits ~1s to disambiguate — long enough that users hammer the key.
    Arrow keys are unaffected: their escape sequences resolve to key objects
    in the input parser, before bindings ever see an Escape.

    On stepping back, any queued input is flushed so extra Esc presses
    can't cascade through the prompts that follow.
    """
    bindings = KeyBindings()

    @bindings.add("escape", eager=True)
    def _(event):
        event.app.exit(result=_BACK)

    app = question.application
    app.key_bindings = merge_key_bindings([app.key_bindings, bindings])
    result = question.ask()

    if result is _BACK:
        try:
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except (termios.error, OSError, ValueError):
            pass  # not a tty (tests, pipes) — nothing buffered to flush
    return result


def _ask_checkbox(question):
    """_ask for checkboxes: anything but a list means 'step back'.

    A checkbox can only legitimately return a list. Esc returns the _BACK
    sentinel; an Esc chased quickly by Enter parses as Alt+Enter and hits a
    default accept-input binding, leaking the empty buffer string — fold
    that artifact into 'back' rather than crashing on it.
    """
    result = _ask(question)
    if result is None:
        sys.exit(1)  # ctrl-c
    if not isinstance(result, list):
        return _BACK
    return result


def _step_name(console: Console, state: dict):
    name = _ask(questionary.text("Fund name:", default=state.get("name", "ai-hedge-fund")))
    if name is None:
        sys.exit(1)  # ctrl-c
    if name is _BACK:
        return _BACK
    state["name"] = name.strip().replace(" ", "-").lower() or "ai-hedge-fund"


def _step_tickers(console: Console, state: dict):
    default = ", ".join(state["universe"]) if state.get("universe") else ""
    raw = _ask(questionary.text(
        f"Enter your stocks (comma or space separated, e.g. {', '.join(UNIVERSE_PRESETS[:3])}):",
        default=default,
        validate=lambda text: bool(text.strip()) or "Enter at least one ticker.",
    ))
    if raw is None:
        sys.exit(1)
    if raw is _BACK:
        return _BACK
    universe: list[str] = []
    for ticker in raw.replace(",", " ").upper().split():
        if ticker not in universe:
            universe.append(ticker)
    state["universe"] = universe
    console.print(f"\nYour stocks: [green]{', '.join(universe)}[/]\n")


def _step_strategies(library):
    """Returns a step closure bound to the sorted strategy library."""
    def step(console: Console, state: dict):
        picked = _ask_checkbox(questionary.checkbox(
            "Select your strategies.",
            choices=[
                questionary.Choice(_CUSTOM_LABEL, value=_CUSTOM),
                *(questionary.Choice(_strategy_label(s), value=s) for s in library),
            ],
            instruction=_CHECKBOX_INSTRUCTION,
            validate=lambda ps: bool(ps) or "You must select at least one strategy.",
            style=_CHECKBOX_STYLE,
        ))
        if picked is _BACK:
            return _BACK

        strategies = [s for s in picked if s is not _CUSTOM]
        if _CUSTOM in picked:
            custom = _build_custom_strategy(console)
            if custom is _BACK:
                return step(console, state)  # re-ask strategies
            strategies.append(custom)
        state["strategies"] = strategies
        console.print(f"\nYour strategies: [green]{', '.join(s.name for s in strategies)}[/]\n")
    return step


def _step_capital(console: Console, state: dict):
    raw = _ask(questionary.text(
        "Starting capital ($):",
        default=f"{state.get('capital', DEFAULT_CAPITAL):.0f}",
    ))
    if raw is None:
        sys.exit(1)
    if raw is _BACK:
        return _BACK
    state["capital"] = float(raw or DEFAULT_CAPITAL)
    console.print(f"\nCapital: [green]${state['capital']:,.0f}[/]\n")


def _step_cadence(console: Console, state: dict):
    cadence = _ask(questionary.select(
        "Rebalance cadence:",
        choices=["daily", "weekly", "monthly"],
        default=state.get("rebalance", "weekly"),
    ))
    if cadence is None:
        sys.exit(1)
    if cadence is _BACK:
        return _BACK
    state["rebalance"] = cadence
    console.print(f"\nRebalance: [green]{cadence}[/]\n")


# ---------------------------------------------------------------------------
# The running UI — v1's parallel roster
# ---------------------------------------------------------------------------

def _run_with_roster(console: Console, spec: FundSpec, as_of: str) -> CycleRecord:
    """Show the v1 running UI — every agent working its tickers in parallel —
    then replay the cycle off the now-warm cache for the record.

    The roster's threads WARM the disk caches (prompts + data). The real
    `run_cycle` afterward reads those caches: instant, sequential, and the
    single source of truth (fail-loud errors surface there, not here).
    """
    agent_names = _agent_names(spec)
    display = {n: DISPLAY_NAMES.get(n, n) for n in agent_names}

    roster = _Roster(console, [display[n] for n in agent_names])

    def warm(agent_name: str) -> None:
        who = display[agent_name]
        model = ALPHA_MODEL_REGISTRY[agent_name]()  # own instance per thread
        with FDClient() as raw:  # own client per thread (requests isn't shared-safe)
            fd = CachedDataClient(raw)
            for ticker in spec.universe:
                roster.working(who, ticker)
                started = time.time()
                try:
                    model.predict(ticker, as_of, fd)
                except Exception:
                    pass  # best-effort warm; run_cycle is the source of truth
                dwell = _ROSTER_DWELL - (time.time() - started)
                if dwell > 0:
                    time.sleep(dwell)
        roster.done(who)

    with roster:
        with ThreadPoolExecutor(max_workers=min(8, len(agent_names))) as pool:
            for future in as_completed([pool.submit(warm, n) for n in agent_names]):
                future.result()

    fund = Fund(spec)
    broker = SimBroker(cash=spec.capital)
    with FDClient() as raw:
        return run_cycle(fund, as_of, broker, CachedDataClient(raw))


class _Roster:
    """v1-style live progress: one row per agent, all working in parallel.

    UI-only. Rows show `⋯ Name  [TICKER] Analyzing` in yellow while an agent
    works its tickers, then flip to `✓ Name  Done` in green — the exact shape
    of v1's agent roster. The verdicts come afterward, in the reveal.
    """

    def __init__(self, console: Console, names: list[str]) -> None:
        self._order = names
        self._state: dict[str, tuple[str, str | None]] = {n: ("pending", None) for n in names}
        self._lock = threading.Lock()
        self._live = Live(console=console, refresh_per_second=12)

    def __enter__(self) -> _Roster:
        self._live.start()
        self._live.update(self._render())
        return self

    def __exit__(self, *exc) -> None:
        self._live.update(self._render())
        self._live.stop()

    def working(self, name: str, ticker: str) -> None:
        with self._lock:
            self._state[name] = ("working", ticker)
            self._live.update(self._render())

    def done(self, name: str) -> None:
        with self._lock:
            self._state[name] = ("done", None)
            self._live.update(self._render())

    def _render(self) -> Table:
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column()
        for name in self._order:
            status, ticker = self._state[name]
            row = Text()
            if status == "done":
                row.append("✓ ", style="green bold")
                row.append(f"{name:<24}", style="bold")
                row.append("Done", style="green")
            elif status == "working":
                row.append("⋯ ", style="yellow")
                row.append(f"{name:<24}", style="bold")
                # In the backtest warm phase the label is "TICKER · date";
                # tint the date red so the point-in-time cursor stands out.
                symbol, _, as_of = ticker.partition(" · ")
                row.append("[", style="cyan")
                row.append(symbol, style="cyan")
                if as_of:
                    row.append(" · ", style="cyan")
                    row.append(as_of, style="red")
                row.append("] ", style="cyan")
                row.append("Analyzing", style="yellow")
            else:
                row.append("⋯ ", style="dim")
                row.append(f"{name:<24}", style="dim")
                row.append("queued", style="dim")
            table.add_row(row)
        return table


# ---------------------------------------------------------------------------
# The backtest — time-travel the fund through history
# ---------------------------------------------------------------------------

def _run_backtest(console: Console, spec: FundSpec, start: str, end: str) -> None:
    """Warm the caches across history (visible work), then replay the fund
    tick by tick off the warm cache while the equity curve draws itself.

    Warm-then-replay, same contract as _run_with_roster: threads only warm
    disk caches; the sequential backtest_fund afterward is the source of
    truth (determinism and fail-loud live in the engine, not the UI).
    """
    with FDClient() as raw:
        bars = CachedDataClient(raw).get_prices(spec.benchmark, start, end)
    closes = {b.time[:10]: b.close for b in bars if start <= b.time[:10] <= end}
    if not closes:
        raise ValueError(
            f"no {spec.benchmark} bars in [{start}, {end}] — "
            "cannot build the trading grid"
        )
    grid = rebalance_grid(sorted(closes), spec.rebalance)

    console.print(
        f"\n[bold white]BACKTEST:[/] {start} → {end}"
        f"  [dim]{len(grid)} {spec.rebalance} cycles · vs {spec.benchmark}[/]\n"
    )

    _warm_market_data(console, spec, grid)
    _warm_agents(console, spec, grid)

    fund = Fund(spec)
    board = _BacktestBoard(console, spec, closes, len(grid))
    with FDClient() as raw:
        with board:
            result = backtest_fund(fund, start, end, CachedDataClient(raw),
                                   on_cycle=board.tick)

    _print_backtest(console, result)

    FUNDS_DIR.mkdir(exist_ok=True)
    # Stamp each run so reruns of the same fund don't clobber older receipts.
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    path = FUNDS_DIR / f"{spec.name}-backtest-{stamp}.json"
    path.write_text(result.model_dump_json(indent=2))
    console.print(f"  [green]✓[/] Saved backtest record to [bold]{path}[/]\n")


_WARM_CHUNK = 10  # dates per warm task — small enough that one stock still fans out


def _warm_market_data(console: Console, spec: FundSpec, grid: list[str]) -> None:
    """Prefetch exactly the requests the engine will make (the disk cache
    keys on exact request params, so warming must mirror them per date).
    Doing this first also keeps the agent threads from racing duplicate
    fetches of the shared snapshot data.

    Work is split into (ticker, chunk-of-dates) tasks rather than one task
    per ticker: parallelism comes from the window, so a one-stock fund
    still saturates the pool instead of fetching 78 weeks on one thread.
    """
    has_agents = any(
        issubclass(ALPHA_MODEL_REGISTRY[m.name], LLMAgent)
        for s in spec.strategies for m in s.models
    )
    chunks = [
        (ticker, grid[j:j + _WARM_CHUNK])
        for ticker in spec.universe
        for j in range(0, len(grid), _WARM_CHUNK)
    ]

    progress = Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=40, complete_style="cyan"),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    )
    task = progress.add_task(
        f"Loading market data · {len(spec.universe)} stocks × {len(grid)} "
        f"{spec.rebalance} cycles",
        total=len(spec.universe) * len(grid),
    )

    def prefetch(ticker: str, dates: list[str]) -> None:
        with FDClient() as raw:  # own client per task (requests isn't shared-safe)
            fd = CachedDataClient(raw)
            if has_agents:
                fd.get_company_facts(ticker)  # disk-cached after the first task
            for as_of in dates:
                lookback = (
                    _date.fromisoformat(as_of) - timedelta(days=_MARK_LOOKBACK_DAYS)
                ).isoformat()
                fd.get_prices(ticker, lookback, as_of)  # run_cycle's marks
                if has_agents:
                    # build_snapshot's exact request (periods default = 20)
                    fd.get_financial_metrics(ticker, as_of, period="ttm", limit=20)
                progress.advance(task)  # rich Progress is thread-safe

    with progress:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(prefetch, t, ds) for t, ds in chunks]
            for future in as_completed(futures):
                future.result()  # fail loud — bad data here poisons every cycle


def _warm_agents(console: Console, spec: FundSpec, grid: list[str]) -> None:
    """The roster, across history: every agent replays the whole window,
    warming prompt caches (and model-specific data, e.g. PEAD's earnings).
    No dwell — an unchanged snapshot is an instant cache hit, and the LLM
    calls on new filings pace the roster naturally."""
    agent_names = _agent_names(spec)
    display = {n: DISPLAY_NAMES.get(n, n) for n in agent_names}
    roster = _Roster(console, [display[n] for n in agent_names])

    def warm(agent_name: str) -> None:
        who = display[agent_name]
        model = ALPHA_MODEL_REGISTRY[agent_name]()  # own instance per thread
        with FDClient() as raw:
            fd = CachedDataClient(raw)
            for as_of in grid:
                for ticker in spec.universe:
                    roster.working(who, f"{ticker} · {as_of}")
                    try:
                        model.predict(ticker, as_of, fd)
                    except Exception:
                        pass  # best-effort warm; backtest_fund is the source of truth
        roster.done(who)

    with roster:
        with ThreadPoolExecutor(max_workers=min(8, len(agent_names))) as pool:
            for future in as_completed([pool.submit(warm, n) for n in agent_names]):
                future.result()


def _agent_names(spec: FundSpec) -> list[str]:
    """Unique model names across strategies, in first-appearance order."""
    names: list[str] = []
    for strategy in spec.strategies:
        for m in strategy.models:
            if m.name not in names:
                names.append(m.name)
    return names


_CHART_HEIGHT = 8


class _BacktestBoard:
    """Live dashboard while the backtest replays: running stats over a
    unicode equity curve, green above starting capital and red below."""

    def __init__(self, console: Console, spec: FundSpec,
                 benchmark_closes: dict[str, float], n_cycles: int) -> None:
        self._spec = spec
        self._closes = benchmark_closes
        self._n = n_cycles
        self._dates: list[str] = []
        self._nav: list[float] = []
        self._width = max(20, min(console.width - 8, 90))
        self._live = Live(console=console, refresh_per_second=12)

    def __enter__(self) -> _BacktestBoard:
        self._live.start()
        return self

    def __exit__(self, *exc) -> None:
        self._live.stop()

    def tick(self, i: int, n: int, record: CycleRecord) -> None:
        started = time.time()
        self._dates.append(record.as_of)
        self._nav.append(record.nav)
        self._live.update(self._render())
        dwell = _CYCLE_DWELL - (time.time() - started)
        if dwell > 0:
            time.sleep(dwell)

    def _render(self) -> Group:
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

        def cell(label: str, value: str, style: str) -> Text:
            t = Text(justify="center")
            t.append(f"{label}\n", style="dim")
            t.append(value, style=f"bold {style}")
            return t

        stats = Table.grid(expand=True)
        for _ in range(4):
            stats.add_column(justify="center")
        stats.add_row(
            cell("PORTFOLIO", f"${nav:,.0f}", "white"),
            cell("RETURN", f"{fund_return:+.2%}",
                 "green" if fund_return >= 0 else "red"),
            cell(self._spec.benchmark, f"{benchmark_return:+.2%}",
                 "green" if benchmark_return >= 0 else "red"),
            cell("MAX DRAWDOWN", f"{max_dd:.2%}", "red"),
        )

        benchmark_curve = [capital] + [
            capital * self._closes[d] / self._closes[self._dates[0]]
            for d in self._dates
        ]
        fund_color = "green" if fund_return >= 0 else "red"
        footer = Text(
            f"cycle {len(self._nav)}/{self._n} · {self._dates[-1]}", style="dim"
        )
        return Group(
            Panel(stats, border_style="dim"),
            Panel(
                Group(*_render_chart(curve, benchmark_curve, capital, self._width)),
                border_style="dim", title="[dim]equity curve", title_align="left",
                subtitle=f"[bold {fund_color}]──[/] fund   "
                         f"[cyan]──[/] {self._spec.benchmark}",
                subtitle_align="right",
            ),
            footer,
        )


def _render_chart(
    fund: list[float],
    benchmark: list[float],
    baseline: float,
    width: int,
) -> list[Text]:
    """Two-series unicode line chart, tearsheet-style: the fund against its
    benchmark on one set of axes, dollar labels in a left gutter. Lines are
    box-drawing polylines (asciichart-style), not filled areas — the gap
    between the two lines is the point. The fund draws last, so where the
    lines collide the fund wins the cell.
    """
    lo = min(min(fund), min(benchmark))
    hi = max(max(fund), max(benchmark))
    span = (hi - lo) or 1.0

    labels = {
        _CHART_HEIGHT - 1: _money(hi),
        _CHART_HEIGHT // 2: _money(lo + span * (_CHART_HEIGHT // 2) / (_CHART_HEIGHT - 1)),
        0: _money(lo),
    }
    gutter = max(len(label) for label in labels.values())
    plot_width = max(20, width - gutter - 1)

    def resample(values: list[float]) -> list[float]:
        if len(values) == 1:
            return values * plot_width
        step = (len(values) - 1) / (plot_width - 1)
        return [values[round(i * step)] for i in range(plot_width)]

    # grid[row][col] = (char, style); row 0 is the top
    grid = [[(" ", "") for _ in range(plot_width)] for _ in range(_CHART_HEIGHT)]

    def draw(values: list[float], style_of) -> None:
        cols = resample(values)
        level = [round((v - lo) / span * (_CHART_HEIGHT - 1)) for v in cols]
        for x in range(plot_width - 1):
            y0, y1 = level[x], level[x + 1]
            if y0 == y1:
                grid[_CHART_HEIGHT - 1 - y0][x] = ("─", style_of(cols[x]))
            else:
                # Rising: turn up (╯) at the low level, arrive (╭) at the high.
                # Falling: turn down (╮) at the high, arrive (╰) at the low.
                grid[_CHART_HEIGHT - 1 - y0][x] = (
                    "╯" if y1 > y0 else "╮", style_of(cols[x]))
                grid[_CHART_HEIGHT - 1 - y1][x] = (
                    "╭" if y1 > y0 else "╰", style_of(cols[x]))
                for y in range(min(y0, y1) + 1, max(y0, y1)):
                    grid[_CHART_HEIGHT - 1 - y][x] = ("│", style_of(cols[x]))
        grid[_CHART_HEIGHT - 1 - level[-1]][-1] = ("─", style_of(cols[-1]))

    draw(benchmark, lambda v: "cyan")
    draw(fund, lambda v: "bold green" if v >= baseline else "bold red")

    rows: list[Text] = []
    for row in range(_CHART_HEIGHT):
        level = _CHART_HEIGHT - 1 - row
        line = Text()
        if level in labels:
            line.append(f"{labels[level]:>{gutter}}┤", style="dim")
        else:
            line.append(f"{'':>{gutter}}│", style="dim")
        for char, style in grid[row]:
            line.append(char, style=style)
        rows.append(line)
    return rows


def _money(value: float) -> str:
    if abs(value) >= 10_000:
        return f"${value / 1000:,.0f}k"
    return f"${value:,.0f}"


def _print_backtest(console: Console, result: FundBacktestResult) -> None:
    m = result.metrics
    console.print(
        f"\n[bold white]BACKTEST RESULTS:[/] [bold cyan]{result.fund}[/]"
        f"  [dim]({result.start} → {result.end} · {result.rebalance} rebalance"
        f" · {m.n_cycles} cycles · {m.n_orders} orders)[/]"
    )
    table = Table(box=box.SQUARE, header_style="bold")
    for header in ("Total Return", "Annualized", "Sharpe", "Max Drawdown",
                   f"{result.benchmark} Return", "Excess"):
        table.add_column(header, justify="right")
    total_tone = "bold green" if m.total_return_pct >= 0 else "bold red"
    sharpe_tone = ("green" if m.sharpe_ratio > 1
                   else "yellow" if m.sharpe_ratio > 0 else "red")
    excess_tone = "bold green" if m.excess_return_pct >= 0 else "bold red"
    table.add_row(
        Text(f"{m.total_return_pct:+.1%}", style=total_tone),
        f"{m.annualized_return_pct:+.1%}",
        Text(f"{m.sharpe_ratio:.2f}", style=sharpe_tone),
        Text(f"{m.max_drawdown_pct:.1%}", style="red"),
        f"{m.benchmark_return_pct:+.1%}",
        Text(f"{m.excess_return_pct:+.1%}", style=excess_tone),
    )
    console.print(table)


def _build_custom_strategy(console: Console):
    """Let the user hand-pick models directly — one at a time, no bundle.

    Returns a StrategySpec, or _BACK if the user presses Esc.
    """
    picked = _ask_checkbox(questionary.checkbox(
        "Pick your agents (or just one, e.g. PEAD alone).",
        choices=[
            questionary.Choice(
                DISPLAY_NAMES.get(key, key)
                + ("" if issubclass(cls, LLMAgent) else " (quant)"),
                value=key,
            )
            for key, cls in ALPHA_MODEL_REGISTRY.items()
        ],
        instruction=_CHECKBOX_INSTRUCTION,
        validate=lambda ps: bool(ps) or "Pick at least one.",
        style=_CHECKBOX_STYLE,
    ))
    if picked is _BACK:
        return _BACK
    return StrategySpec(name="custom", models=[{"name": key} for key in picked])


def _strategy_kind(strategy: StrategySpec) -> str:
    """Discretionary pods are staffed entirely by LLM agents; anything with a
    quant model in the mix is systematic. Derived, never declared."""
    if all(issubclass(ALPHA_MODEL_REGISTRY[m.name], LLMAgent)
           for m in strategy.models):
        return "discretionary"
    return "systematic"


_SHORT_NAMES = {
    "buffett": "Buffett",
    "munger": "Munger",
    "graham": "Graham",
    "lynch": "Lynch",
    "druckenmiller": "Druckenmiller",
    "pead": "PEAD",
}


def _strategy_label(strategy: StrategySpec) -> str:
    """One clean aligned line per strategy: display name, then who runs it."""
    staff = ", ".join(_SHORT_NAMES.get(m.name, m.name) for m in strategy.models)
    return f"{strategy.title:<16} {staff}"


def _print_cycle(console: Console, record: CycleRecord) -> None:
    """The cycle report, v1-style: bold section headers and grid tables.

    The content is entirely real — signals, clamps, orders straight from the
    CycleRecord. Sections land one at a time (paced by _REVEAL_DELAY) so a
    viewer reads the fund thinking instead of receiving a wall of text.
    """
    spec_by_name = {s.name: s for s in record.spec.strategies}
    for sr in record.strategies:
        strategy = spec_by_name[sr.name]
        tags = [_strategy_kind(strategy), f"{sr.slice:.0%} of capital"]
        if strategy.blend.market_neutral:
            tags.insert(1, "market-neutral")
        console.print(
            f"\n[bold white]AGENT ANALYSIS:[/] [bold cyan]{strategy.title}[/]"
            f"  [dim]({' · '.join(tags)})[/]"
        )
        table = Table(box=box.SQUARE, show_lines=True, header_style="bold")
        table.add_column("Ticker", style="bold cyan")
        table.add_column("Agent")
        table.add_column("Signal", justify="center")
        table.add_column("Confidence", justify="right")
        table.add_column("Reasoning", max_width=70, style="dim")
        for s in sr.signals:
            if s.metadata.get("abstained") is True:
                signal = Text("ABSTAIN", style="dim")
            elif s.value > 0:
                signal = Text("BULLISH", style="bold green")
            elif s.value < 0:
                signal = Text("BEARISH", style="bold red")
            else:
                signal = Text("NEUTRAL", style="yellow")
            confidence = s.metadata.get("confidence")
            table.add_row(
                s.ticker,
                DISPLAY_NAMES.get(s.model_name, s.model_name),
                signal,
                f"{confidence:.0f}%" if confidence is not None else "—",
                s.reasoning or "",
            )
        console.print(table)
        time.sleep(_REVEAL_DELAY)

    if record.clamps:
        console.print("\n[bold white]RISK LIMITS:[/]  [dim]hard caps the agents cannot override[/]")
        table = Table(box=box.SQUARE, header_style="bold")
        table.add_column("Scope", style="bold cyan")
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
        console.print(table)
        time.sleep(_REVEAL_DELAY)

    console.print("\n[bold white]ORDERS:[/]")
    if not record.orders:
        console.print("  [dim]none — no conviction cleared the bar today[/]")
    else:
        table = Table(box=box.SQUARE, header_style="bold")
        table.add_column("Action", justify="center")
        table.add_column("Quantity", justify="right")
        table.add_column("Ticker", style="bold cyan")
        table.add_column("Price", justify="right")
        for o in record.orders:
            tone = "bold green" if o.side == "buy" else "bold red"
            table.add_row(
                Text(o.side.upper(), style=tone),
                Text(f"{o.quantity:,}", style=tone),
                o.ticker,
                f"${o.price:,.2f}",
            )
        console.print(table)
    time.sleep(_REVEAL_DELAY)

    console.print("\n[bold white]PORTFOLIO SUMMARY:[/]")
    long_val = short_val = 0.0
    if not record.positions:
        console.print("  [dim]flat — no positions[/]")
    else:
        table = Table(box=box.SQUARE, header_style="bold")
        table.add_column("Ticker", style="bold cyan")
        table.add_column("Side", justify="center")
        table.add_column("Shares", justify="right")
        table.add_column("Value", justify="right")
        table.add_column("Weight", justify="right")
        for ticker in sorted(record.positions):
            shares = record.positions[ticker]
            value = shares * record.marks[ticker]
            long_val += max(value, 0.0)
            short_val += min(value, 0.0)
            side = (Text("LONG", style="bold green") if shares > 0
                    else Text("SHORT", style="bold red"))
            tone = "green" if value >= 0 else "red"
            table.add_row(
                ticker, side, f"{shares:+d}",
                Text(f"${value:+,.0f}", style=tone),
                Text(f"{value / record.nav:+.1%}", style=tone),
            )
        console.print(table)

    gross = (long_val - short_val) / record.nav
    net = (long_val + short_val) / record.nav
    summary = Text()
    summary.append(f"NAV ${record.nav:,.2f}", style="bold white")
    summary.append(f"   Cash ${record.cash:,.0f}", style="cyan")
    summary.append(f"   Gross {gross:.0%}   Net {net:+.0%}", style="dim")
    console.print(summary)
    console.print()


if __name__ == "__main__":
    main()
