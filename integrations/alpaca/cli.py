"""CLI entry point for the Alpaca-integrated hedge fund runner."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

from integrations.alpaca.run_cycle import CycleInputs, run_cycle
from integrations.alpaca.scheduler import run_daemon
from integrations.alpaca.status import cmd_status
from integrations.alpaca.strategy import load_scheduler_config
from src.cli.input import parse_tickers, select_analysts, select_model

load_dotenv()


def _add_ticker_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--tickers",
        "--ticker",
        dest="tickers",
        type=str,
        help="Comma-separated tickers (e.g., AAPL,MSFT,NVDA)",
    )
    parser.add_argument(
        "--universe",
        dest="universe",
        type=str,
        nargs="?",
        const="latest",
        help="Load tickers from a universe snapshot: 'latest' (default) or a path. "
        "Build one with `alpaca-fund universe build`.",
    )


def _resolve_tickers(args, parser: argparse.ArgumentParser) -> list[str]:
    """Resolve tickers from --tickers or --universe (exactly one required)."""
    if args.tickers and args.universe:
        parser.error("Use either --tickers or --universe, not both.")
    if args.universe:
        from integrations.universe import load_universe_config, resolve_universe_tickers

        try:
            return resolve_universe_tickers(args.universe, load_universe_config().output_dir)
        except ValueError as exc:
            parser.error(str(exc))
    if not args.tickers:
        parser.error("Either --tickers or --universe is required.")
    tickers = parse_tickers(args.tickers)
    if not tickers:
        parser.error("At least one ticker is required.")
    return tickers


def build_run_parser(parser: argparse.ArgumentParser) -> None:
    _add_ticker_source_args(parser)
    parser.add_argument(
        "--broker",
        choices=["noop", "alpaca"],
        default="noop",
        help="Broker backend: noop (dry run, default) or alpaca (sync account from Alpaca)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Submit orders to Alpaca (requires --broker alpaca; paper by default)",
    )
    parser.add_argument("--ollama", action="store_true", help="Use Ollama for local LLM inference")
    parser.add_argument("--model", type=str, help="Model name override (skips interactive prompt)")
    parser.add_argument(
        "--analysts",
        type=str,
        help="Comma-separated analyst keys (skips interactive prompt)",
    )
    parser.add_argument("--analysts-all", action="store_true", help="Use all analysts")
    parser.add_argument(
        "--start-date",
        type=str,
        default=(datetime.now() - relativedelta(months=3)).strftime("%Y-%m-%d"),
        help="Analysis start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Analysis end date (YYYY-MM-DD)",
    )
    parser.add_argument("--show-reasoning", action="store_true", help="Show agent reasoning")
    parser.add_argument(
        "--initial-cash",
        type=float,
        default=100_000.0,
        help="Starting cash for noop broker mode",
    )
    parser.add_argument(
        "--margin-requirement",
        type=float,
        default=0.5,
        help="Margin requirement for short positions",
    )
    parser.add_argument(
        "--no-ledger",
        action="store_true",
        help="Skip writing cycle results to data/ledger/",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")


def build_daemon_parser(parser: argparse.ArgumentParser) -> None:
    _add_ticker_source_args(parser)
    parser.add_argument(
        "--broker",
        choices=["noop", "alpaca"],
        default="alpaca",
        help="Broker backend (default: alpaca — required for market clock)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Submit orders to Alpaca (requires --broker alpaca)",
    )
    parser.add_argument("--show-reasoning", action="store_true", help="Show agent reasoning")
    parser.add_argument(
        "--initial-cash",
        type=float,
        default=100_000.0,
        help="Starting cash for noop broker mode",
    )
    parser.add_argument(
        "--margin-requirement",
        type=float,
        default=0.5,
        help="Margin requirement for short positions",
    )
    parser.add_argument(
        "--no-ledger",
        action="store_true",
        help="Skip writing cycle results to data/ledger/",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")


def cmd_daemon(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Run the US market-hours trading daemon (heavy at open, light every 5m).",
    )
    build_daemon_parser(parser)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.execute and args.broker != "alpaca":
        parser.error("--execute requires --broker alpaca")

    tickers = _resolve_tickers(args, parser)

    config = load_scheduler_config()
    print(
        f"Scheduler config: heavy={config.heavy_model_name} | "
        f"light interval={config.light_interval_minutes}m | "
        f"triggers: price>{config.price_swing_pct}% SPY>{config.spy_move_pct}%"
    )

    try:
        run_daemon(
            args.broker,
            CycleInputs(
                tickers=tickers,
                start_date="",
                end_date="",
                show_reasoning=args.show_reasoning,
                selected_analysts=[],
                model_name=config.heavy_model_name,
                model_provider=config.heavy_model_provider,
                margin_requirement=args.margin_requirement,
                initial_cash=args.initial_cash,
                execute=args.execute,
                save_ledger=not args.no_ledger,
            ),
            config=config,
        )
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    except ImportError as exc:
        print(f"Missing dependency: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_report(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Generate performance reports from Alpaca fills + cycle ledgers.",
    )
    parser.add_argument(
        "--period",
        choices=["daily", "weekly", "monthly", "yearly", "all"],
        default="daily",
        help="Report period (default: daily). 'all' runs daily plus any period ending today.",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Report end date YYYY-MM-DD (default: today's trading date)",
    )
    parser.add_argument(
        "--no-advisory",
        action="store_true",
        help="Skip the LLM-generated upgrade advisory (uses rule-based fallback)",
    )
    args = parser.parse_args(argv)

    from datetime import date as date_cls

    from integrations.alpaca.reporting import (
        build_daily_report,
        build_period_report,
        generate_advisory,
        run_end_of_day_reports,
        save_report,
        _fallback_advisory,
    )

    config = load_scheduler_config()
    day = date_cls.fromisoformat(args.date) if args.date else None

    try:
        if args.period == "all":
            results = run_end_of_day_reports(
                model_name=config.heavy_model_name,
                model_provider=config.heavy_model_provider,
                day=day,
            )
        else:
            if args.period == "daily":
                report = build_daily_report(day)
            else:
                report = build_period_report(args.period, day)
            if args.no_advisory:
                report.advisory = _fallback_advisory(report)
            else:
                report.advisory = generate_advisory(
                    report,
                    model_name=config.heavy_model_name,
                    model_provider=config.heavy_model_provider,
                )
            results = [(report, save_report(report))]
    except ValueError as exc:
        print(f"Report error: {exc}", file=sys.stderr)
        return 1

    for report, path in results:
        print(f"{report.period} report saved: {path}")
        print(
            f"  P&L: {report.pnl} ({report.pnl_pct}%) | fills: {report.fills} | "
            f"turnover: {report.turnover_x}x"
        )
    if results:
        print("\nUpgrade advisory (paste into Cursor):\n")
        print(results[0][0].advisory)
    return 0


def cmd_run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Run one AI hedge fund trading cycle.",
    )
    build_run_parser(parser)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.execute and args.broker != "alpaca":
        parser.error("--execute requires --broker alpaca")

    tickers = _resolve_tickers(args, parser)

    flags = {
        "analysts": args.analysts,
        "analysts_all": args.analysts_all,
        "ollama": args.ollama,
        "model": args.model,
    }
    selected_analysts = select_analysts(flags)
    model_name, model_provider = select_model(args.ollama, args.model)

    try:
        result = run_cycle(
            broker_name=args.broker,
            inputs=CycleInputs(
                tickers=tickers,
                start_date=args.start_date,
                end_date=args.end_date,
                show_reasoning=args.show_reasoning,
                selected_analysts=selected_analysts,
                model_name=model_name,
                model_provider=model_provider,
                margin_requirement=args.margin_requirement,
                initial_cash=args.initial_cash,
                execute=args.execute,
                save_ledger=not args.no_ledger,
            ),
        )
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    except ImportError as exc:
        print(f"Missing dependency: {exc}", file=sys.stderr)
        return 1

    print(f"\n{result.account_summary}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])

    if argv and argv[0] == "status":
        return cmd_status()

    if argv and argv[0] == "daemon":
        return cmd_daemon(argv[1:])

    if argv and argv[0] == "universe":
        from integrations.universe.cli import cmd_universe

        return cmd_universe(argv[1:])

    if argv and argv[0] == "report":
        return cmd_report(argv[1:])

    if argv and argv[0] == "run":
        return cmd_run(argv[1:])

    return cmd_run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
