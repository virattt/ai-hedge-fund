"""CLI for monitors (PRD v4 §14, research-only).

    python -m src.monitoring create --name "AI weekly" --tickers NVDA,MSFT --granularity weekly
    python -m src.monitoring run --name "AI weekly" --date 2026-06-12
    python -m src.monitoring list

``run`` invokes TradingAgents' debate graph (needs the TradingAgents env + LLM
keys); on any failure it emits a degraded, disclaimer-carrying report.
"""

import argparse
from datetime import date

from src.monitoring.runner import create_monitor, run_monitor
from src.storage import engine, session_scope
from src.storage.models import Base, MonitorConfig


def _cmd_create(args: argparse.Namespace) -> int:
    Base.metadata.create_all(bind=engine)
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    with session_scope() as s:
        monitor = create_monitor(s, name=args.name, tickers=tickers, granularity=args.granularity)
        print(f"monitor '{monitor.name}' tickers={monitor.tickers} granularity={monitor.granularity}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    Base.metadata.create_all(bind=engine)
    with session_scope() as s:
        monitor = s.query(MonitorConfig).filter_by(name=args.name).one_or_none()
        if monitor is None:
            print(f"no monitor named '{args.name}'")
            return 1
        result = run_monitor(s, monitor, trade_date=args.date)
        print(f"ran '{result.monitor_name}': {len(result.reports)} report(s)")
        for r in result.reports:
            print(f"  {r['ticker']:<6} label={r['label']:<22} degraded={r['degraded']} conf={r['confidence']}")
    return 0


def _cmd_list(_args: argparse.Namespace) -> int:
    with session_scope() as s:
        monitors = s.query(MonitorConfig).order_by(MonitorConfig.name).all()
        for mon in monitors:
            print(f"  {mon.name:<24} tickers={mon.tickers} granularity={mon.granularity} enabled={mon.enabled}")
        if not monitors:
            print("  (no monitors)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="monitoring", description="Stock monitoring (research-only).")
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("create", help="create/update a monitor")
    c.add_argument("--name", required=True)
    c.add_argument("--tickers", required=True, help="comma-separated, e.g. NVDA,MSFT")
    c.add_argument("--granularity", default="weekly", choices=["daily", "weekly", "monthly", "custom"])
    c.set_defaults(func=_cmd_create)

    r = sub.add_parser("run", help="run a monitor once via the analyzing flow")
    r.add_argument("--name", required=True)
    r.add_argument("--date", default=date.today().isoformat())
    r.set_defaults(func=_cmd_run)

    sub.add_parser("list", help="list monitors").set_defaults(func=_cmd_list)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
