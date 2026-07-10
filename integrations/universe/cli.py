"""`alpaca-fund universe` subcommands: build, show, backtest."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from datetime import datetime

from dotenv import load_dotenv

from integrations.universe.config import load_universe_config
from integrations.universe.store import load_latest_universe, load_universe

load_dotenv()


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def cmd_build(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="alpaca-fund universe build",
        description="Score all tradable US equities and select the trading universe.",
    )
    parser.add_argument("--as-of", type=str, default=_today(), help="Selection date (YYYY-MM-DD, default today)")
    parser.add_argument("--size", type=int, help="Universe size override (default from config: 127)")
    parser.add_argument("--stage2-size", type=int, help="Shortlist size for expensive factors (default 300)")
    parser.add_argument("--min-dollar-volume", type=float, help="Stage 0 median dollar volume gate")
    parser.add_argument("--skip-learnability", action="store_true", help="Skip the Alpha Learnability replay (much faster)")
    parser.add_argument("--no-save", action="store_true", help="Do not write the snapshot to disk")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    config = load_universe_config()
    overrides = {}
    if args.size is not None:
        overrides["size"] = args.size
    if args.stage2_size is not None:
        overrides["stage2_size"] = args.stage2_size
    if args.min_dollar_volume is not None:
        overrides["min_median_dollar_volume"] = args.min_dollar_volume
    if args.skip_learnability:
        overrides["learnability_enabled"] = False
    if overrides:
        config = replace(config, **overrides)

    from integrations.universe.data import AlpacaUniverseDataSource
    from integrations.universe.pipeline import build_universe

    try:
        source = AlpacaUniverseDataSource(config)
        snapshot = build_universe(source, config, args.as_of, save=not args.no_save)
    except (ValueError, ImportError) as exc:
        print(f"Universe build failed: {exc}", file=sys.stderr)
        return 1

    _print_snapshot(snapshot, top=config.size)
    return 0


def cmd_show(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="alpaca-fund universe show",
        description="Display a universe snapshot.",
    )
    parser.add_argument("--path", type=str, default="latest", help="Snapshot path or 'latest' (default)")
    parser.add_argument("--top", type=int, default=25, help="How many rows of the breakdown to print")
    args = parser.parse_args(argv)

    config = load_universe_config()
    if args.path.strip().lower() == "latest":
        snapshot = load_latest_universe(config.output_dir)
        if snapshot is None:
            print(f"No universe snapshots found in {config.output_dir}.", file=sys.stderr)
            return 1
    else:
        try:
            snapshot = load_universe(args.path)
        except (OSError, ValueError) as exc:
            print(f"Could not load snapshot: {exc}", file=sys.stderr)
            return 1

    _print_snapshot(snapshot, top=args.top)
    return 0


def cmd_backtest(argv: list[str]) -> int:
    from integrations.universe.backtest import run_comparison_backtest

    return run_comparison_backtest(argv)


def _print_snapshot(snapshot, *, top: int) -> None:
    print(f"\nUniverse as of {snapshot.as_of} — {snapshot.size} tickers")
    print(f"Generated: {snapshot.generated_at}")
    for stage, count in snapshot.stage_counts.items():
        print(f"  {stage}: {count}")

    selected = {s.ticker: s for s in snapshot.scores if s.ticker in set(snapshot.tickers)}
    print(f"\n{'#':>4}  {'Ticker':<7} {'Composite':>10}  {'Sector':<24} {'Learnability':>12}")
    for i, ticker in enumerate(snapshot.tickers[:top], start=1):
        score = selected.get(ticker)
        if score is None:
            print(f"{i:>4}  {ticker:<7}")
            continue
        learn = score.factors.get("alpha_learnability")
        learn_str = f"{learn.raw:+.3f}" if learn and learn.raw is not None else "-"
        print(
            f"{i:>4}  {ticker:<7} {score.composite:>10.4f}  "
            f"{(score.sector or 'UNKNOWN')[:24]:<24} {learn_str:>12}"
        )
    if snapshot.size > top:
        print(f"  ... and {snapshot.size - top} more")

    print("\nTickers:")
    print(",".join(snapshot.tickers))
    if snapshot.caveats:
        print("\nCaveats:")
        for caveat in snapshot.caveats:
            print(f"  - {caveat}")


def cmd_universe(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help"}:
        print("Usage: alpaca-fund universe {build|show|backtest} [options]")
        print("  build     Score all tradable US equities and select the universe")
        print("  show      Display a saved universe snapshot")
        print("  backtest  Compare ranked universe vs baselines (LLM-free)")
        return 0

    command, rest = argv[0], argv[1:]
    if command == "build":
        return cmd_build(rest)
    if command == "show":
        return cmd_show(rest)
    if command == "backtest":
        return cmd_backtest(rest)
    print(f"Unknown universe command: {command}", file=sys.stderr)
    return 1
