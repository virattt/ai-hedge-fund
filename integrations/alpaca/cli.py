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


def build_run_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--tickers",
        "--ticker",
        dest="tickers",
        type=str,
        required=True,
        help="Comma-separated tickers (e.g., AAPL,MSFT,NVDA)",
    )
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
    parser.add_argument(
        "--tickers",
        "--ticker",
        dest="tickers",
        type=str,
        required=True,
        help="Comma-separated tickers (e.g., AAPL,MSFT,NVDA)",
    )
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

    tickers = parse_tickers(args.tickers)
    if not tickers:
        parser.error("At least one ticker is required.")

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

    tickers = parse_tickers(args.tickers)
    if not tickers:
        parser.error("At least one ticker is required.")

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

    if argv and argv[0] == "run":
        return cmd_run(argv[1:])

    return cmd_run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
