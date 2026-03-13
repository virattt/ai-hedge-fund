"""
autoresearch/cache_fundamentals.py — One-time cache for fundamentals and metrics.

This script pulls fundamental data for a list of tickers using the existing
FinancialDatasets-backed helpers in `src.tools.api` and stores everything in
JSON under `autoresearch/cache/`, so backtests and agents can read it locally
without re-hitting the external API.

Usage (example):

    poetry run python -m autoresearch.cache_fundamentals \\
        --tickers NVDA,TSM,MSFT \\
        --end 2026-03-07 \\
        --output-prefix ai_infra

This will write:

    autoresearch/cache/financial_metrics_ai_infra.json
"""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from src.tools.api import get_financial_metrics


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(__file__).resolve().parent / "cache"


def cache_financial_metrics(
    tickers: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 100,
) -> dict:
    """
    Fetch financial metrics for each ticker and return as a dict:
        { ticker: [ {metric...}, ... ], ... }
    """
    out: dict[str, list[dict]] = {}
    for ticker in tickers:
        print(f"  Fetching financial metrics for {ticker} (period={period}, end={end_date})...")
        metrics = get_financial_metrics(ticker, end_date=end_date, period=period, limit=limit)
        out[ticker] = [m.model_dump() for m in metrics] if metrics else []
        print(f"    → {len(out[ticker])} metric rows cached")
    return out


def main():
    parser = argparse.ArgumentParser(description="Cache fundamental metrics for autoresearch")
    parser.add_argument(
        "--tickers",
        type=str,
        required=True,
        help="Comma-separated tickers (e.g. NVDA,TSM,MSFT)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default="2026-03-07",
        help="Last report date to include (YYYY-MM-DD, used as report_period_lte)",
    )
    parser.add_argument(
        "--period",
        type=str,
        default="ttm",
        help='FinancialDatasets period parameter (e.g. "ttm", "annual", "quarterly")',
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of records per ticker from /financial-metrics",
    )
    parser.add_argument(
        "--output-prefix",
        type=str,
        default="fundamentals",
        help="Prefix for output filename under autoresearch/cache/",
    )

    args = parser.parse_args()
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("AUTORESEARCH — Fundamentals Cache Builder")
    print("=" * 60)
    print(f"Tickers: {tickers}")
    print(f"End date: {args.end}")
    print(f"Period: {args.period}")
    print(f"Limit per ticker: {args.limit}")
    print(f"Cache dir: {CACHE_DIR}")
    print("=" * 60)

    print("\n--- Phase 1: Caching financial metrics ---")
    metrics_cache = cache_financial_metrics(
        tickers=tickers,
        end_date=args.end,
        period=args.period,
        limit=args.limit,
    )

    metrics_path = CACHE_DIR / f"financial_metrics_{args.output_prefix}.json"
    if metrics_path.exists():
        backup = metrics_path.with_suffix(".json.bak")
        backup.write_text(metrics_path.read_text())
        print(f"  Backed up existing metrics → {backup}")

    with open(metrics_path, "w") as f:
        json.dump(metrics_cache, f, indent=2)
    print(f"\nFinancial metrics saved → {metrics_path}")

    meta = {
        "tickers": tickers,
        "end_date": args.end,
        "period": args.period,
        "limit": args.limit,
        "has_financial_metrics": True,
    }
    with open(CACHE_DIR / f"fundamentals_meta_{args.output_prefix}.json", "w") as f:
        json.dump(meta, f, indent=2)

    print("\nFundamentals cache complete.")


if __name__ == "__main__":
    main()

