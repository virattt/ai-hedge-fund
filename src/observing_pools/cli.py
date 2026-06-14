"""CLI for the observing-pools workflow (PRD v4 §9.8 / §14).

    python -m src.observing_pools init
    python -m src.observing_pools refresh --platform ai --universe data/universes/ai_seed.csv --top 20 --dry-run
    python -m src.observing_pools inspect --platform ai

Research-only: prints ranked pools, never trade instructions.
"""

import argparse
from datetime import date
from functools import partial

from src.observing_pools.pipeline import RefreshConfig, refresh_pool
from src.observing_pools.platforms import PLATFORM_KEYS, init_platforms
from src.observing_pools.universe import load_seed_csv, upsert_candidates
from src.storage import engine, session_scope
from src.storage.models import Base, ObservationPoolEntry

DEFAULT_UNIVERSE = "data/universes/ai_seed.csv"


def _cmd_init(args: argparse.Namespace) -> int:
    Base.metadata.create_all(bind=engine)  # dev convenience; migrations authoritative in P2
    with session_scope() as s:
        init_platforms(s)
        if args.universe:
            rows, rejected = load_seed_csv(args.universe)
            upsert_candidates(s, rows)
            print(f"loaded universe: {len(rows)} candidates, {len(rejected)} rejected")
    print(f"initialized {len(PLATFORM_KEYS)} platforms: {', '.join(PLATFORM_KEYS)}")
    return 0


def _cmd_refresh(args: argparse.Namespace) -> int:
    # Lazy import: only the real refresh needs the (heavy) agent stack.
    from src.observing_pools.scoring_graph import run_scoring_analysts

    runner = partial(run_scoring_analysts, model_name=args.model, model_provider=args.provider)
    config = RefreshConfig(
        platform_key=args.platform,
        universe_csv=args.universe,
        top_n=args.top,
        token_budget=args.budget,
        dry_run=args.dry_run,
    )
    Base.metadata.create_all(bind=engine)
    with session_scope() as s:
        run = refresh_pool(s, config, runner, end_date=args.end_date)
        summary = run.summary or {}
        print(f"refresh status={run.status} platform={args.platform} " f"ranked={summary.get('ranked')} unavailable={summary.get('data_unavailable')} " f"dry_run={args.dry_run}")
        if summary.get("top_tickers"):
            print("top:", ", ".join(summary["top_tickers"]))
    return 0 if run.status != "error" else 1


def _cmd_inspect(args: argparse.Namespace) -> int:
    with session_scope() as s:
        q = s.query(ObservationPoolEntry).filter_by(platform_key=args.platform)
        ranked = q.filter(ObservationPoolEntry.rank.isnot(None)).order_by(ObservationPoolEntry.rank).all()
        print(f"pool '{args.platform}': {len(ranked)} ranked entries")
        for e in ranked:
            print(f"  #{e.rank:<3} {e.ticker:<6} composite={e.composite_score:.1f}  " f"[fit={e.platform_fit_score:.0f} val={_fmt(e.value_investor_score)} " f"grw={_fmt(e.innovation_growth_score)} mom={_fmt(e.risk_adjusted_momentum_score)}]")
    return 0


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.0f}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="observing_pools", description="Innovation observing pools (research-only).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create tables, seed the 5 platforms, load a universe")
    p_init.add_argument("--universe", default=DEFAULT_UNIVERSE, help="seed CSV (set empty to skip)")
    p_init.set_defaults(func=_cmd_init)

    p_ref = sub.add_parser("refresh", help="rank a platform pool via the analyst committee")
    p_ref.add_argument("--platform", required=True, choices=PLATFORM_KEYS)
    p_ref.add_argument("--universe", default=DEFAULT_UNIVERSE)
    p_ref.add_argument("--top", type=int, default=20)
    p_ref.add_argument("--budget", type=int, default=None, help="max analyst-call proxy before partial")
    p_ref.add_argument("--end-date", default=date.today().isoformat())
    p_ref.add_argument("--model", default="gpt-4.1")
    p_ref.add_argument("--provider", default="OpenAI")
    p_ref.add_argument("--dry-run", action="store_true", help="compute + print, persist nothing")
    p_ref.set_defaults(func=_cmd_refresh)

    p_ins = sub.add_parser("inspect", help="print the current ranked pool")
    p_ins.add_argument("--platform", required=True, choices=PLATFORM_KEYS)
    p_ins.set_defaults(func=_cmd_inspect)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
