"""
autoresearch/cache_crypto.py — One-time cache for crypto price history.

This script pulls historical crypto prices for a set of symbols from
Financial Datasets (`GET /crypto/prices`) and stores them in JSON under
`autoresearch/cache/crypto_prices_<prefix>.json`.

Usage:

    poetry run python -m autoresearch.cache_crypto \\
        --symbols BTC,ETH \\
        --start 2018-01-01 \\
        --end 2026-03-07 \\
        --output-prefix core_crypto
"""

import argparse
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()

CACHE_DIR = Path(__file__).resolve().parent / "cache"
FD_BASE_URL = "https://api.financialdatasets.ai"


def fetch_crypto_prices(symbol: str, start_date: str, end_date: str) -> list[dict]:
    """Fetch crypto OHLCV for a symbol."""
    api_key = os.environ.get("FINANCIAL_DATASETS_API_KEY", "")
    headers = {"X-API-KEY": api_key} if api_key else {}
    url = (
        f"{FD_BASE_URL}/crypto/prices/?symbol={symbol}"
        f"&interval=day&interval_multiplier=1&start_date={start_date}&end_date={end_date}"
    )
    print(f"  GET {url}")
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"  WARNING: non-200 response from crypto/prices for {symbol}: {resp.status_code}")
        return []
    try:
        data = resp.json()
        # The exact schema may change; we simply persist the raw 'prices' list or the whole payload.
        if isinstance(data, dict) and "prices" in data:
            return data["prices"] or []
        return data if isinstance(data, list) else []
    except Exception:
        return []


def main():
    parser = argparse.ArgumentParser(description="Cache crypto price history for autoresearch")
    parser.add_argument(
        "--symbols",
        type=str,
        required=True,
        help="Comma-separated crypto symbols (e.g. BTC,ETH)",
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
        "--output-prefix",
        type=str,
        default="crypto",
        help="Prefix for output filename under autoresearch/cache/",
    )

    args = parser.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("AUTORESEARCH — Crypto Prices Cache Builder")
    print("=" * 60)
    print(f"Symbols: {symbols}")
    print(f"Date range: {args.start} → {args.end}")
    print(f"Cache dir: {CACHE_DIR}")
    print("=" * 60)

    cache: dict[str, list[dict]] = {}
    for symbol in symbols:
        print(f"\n--- Caching crypto prices for {symbol} ---")
        cache[symbol] = fetch_crypto_prices(symbol, args.start, args.end)
        print(f"    → {len(cache[symbol])} price bars cached")

    out_path = CACHE_DIR / f"crypto_prices_{args.output_prefix}.json"
    if out_path.exists():
        backup = out_path.with_suffix(".json.bak")
        backup.write_text(out_path.read_text())
        print(f"  Backed up existing crypto cache → {backup}")

    with open(out_path, "w") as f:
        json.dump(cache, f, indent=2)

    meta = {
        "symbols": symbols,
        "start_date": args.start,
        "end_date": args.end,
    }
    meta_path = CACHE_DIR / f"crypto_meta_{args.output_prefix}.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nCrypto prices saved → {out_path}")


if __name__ == "__main__":
    main()

