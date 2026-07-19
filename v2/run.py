"""Run the AI hedge fund.

Usage::

    poetry run python -m v2.run
        No arguments: the interactive experience. Build a fund — pick stocks,
        pick strategies, set capital — then watch it run its first cycle.

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
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from v2.brokers import SimBroker
from v2.data import CachedDataClient, FDClient
from v2.fund import Fund, FundSpec, StrategySpec, load_spec, load_strategy
from v2.pipeline import CycleRecord, run_cycle
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
DEFAULT_DATE = "2025-06-03"
_REVEAL_DELAY = 0.7   # seconds between theses in the first-cycle reveal
_ROSTER_DWELL = 0.5  # min seconds a roster row lingers on a ticker (readable on warm cache)

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
    parser.add_argument("--out", help="also write the CycleRecord JSON to this file")
    args = parser.parse_args()

    if args.mandate is None:
        _interactive()
        return

    console = Console(stderr=True)  # status + summary on stderr; stdout stays pure JSON
    spec = load_spec(args.mandate)
    fund = Fund(spec)
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

    library = sorted(
        (load_strategy(p) for p in STRATEGY_DIR.glob("*.yaml")),
        key=lambda s: (_strategy_kind(s) == "systematic", s.name),
    )
    console.print(Panel(
        f"[bold white]AI HEDGE FUND[/] · {VERSION}",
        border_style="cyan",
    ))

    # The builder is a small state machine: each step reads/writes `state` and
    # returns _BACK when the user presses Esc, so we can rewind one step.
    state: dict = {}
    steps = [_step_name, _step_tickers, _step_strategies(library), _step_capital]
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

    record = _run_with_roster(console, spec, DEFAULT_DATE)
    _print_cycle(console, record)


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
    agent_names: list[str] = []
    for strategy in spec.strategies:
        for m in strategy.models:
            if m.name not in agent_names:
                agent_names.append(m.name)
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
                row.append(f"[{ticker}] ", style="cyan")
                row.append("Analyzing", style="yellow")
            else:
                row.append("⋯ ", style="dim")
                row.append(f"{name:<24}", style="dim")
                row.append("queued", style="dim")
            table.add_row(row)
        return table


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
