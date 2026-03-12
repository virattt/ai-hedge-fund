"""
autoresearch/cache_signals.py — One-time expensive pre-computation.

Runs the FULL agent pipeline (including LLM calls) across every business day
in the backtest window. Caches:
  1. Per-date analyst signals  →  cache/signals.json
  2. Per-ticker price history  →  cache/prices.json

After this script finishes, `evaluate.py` can run thousands of experiments
in seconds because it never makes LLM or API calls — it reads from cache.

Usage:
    poetry run python -m autoresearch.cache_signals [--tickers AAPL,NVDA] [--start 2025-06-01] [--end 2025-12-01]
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.main import run_hedge_fund
from src.tools.api import get_prices, prices_to_df

CACHE_DIR = Path(__file__).resolve().parent / "cache"


def cache_prices(tickers: list[str], start_date: str, end_date: str) -> dict:
    """Fetch and cache raw price data for all tickers."""
    price_cache = {}
    lookback_start = (datetime.strptime(start_date, "%Y-%m-%d") - relativedelta(months=3)).strftime("%Y-%m-%d")

    for ticker in tickers:
        print(f"  Fetching prices for {ticker} ({lookback_start} → {end_date})...")
        prices = get_prices(ticker, lookback_start, end_date)
        if prices:
            df = prices_to_df(prices)
            records = []
            for _, row in df.iterrows():
                records.append({
                    "date": row.name.strftime("%Y-%m-%d") if hasattr(row.name, "strftime") else str(row.name),
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": float(row.get("volume", 0)),
                })
            price_cache[ticker] = records
            print(f"    → {len(records)} price bars cached")
        else:
            print(f"    → WARNING: No price data for {ticker}")
            price_cache[ticker] = []

    return price_cache


def cache_agent_signals(
    tickers: list[str],
    start_date: str,
    end_date: str,
    model_name: str = "z-ai/glm-4.5-air",
    model_provider: str = "OpenRouter",
) -> dict:
    """Run the full agent pipeline for each business day and cache signals.

    Saves incrementally after every day so partial progress survives crashes.
    On restart, already-cached dates are skipped automatically.
    """
    dates = pd.date_range(start_date, end_date, freq="B")
    signals_path = CACHE_DIR / "signals.json"

    # Resume from existing partial cache if available
    if signals_path.exists():
        with open(signals_path) as f:
            all_signals = json.load(f)
        print(f"  Resuming from existing cache ({len(all_signals)} dates already done)")
    else:
        all_signals = {}

    initial_cash = 100_000

    portfolio = {
        "cash": initial_cash,
        "margin_requirement": 0.5,
        "margin_used": 0.0,
        "positions": {t: {"long": 0, "short": 0, "long_cost_basis": 0.0, "short_cost_basis": 0.0, "short_margin_used": 0.0} for t in tickers},
        "realized_gains": {t: {"long": 0.0, "short": 0.0} for t in tickers},
    }

    total = len(dates)
    for i, current_date in enumerate(dates):
        date_str = current_date.strftime("%Y-%m-%d")
        lookback_start = (current_date - relativedelta(months=1)).strftime("%Y-%m-%d")
        if lookback_start == date_str:
            continue

        if date_str in all_signals:
            print(f"  [{i+1}/{total}] {date_str} — already cached, skipping")
            continue

        print(f"\n[{i+1}/{total}] Running agents for {date_str}...")

        try:
            result = run_hedge_fund(
                tickers=tickers,
                start_date=lookback_start,
                end_date=date_str,
                portfolio=portfolio,
                show_reasoning=False,
                model_name=model_name,
                model_provider=model_provider,
            )

            signals = result.get("analyst_signals", {})
            date_signals = {}
            for agent_id, ticker_signals in signals.items():
                if agent_id.startswith("risk_management"):
                    continue
                agent_data = {}
                for ticker, sig_data in ticker_signals.items():
                    agent_data[ticker] = {
                        "signal": sig_data.get("signal", "neutral"),
                        "confidence": sig_data.get("confidence", 50),
                    }
                date_signals[agent_id] = agent_data

            all_signals[date_str] = date_signals
            print(f"    → Cached signals from {len(date_signals)} agents")

            # Incremental save after every day
            with open(signals_path, "w") as f:
                json.dump(all_signals, f, indent=2)

        except KeyboardInterrupt:
            print("\n\nInterrupted — partial cache already saved on disk.")
            break
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "insufficient_quota" in err_str:
                print("\n\n*** QUOTA EXHAUSTED (429) ***")
                print("LLM provider quota exhausted. Aborting to avoid endless retries.")
                print("Top up credits or switch provider (e.g. --provider Groq, --provider OpenRouter).")
                print("Partial cache saved on disk.")
                meta = {
                    "tickers": tickers,
                    "start_date": start_date,
                    "end_date": end_date,
                    "model": model_name,
                    "provider": model_provider,
                    "has_signals": False,
                    "cached_dates": len(all_signals),
                    "aborted": "quota_exhausted",
                }
                with open(CACHE_DIR / "meta.json", "w") as f:
                    json.dump(meta, f, indent=2)
                sys.exit(1)
            print(f"    → ERROR: {e}")
            all_signals[date_str] = {}
            with open(signals_path, "w") as f:
                json.dump(all_signals, f, indent=2)

    return all_signals


def main():
    parser = argparse.ArgumentParser(description="Cache agent signals for autoresearch")
    parser.add_argument("--tickers", type=str, default="AAPL,NVDA,MSFT,GOOGL,TSLA")
    parser.add_argument("--start", type=str, default="2025-01-02", help="Match params.BACKTEST_START")
    parser.add_argument("--end", type=str, default="2026-03-07", help="Match params.BACKTEST_END")
    parser.add_argument("--model", type=str, default="z-ai/glm-4.5-air")
    parser.add_argument("--provider", type=str, default="OpenRouter")
    parser.add_argument("--prices-only", action="store_true", help="Only cache prices, skip agent signals")
    parser.add_argument("--prices-path", type=str, default="prices.json", help="Output path for prices (relative to cache dir)")
    args = parser.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",")]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("AUTORESEARCH — Signal Cache Builder")
    print("=" * 60)
    print(f"Tickers:    {tickers}")
    print(f"Date range: {args.start} → {args.end}")
    print(f"Model:      {args.model} ({args.provider})")
    print(f"Cache dir:  {CACHE_DIR}")
    print("=" * 60)

    # Phase 1: Cache prices (OVERWRITES — no resume; backup existing first)
    print("\n--- Phase 1: Caching price data ---")
    prices_path = CACHE_DIR / args.prices_path
    if prices_path.exists():
        backup_path = prices_path.with_suffix(".json.bak")
        backup_path.write_text(prices_path.read_text())
        print(f"  Backed up existing prices → {backup_path}")
    price_cache = cache_prices(tickers, args.start, args.end)
    with open(prices_path, "w") as f:
        json.dump(price_cache, f, indent=2)
    print(f"\nPrices saved → {prices_path}")

    if args.prices_only:
        print("\n--prices-only flag set. Skipping agent signals.")
        meta = {"tickers": tickers, "start_date": args.start, "end_date": args.end, "model": args.model, "provider": args.provider, "has_signals": False}
        with open(CACHE_DIR / "meta.json", "w") as f:
            json.dump(meta, f, indent=2)
        print("Done.")
        return

    # Phase 2: Cache agent signals (saves incrementally, resumes on restart)
    print("\n--- Phase 2: Caching agent signals (this takes a while) ---")
    signals_path = CACHE_DIR / "signals.json"
    if signals_path.exists():
        backup_path = CACHE_DIR / "signals.json.bak"
        backup_path.write_text(signals_path.read_text())
        print(f"  Backed up existing signals → {backup_path}")
    signals_cache = cache_agent_signals(tickers, args.start, args.end, args.model, args.provider)
    print(f"\nSignals saved → {signals_path}")

    meta = {
        "tickers": tickers,
        "start_date": args.start,
        "end_date": args.end,
        "model": args.model,
        "provider": args.provider,
        "has_signals": True,
        "cached_dates": len(signals_cache),
    }
    with open(CACHE_DIR / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nCache complete: {len(signals_cache)} dates cached.")
    print("You can now run: poetry run python -m autoresearch.evaluate")


if __name__ == "__main__":
    main()
