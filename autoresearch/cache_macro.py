"""
autoresearch/cache_macro.py — One-time cache for macro interest-rate data.

This script pulls historical interest-rate data from Financial Datasets and
stores the raw JSON payload under `autoresearch/cache/macro_rates.json` so that
regime detection and backtests can operate without re-hitting the API.

Usage:

    poetry run python -m autoresearch.cache_macro \\
        --start 2018-01-01 \\
        --end 2026-03-07
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


def fetch_interest_rates(bank: str, start_date: str, end_date: str) -> dict:
    """
    Fetch macro interest-rate data from Financial Datasets.

    Per the Financial Datasets docs, the historical interest-rates endpoint
    requires a `bank` parameter (e.g. FED, ECB, BOJ). We default to FED
    unless overridden on the CLI.
    """
    api_key = os.environ.get("FINANCIAL_DATASETS_API_KEY", "")
    headers = {"X-API-KEY": api_key} if api_key else {}
    url = f"{FD_BASE_URL}/macro/interest-rates?bank={bank}&start_date={start_date}&end_date={end_date}"
    print(f"  GET {url}")
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"  WARNING: non-200 response from interest-rates endpoint: {resp.status_code}")
        try:
            print(f"  Response body: {resp.text[:500]}")
        except Exception:
            pass
        return {}
    try:
        return resp.json()
    except Exception:
        return {}


def main():
    parser = argparse.ArgumentParser(description="Cache macro interest-rate data for autoresearch")
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
        "--output",
        type=str,
        default="macro_rates.json",
        help="Output filename under autoresearch/cache/",
    )
    parser.add_argument(
        "--bank",
        type=str,
        default="FED",
        help="Central bank code for interest rates (e.g. FED, ECB, BOJ). Defaults to FED.",
    )

    args = parser.parse_args()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("AUTORESEARCH — Macro Rates Cache Builder")
    print("=" * 60)
    print(f"Date range: {args.start} → {args.end}")
    print(f"Cache dir: {CACHE_DIR}")
    print("=" * 60)

    data = fetch_interest_rates(args.bank, args.start, args.end)

    out_path = CACHE_DIR / args.output
    if out_path.exists():
        backup = out_path.with_suffix(".json.bak")
        backup.write_text(out_path.read_text())
        print(f"  Backed up existing macro cache → {backup}")

    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nMacro rates saved → {out_path}")


if __name__ == "__main__":
    main()

