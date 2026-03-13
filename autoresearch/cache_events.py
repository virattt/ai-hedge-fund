"""
autoresearch/cache_events.py — One-time cache for insider trades and company news.

This script pulls insider-trade and news history for a list of tickers using the
helpers in `src.tools.api` and stores results in JSON under `autoresearch/cache/`.

Usage (example):

    poetry run python -m autoresearch.cache_events \\
        --tickers NVDA,TSM,MSFT \\
        --start 2018-01-01 \\
        --end 2026-03-07 \\
        --output-prefix ai_infra
"""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from src.tools.api import get_company_news, get_insider_trades


load_dotenv()

CACHE_DIR = Path(__file__).resolve().parent / "cache"


def cache_insider_trades(
    tickers: list[str],
    start_date: str,
    end_date: str,
    limit: int = 1000,
) -> dict:
    """Fetch insider trades for each ticker."""
    out: dict[str, list[dict]] = {}
    for ticker in tickers:
        print(f"  Fetching insider trades for {ticker} ({start_date} → {end_date})...")
        trades = get_insider_trades(
            ticker=ticker,
            end_date=end_date,
            start_date=start_date,
            limit=limit,
        )
        out[ticker] = [t.model_dump() for t in trades] if trades else []
        print(f"    → {len(out[ticker])} trades cached")
    return out


def cache_company_news(
    tickers: list[str],
    start_date: str,
    end_date: str,
    limit: int = 1000,
) -> dict:
    """Fetch company news for each ticker."""
    out: dict[str, list[dict]] = {}
    for ticker in tickers:
        print(f"  Fetching company news for {ticker} ({start_date} → {end_date})...")
        news_items = get_company_news(
            ticker=ticker,
            end_date=end_date,
            start_date=start_date,
            limit=limit,
        )
        out[ticker] = [n.model_dump() for n in news_items] if news_items else []
        print(f"    → {len(out[ticker])} news items cached")
    return out


def main():
    parser = argparse.ArgumentParser(description="Cache insider trades and news for autoresearch")
    parser.add_argument(
        "--tickers",
        type=str,
        required=True,
        help="Comma-separated tickers (e.g. NVDA,TSM,MSFT)",
    )
    parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=str,
        required=True,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Maximum number of records per request (per ticker)",
    )
    parser.add_argument(
        "--output-prefix",
        type=str,
        default="events",
        help="Prefix for output filenames under autoresearch/cache/",
    )

    args = parser.parse_args()
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("AUTORESEARCH — Events Cache Builder")
    print("=" * 60)
    print(f"Tickers: {tickers}")
    print(f"Date range: {args.start} → {args.end}")
    print(f"Limit per page: {args.limit}")
    print(f"Cache dir: {CACHE_DIR}")
    print("=" * 60)

    print("\n--- Phase 1: Caching insider trades ---")
    insider_cache = cache_insider_trades(
        tickers=tickers,
        start_date=args.start,
        end_date=args.end,
        limit=args.limit,
    )
    insider_path = CACHE_DIR / f"insider_trades_{args.output_prefix}.json"
    if insider_path.exists():
        backup = insider_path.with_suffix(".json.bak")
        backup.write_text(insider_path.read_text())
        print(f"  Backed up existing insider trades → {backup}")
    with open(insider_path, "w") as f:
        json.dump(insider_cache, f, indent=2)
    print(f"Insider trades saved → {insider_path}")

    print("\n--- Phase 2: Caching company news ---")
    news_cache = cache_company_news(
        tickers=tickers,
        start_date=args.start,
        end_date=args.end,
        limit=args.limit,
    )
    news_path = CACHE_DIR / f"news_{args.output_prefix}.json"
    if news_path.exists():
        backup = news_path.with_suffix(".json.bak")
        backup.write_text(news_path.read_text())
        print(f"  Backed up existing news → {backup}")
    with open(news_path, "w") as f:
        json.dump(news_cache, f, indent=2)
    print(f"News saved → {news_path}")

    meta = {
        "tickers": tickers,
        "start_date": args.start,
        "end_date": args.end,
        "limit": args.limit,
        "has_insider_trades": True,
        "has_news": True,
    }
    with open(CACHE_DIR / f"events_meta_{args.output_prefix}.json", "w") as f:
        json.dump(meta, f, indent=2)

    print("\nEvents cache complete.")


if __name__ == "__main__":
    main()

