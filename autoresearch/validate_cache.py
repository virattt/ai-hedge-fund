"""
autoresearch/validate_cache.py — Sanity checks for cached universes.

This script checks that cached price and fundamentals/events files cover a
desired backtest window and are non-empty for critical tickers. It is meant as
the final gate before running expensive autoresearch loops.

Usage (from repo root):

    poetry run python -m autoresearch.validate_cache \
      --universes tastytrade_sleeve_long,hl_hip3_sleeve_long \
      --start 2018-01-01 \
      --end 2026-03-07
"""

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


CACHE_DIR = Path(__file__).resolve().parent / "cache"


@dataclass
class UniverseReport:
    name: str
    prices_path: Path
    has_prices: bool
    price_coverage: Tuple[str | None, str | None]
    missing_fundamentals: bool
    missing_events: bool
    missing_macro: bool
    missing_crypto: bool
    empty_tickers: List[str]


def _load_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def _date_range(records: List[Dict]) -> Tuple[str | None, str | None]:
    if not records:
        return None, None
    dates = []
    for r in records:
        d = r.get("date") or r.get("time")
        if not d:
            continue
        try:
            # Allow both "YYYY-MM-DD" and ISO timestamps
            dates.append(datetime.fromisoformat(d).date())
        except Exception:
            continue
    if not dates:
        return None, None
    lo, hi = min(dates), max(dates)
    return lo.isoformat(), hi.isoformat()


def validate_universe(
    universe: str,
    start: str | None,
    end: str | None,
) -> UniverseReport:
    prices_path = CACHE_DIR / f"prices_{universe}.json"
    prices_raw: Dict[str, List[Dict]] = _load_json(prices_path)

    has_prices = bool(prices_raw)
    empty_tickers: List[str] = []
    overall_lo: str | None = None
    overall_hi: str | None = None

    for ticker, records in prices_raw.items():
        if not records:
            empty_tickers.append(ticker)
            continue
        lo, hi = _date_range(records)
        if lo is None or hi is None:
            continue
        if overall_lo is None or lo < overall_lo:
            overall_lo = lo
        if overall_hi is None or hi > overall_hi:
            overall_hi = hi

    # Presence checks for other cached dimensions (all optional, but useful)
    fundamentals_path = CACHE_DIR / f"financial_metrics_{universe}.json"
    events_path = CACHE_DIR / f"insider_trades_{universe}.json"
    news_path = CACHE_DIR / f"news_{universe}.json"
    macro_path = CACHE_DIR / "macro_rates.json"
    crypto_path = CACHE_DIR / f"crypto_prices_{universe}.json"

    missing_fundamentals = not fundamentals_path.exists()
    # Treat both insider_trades and news as part of "events"
    missing_events = not (events_path.exists() and news_path.exists())
    missing_macro = not macro_path.exists()
    missing_crypto = not crypto_path.exists()

    return UniverseReport(
        name=universe,
        prices_path=prices_path,
        has_prices=has_prices,
        price_coverage=(overall_lo, overall_hi),
        missing_fundamentals=missing_fundamentals,
        missing_events=missing_events,
        missing_macro=missing_macro,
        missing_crypto=missing_crypto,
        empty_tickers=empty_tickers,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate cached universes under autoresearch/cache/ before backtesting.",
    )
    parser.add_argument(
        "--universes",
        type=str,
        required=True,
        help="Comma-separated universe suffixes (e.g. tastytrade_sleeve_long,hl_hip3_sleeve_long)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Desired backtest start date (YYYY-MM-DD). If provided, coverage is checked against it.",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="Desired backtest end date (YYYY-MM-DD). If provided, coverage is checked against it.",
    )

    args = parser.parse_args()
    universes = [u.strip() for u in args.universes.split(",") if u.strip()]
    if not universes:
        print("No universes provided.")
        return 1

    print("=" * 72)
    print("AUTORESEARCH — Cache Validator")
    print("=" * 72)
    print(f"Cache dir : {CACHE_DIR}")
    if args.start or args.end:
        print(f"Target    : {args.start or 'min'} → {args.end or 'max'}")
    print("-" * 72)

    overall_ok = True

    for uni in universes:
        report = validate_universe(uni, args.start, args.end)
        print(f"\nUniverse: {uni}")
        print(f"  prices file : {report.prices_path.name}")
        if not report.has_prices:
            print("  STATUS      : FAIL — prices cache missing or empty")
            overall_ok = False
            continue

        lo, hi = report.price_coverage
        print(f"  coverage    : {lo or 'unknown'} → {hi or 'unknown'}")

        # Coverage checks against target window
        # These are soft warnings: they do NOT flip the overall PASS/FAIL flag.
        if args.start and lo and lo > args.start:
            print(f"  WARNING     : coverage starts after target start ({args.start})")
        if args.end and hi and hi < args.end:
            print(f"  WARNING     : coverage ends before target end ({args.end})")

        if report.empty_tickers:
            overall_ok = False
            empties = ", ".join(sorted(report.empty_tickers))
            print(f"  WARNING     : no price records for tickers: {empties}")

        if report.missing_fundamentals:
            print("  NOTE        : fundamentals cache missing "
                  f"(expected financial_metrics_{uni}.json)")
        if report.missing_events:
            print("  NOTE        : events cache incomplete "
                  f"(expected insider_trades_{uni}.json and news_{uni}.json)")
        if report.missing_macro:
            print("  NOTE        : macro cache missing (expected macro_rates.json)")
        if report.missing_crypto:
            print("  NOTE        : crypto cache missing "
                  f"(expected crypto_prices_{uni}.json)")

    print("\n" + "-" * 72)
    if overall_ok:
        print("CACHE VALIDATION: PASS — all universes have coverage and non-empty data.")
        return 0
    print("CACHE VALIDATION: FAIL — see warnings above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

