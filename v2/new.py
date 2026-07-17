"""Build a fund interactively — the human front door to the engine.

Usage::

    poetry run python -m v2.new

Walks you through staffing a fund: pick a universe, pick strategies from the
library (v2/strategies/), confirm risk and capital — then writes the mandate
to v2/funds/<name>.yaml and offers to run the fund's first cycle.

The wizard is a thin client: it only *composes a FundSpec*. The YAML it
writes is the same machine-facing format a chat LLM or the strategy
generator will emit — humans click, machines write, the engine reads one
thing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import questionary
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from v2.brokers import SimBroker
from v2.data import CachedDataClient, FDClient
from v2.fund import Fund, FundSpec, StrategySpec, load_strategy
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

DEFAULT_RISK = {"max_position_pct": 0.25, "max_gross_exposure": 1.0}
DEFAULT_CAPITAL = 100_000.0


def strategy_kind(strategy: StrategySpec) -> str:
    """Discretionary pods are staffed entirely by LLM agents; anything with a
    quant model in the mix is systematic. Derived, never declared."""
    if all(issubclass(ALPHA_MODEL_REGISTRY[m.name], LLMAgent)
           for m in strategy.models):
        return "discretionary"
    return "systematic"


def strategy_label(strategy: StrategySpec) -> str:
    """Discretionary pods are presented by their staff; systematic ones by
    their engine. Nobody anthropomorphizes a drift model."""
    names = ", ".join(DISPLAY_NAMES.get(m.name, m.name) for m in strategy.models)
    tags = [strategy_kind(strategy)]
    if strategy.blend.market_neutral:
        tags.append("market-neutral")
    return f"{strategy.name} — {names} ({', '.join(tags)})"


def main() -> None:
    load_dotenv()
    console = Console()

    library = [load_strategy(p) for p in sorted(STRATEGY_DIR.glob("*.yaml"))]
    n_agents = sum(1 for cls in ALPHA_MODEL_REGISTRY.values()
                   if issubclass(cls, LLMAgent))
    console.print(Panel(
        f"[bold white]AI HEDGE FUND[/] · build your fund\n"
        f"[dim]{n_agents} agents · {len(library)} strategies · add your own in "
        f"v2/signals/ and v2/strategies/[/]",
        border_style="cyan",
    ))

    name = questionary.text("Fund name:", default="my-fund").ask()
    if name is None:
        sys.exit(1)  # ctrl-c
    name = name.strip().replace(" ", "-").lower()

    universe = questionary.checkbox(
        "Pick your stocks:",
        choices=[questionary.Choice(t, checked=t in UNIVERSE_PRESETS[:5])
                 for t in UNIVERSE_PRESETS],
        validate=lambda picked: bool(picked) or "pick at least one",
    ).ask()
    if universe is None:
        sys.exit(1)
    extra = questionary.text("Add more tickers (space-separated, or leave blank):").ask()
    if extra:
        universe.extend(t.upper() for t in extra.split())

    chosen = questionary.checkbox(
        "Pick your strategies:",
        choices=[
            questionary.Choice(
                strategy_label(s),
                value=s,
                checked=s.name in ("fundamental-ls", "earnings-drift"),
            )
            for s in library
        ],
        validate=lambda picked: bool(picked) or "pick at least one",
    ).ask()
    if not chosen:
        sys.exit(1)

    capital = float(questionary.text(
        "Starting capital ($):", default=f"{DEFAULT_CAPITAL:.0f}",
    ).ask() or DEFAULT_CAPITAL)

    # Equal capital slices; power users edit the YAML (or soon: tell the LLM).
    spec = FundSpec(
        name=name,
        universe=universe,
        strategies=[s.model_dump() for s in chosen],
        risk=DEFAULT_RISK,
        capital=capital,
    )

    FUNDS_DIR.mkdir(exist_ok=True)
    path = FUNDS_DIR / f"{name}.yaml"
    path.write_text(yaml.safe_dump(spec.model_dump(), sort_keys=False))

    console.print()
    console.print(f"  [green]✓[/] wrote [bold]{path}[/] — this file IS your fund.")
    console.print("  [dim]Soon an LLM will write it for you in chat; today you clicked it together.[/]\n")
    console.print(Syntax(path.read_text(), "yaml", background_color="default"))

    if not questionary.confirm("Run your fund's first cycle now?", default=True).ask():
        console.print(
            f"\n  Later: [bold]poetry run python -m v2.cycle {path}[/]"
        )
        return

    date = questionary.text("As-of date (YYYY-MM-DD):", default="2025-06-03").ask()
    fund = Fund(spec)
    broker = SimBroker(cash=spec.capital)
    with FDClient() as raw:
        fd = CachedDataClient(raw)
        with console.status(
            f"[cyan]{len(spec.universe)} stocks × your analysts are reading "
            f"the filings (only data filed by {date})…",
            spinner="dots",
        ):
            record = run_cycle(fund, date, broker, fd)

    _print_cycle(console, record)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _print_cycle(console: Console, record: CycleRecord) -> None:
    """The first-cycle report: every thesis, every clamp, the resulting book."""
    spec_by_name = {s.name: s for s in record.spec.strategies}
    for sr in record.strategies:
        strategy = spec_by_name[sr.name]
        tags = [strategy_kind(strategy), f"{sr.slice:.0%} of capital"]
        if strategy.blend.market_neutral:
            tags.insert(1, "market-neutral")
        console.print(f"\n[bold cyan]{sr.name}[/]  [dim]({' · '.join(tags)})[/]")
        for s in sr.signals:
            if s.metadata.get("abstained") is True:
                console.print(f"  [dim]{s.ticker:6} {s.model_name}: abstained[/]")
                continue
            tone = "green" if s.value > 0 else "red" if s.value < 0 else "dim"
            view = "BULLISH" if s.value > 0 else "BEARISH" if s.value < 0 else "neutral"
            line = f"  [bold]{s.ticker:6}[/] {DISPLAY_NAMES.get(s.model_name, s.model_name)}: [{tone}]{view} {s.value:+.2f}[/]"
            console.print(line)
            if s.reasoning:
                console.print(f"         [dim]{s.reasoning[:160]}[/]")

    if record.clamps:
        console.print("\n[bold yellow]risk desk[/]")
        for c in record.clamps:
            where = c.ticker or "whole book"
            console.print(
                f"  clamped {where}: {c.before:+.2f} → {c.after:+.2f}  [dim]({c.limit})[/]"
            )

    console.print("\n[bold]orders[/]")
    if not record.orders:
        console.print("  [dim]none — no conviction cleared the bar today[/]")
    for o in record.orders:
        tone = "green" if o.side == "buy" else "red"
        console.print(f"  [{tone}]{o.side.upper():4}[/] {o.quantity} {o.ticker} @ ${o.price:,.2f}")

    console.print(
        f"\n  [bold green]✓[/] NAV [bold]${record.nav:,.2f}[/]"
        f"  ·  cash ${record.cash:,.2f}"
        f"  ·  every call above is explained and on the record\n"
    )


if __name__ == "__main__":
    main()
