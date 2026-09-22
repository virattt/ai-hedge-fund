"""Run the scheduler daemon.

Usage::

    python -m hedge_fund.daemon ~/.hedge-fund/mandates/example.yaml --tickers AAPL,MSFT
        Poll on --interval (default 60s). Each evaluation uses the market
        calendar and the mandate's rebalance cadence. Paper venue is the
        default; --venue sim is the other allowed book. A kill-switch file
        or HEDGE_FUND_KILL_SWITCH stops new ticks.

    python -m hedge_fund.daemon ~/.hedge-fund/mandates/example.yaml --tickers AAPL,MSFT --once
        One evaluation, then exit. Same rules; no polling sleep. The
        TickResult prints to stdout as JSON (the CycleRecord is nested
        when the tick ran).

    python -m hedge_fund.daemon ~/.hedge-fund/mandates/example.yaml --tickers AAPL,MSFT --config schedule.yaml
        Load interval / venue / kill-switch / lookback from YAML; CLI
        flags override the file.

A mandate is the desk and never names tickers; --tickers says what to
point it at. Live venues are rejected.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date as _date
from pathlib import Path

import yaml
from rich.console import Console

from hedge_fund.daemon import (
    DEFAULT_INTERVAL_SECONDS,
    DEFAULT_LOOKBACK_DAYS,
    KILL_SWITCH_ENV,
    FileTickStore,
    KillSwitch,
    ScheduleConfig,
    TickResult,
    VENUES,
    evaluate_tick,
    run_loop,
)
from hedge_fund.data import CachedDataClient, FDClient
from hedge_fund.fund import Fund, load_spec, normalize_universe
from hedge_fund.paths import KILL_SWITCH_PATH, TICKS_DIR, USER_DIR, ensure_mandates_dir
from hedge_fund.tui.keys import apply_credentials

_SCHEDULE_KEYS = {"interval_seconds", "venue", "lookback_days", "kill_switch", "ticks_dir"}


def _load_schedule_file(path: Path) -> dict:
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: schedule config must be a mapping")
    unknown = set(data) - _SCHEDULE_KEYS
    if unknown:
        raise ValueError(f"{path}: unknown schedule keys: {sorted(unknown)}")
    return data


def _build_schedule(args: argparse.Namespace) -> ScheduleConfig:
    raw = _load_schedule_file(Path(args.config)) if args.config else {}
    interval = (
        args.interval if args.interval is not None
        else raw.get("interval_seconds", DEFAULT_INTERVAL_SECONDS)
    )
    venue = args.venue if args.venue is not None else raw.get("venue", "paper")
    lookback = (
        args.lookback if args.lookback is not None
        else raw.get("lookback_days", DEFAULT_LOOKBACK_DAYS)
    )
    kill_path = (
        Path(args.kill_switch).expanduser() if args.kill_switch
        else Path(raw["kill_switch"]).expanduser() if raw.get("kill_switch")
        else KILL_SWITCH_PATH
    )
    ticks_dir = (
        Path(args.ticks_dir).expanduser() if args.ticks_dir
        else Path(raw["ticks_dir"]).expanduser() if raw.get("ticks_dir")
        else TICKS_DIR
    )
    return ScheduleConfig(
        interval_seconds=float(interval),
        venue=venue,
        lookback_days=int(lookback),
        kill_switch_path=kill_path,
        ticks_dir=ticks_dir,
    )


def _result_payload(result: TickResult) -> dict:
    payload = {
        "status": result.status,
        "reason": result.reason,
        "key": result.key,
        "session_date": result.session_date,
        "venue": result.venue,
    }
    if result.record is not None:
        payload["record"] = json.loads(result.record.model_dump_json())
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m hedge_fund.daemon",
        description="Always-on scheduler: run_cycle on the market calendar "
        "with idempotent ticks and a kill-switch. Paper or sim venue only.",
    )
    parser.add_argument(
        "mandate",
        help="path to a fund spec YAML, e.g. ~/.hedge-fund/mandates/example.yaml",
    )
    parser.add_argument(
        "--tickers",
        required=True,
        help="what to trade this run, comma or space separated, e.g. AAPL,MSFT",
    )
    parser.add_argument(
        "--date",
        help="as-of date YYYY-MM-DD (default: today, re-read each poll)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        help=f"seconds between polls (default: {DEFAULT_INTERVAL_SECONDS:g}; "
        "ignored with --once)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="evaluate one tick and exit — no polling sleep",
    )
    parser.add_argument(
        "--venue",
        choices=VENUES,
        help="paper (default, live clock, no live venue) or sim",
    )
    parser.add_argument(
        "--config",
        help="schedule YAML: interval_seconds, venue, lookback_days, "
        "kill_switch, ticks_dir (CLI flags override)",
    )
    parser.add_argument(
        "--kill-switch",
        help=f"path that, if present, halts new ticks "
        f"(default: {KILL_SWITCH_PATH}; also {KILL_SWITCH_ENV}=1)",
    )
    parser.add_argument(
        "--ticks-dir",
        help=f"directory for idempotency keys (default: {TICKS_DIR})",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        help=f"calendar days of benchmark bars for the session grid "
        f"(default: {DEFAULT_LOOKBACK_DAYS})",
    )
    parser.add_argument(
        "--model",
        help="LLM the investor personas reason with "
        "(default: HEDGE_FUND_LLM_MODEL env, else the built-in default)",
    )
    parser.add_argument(
        "--receipts",
        help="directory for CycleRecord receipts (default: the mandates dir)",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    apply_credentials()
    ensure_mandates_dir()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.model:
        os.environ["HEDGE_FUND_LLM_MODEL"] = args.model

    try:
        schedule = _build_schedule(args)
    except ValueError as exc:
        parser.error(str(exc))

    universe = normalize_universe(args.tickers.replace(",", " ").split())
    spec = load_spec(args.mandate)
    fund = Fund(spec)
    receipts = Path(args.receipts).expanduser() if args.receipts else ensure_mandates_dir()
    receipts.mkdir(parents=True, exist_ok=True)
    store = FileTickStore(schedule.ticks_dir)
    kill_switch = KillSwitch(schedule.kill_switch_path)
    console = Console(stderr=True)

    console.print(
        f"[dim]scheduler · {schedule.venue} venue · "
        f"{spec.rebalance} rebalance vs {spec.benchmark} · "
        f"kill-switch {schedule.kill_switch_path} "
        f"(or {KILL_SWITCH_ENV})[/]"
    )

    def one_tick() -> TickResult:
        as_of = args.date or _date.today().isoformat()
        with FDClient() as raw:
            data = CachedDataClient(raw)
            return evaluate_tick(
                fund,
                universe,
                as_of=as_of,
                data_client=data,
                receipts=receipts,
                store=store,
                kill_switch=kill_switch,
                venue=schedule.venue,
                lookback_days=schedule.lookback_days,
            )

    def report(result: TickResult) -> None:
        if result.status == "ran":
            record = result.record
            assert record is not None
            console.print(
                f"[bold]{spec.name}[/] @ {record.as_of}  ·  "
                f"{result.key}  ·  {len(record.orders)} orders  ·  "
                f"NAV ${record.nav:,.2f}"
            )
        elif result.status == "halted":
            console.print(f"[red]halted[/] {result.reason}")
        else:
            console.print(f"[dim]{result.status}: {result.reason}[/]")

    if args.once:
        result = one_tick()
        report(result)
        print(json.dumps(_result_payload(result), indent=2))
        return

    console.print(
        f"[dim]polling every {schedule.interval_seconds:g}s — "
        f"touch {schedule.kill_switch_path} or export {KILL_SWITCH_ENV}=1 "
        f"to halt; keys under {schedule.ticks_dir}[/]"
    )
    USER_DIR.mkdir(parents=True, exist_ok=True)

    def on_tick() -> TickResult:
        result = one_tick()
        report(result)
        return result

    run_loop(
        on_tick,
        interval_seconds=schedule.interval_seconds,
        sleep=time.sleep,
        once=False,
    )


if __name__ == "__main__":
    main()
