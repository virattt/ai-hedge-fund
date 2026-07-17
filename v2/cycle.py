"""Run one cycle of a fund from a YAML mandate.

Usage::

    poetry run python -m v2.cycle v2/funds/example.yaml
    poetry run python -m v2.cycle v2/funds/example.yaml --date 2024-06-03
    poetry run python -m v2.cycle v2/funds/example.yaml --date 2024-06-03 --out record.json

The full CycleRecord prints to stdout as JSON (pipe it anywhere); a short
human summary goes to stderr. This runs against a fresh SimBroker — one
isolated tick, mainly for inspecting what a mandate would do on a date.
"""

from __future__ import annotations

import argparse
from datetime import date as _date
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

from v2.brokers import SimBroker
from v2.data import CachedDataClient, FDClient
from v2.fund import Fund, load_spec
from v2.pipeline import run_cycle


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="python -m v2.cycle",
        description="Run one cycle of a fund from a YAML mandate.",
    )
    parser.add_argument("mandate", help="path to a fund spec YAML, e.g. v2/funds/example.yaml")
    parser.add_argument(
        "--date",
        default=_date.today().isoformat(),
        help="as-of date YYYY-MM-DD (default: today); analysts only see data "
        "filed by this date",
    )
    parser.add_argument("--out", help="also write the CycleRecord JSON to this file")
    args = parser.parse_args()

    console = Console(stderr=True)  # status + summary on stderr; stdout stays pure JSON

    spec = load_spec(args.mandate)
    fund = Fund(spec)
    broker = SimBroker(cash=spec.capital)

    with FDClient() as raw:
        fd = CachedDataClient(raw)
        with console.status(
            f"[cyan]{spec.name}: running one cycle as of {args.date} — "
            f"{len(spec.universe)} tickers x {len(fund.analysts)} analysts…",
            spinner="dots",
        ):
            record = run_cycle(fund, args.date, broker, fd)

    print(record.model_dump_json(indent=2))
    if args.out:
        Path(args.out).write_text(record.model_dump_json(indent=2))

    voting = [s for s in record.signals if s.metadata.get("abstained") is not True]
    console.print(
        f"[bold]{spec.name}[/] @ {record.as_of}  ·  "
        f"{len(record.signals)} signals ({len(record.signals) - len(voting)} abstained)  ·  "
        f"{len(record.clamps)} risk clamps  ·  "
        f"{len(record.orders)} orders  ·  NAV ${record.nav:,.2f}"
    )
    if record.skipped:
        console.print(f"[dim]skipped: {', '.join(s.ticker for s in record.skipped)}[/]")


if __name__ == "__main__":
    main()
