"""Run the AI hedge fund.

Usage::

    aihf
        No arguments: the interactive app — a Textual TUI (the same app as
        `aihf` with no arguments). Build a fund — pick stocks, strategies, rebalance
        cadence — or backtest a saved fund and watch its equity curve draw
        against its benchmark.

    aihf ~/.hedge-fund/mandates/example.yaml --tickers AAPL,MSFT
        With a mandate: run one cycle non-interactively. The full CycleRecord
        prints to stdout as JSON (pipe it anywhere); a short human summary
        goes to stderr. Add --out record.json to also write it to a file.

    aihf ~/.hedge-fund/mandates/example.yaml --tickers AAPL,MSFT --backtest
        Backtest the mandate: run_cycle looped over history at the mandate's
        rebalance cadence; the full result JSON prints to stdout.

A mandate is the desk — strategies, staff, risk, capital, cadence — and never
names tickers; --tickers says what to point it at for this run.

Both paths run the same engine underneath. The interactive app is a thin
client: it only *composes a FundSpec* — the same machine-facing YAML this
CLI reads. Humans click, machines write, the engine reads one thing.
"""

from __future__ import annotations

import argparse
import os
from datetime import date as _date
from datetime import timedelta
from pathlib import Path

from rich.console import Console

from hedge_fund.backtesting import backtest_fund
from hedge_fund.brokers import SimBroker
from hedge_fund.data import CachedDataClient, FDClient
from hedge_fund.fund import Fund, load_spec, normalize_universe
from hedge_fund.paths import ensure_mandates_dir
from hedge_fund.pipeline import run_cycle
from hedge_fund.tui.keys import apply_credentials
from hedge_fund.tui.shared import _BACKTEST_WEEKS


def main() -> None:
    apply_credentials()
    ensure_mandates_dir()
    parser = argparse.ArgumentParser(
        prog="aihf",
        description="Run the AI hedge fund. No arguments: launch the "
        "interactive app. With a mandate YAML: run one cycle and print the "
        "record.",
    )
    parser.add_argument("mandate", nargs="?",
                        help="path to a fund spec YAML, e.g. "
                        "~/.hedge-fund/mandates/example.yaml "
                        "(omit to launch the interactive app)")
    parser.add_argument(
        "--tickers",
        help="what to trade this run, comma or space separated, e.g. "
        "AAPL,MSFT,NVDA — required with a mandate (a fund carries no "
        "watchlist; the universe is a run-time input)",
    )
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
    parser.add_argument(
        "--model",
        help="LLM the investor agents reason with, e.g. claude-opus-5 "
        "(default: HEDGE_FUND_LLM_MODEL env, else the built-in default); quant models "
        "ignore it",
    )
    parser.add_argument("--out", help="also write the record JSON to this file")
    args = parser.parse_args()

    if args.model:
        os.environ["HEDGE_FUND_LLM_MODEL"] = args.model

    if args.mandate is None:
        # The interactive experience is the Textual app. Import it lazily so
        # the non-interactive path never pays to load Textual.
        from hedge_fund.tui.app import HedgeFundApp

        HedgeFundApp().run()
        return

    if not args.tickers:
        parser.error("--tickers is required with a mandate, e.g. --tickers AAPL,MSFT")
    universe = normalize_universe(args.tickers.replace(",", " ").split())

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
                f"({spec.rebalance} rebalance vs {spec.benchmark}) "
                f"over {', '.join(universe)}…",
                spinner="dots",
            ):
                result = backtest_fund(fund, start, args.date, fd, universe)
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
            f"{len(universe)} tickers x {n_models} models "
            f"across {len(fund.strategies)} strategies…",
            spinner="dots",
        ):
            record = run_cycle(fund, args.date, broker, fd, universe)

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


if __name__ == "__main__":
    main()
