"""
autoresearch/paper_trading.py — Run autoresearch strategy for a single day (dry run or paper).

Uses cached prices to compute signals and output suggested orders. Can be extended
to submit to PaperBroker for live paper trading.

Usage:
    poetry run python -m autoresearch.paper_trading
    poetry run python -m autoresearch.paper_trading --date 2026-03-07
    poetry run python -m autoresearch.paper_trading --date 2026-03-07 --weights oos
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from autoresearch.portfolio_backtest import (
    SECTOR_CONFIG,
    SECTOR_OOS_SHARPE,
    load_params,
    run_sector_backtest,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"),
                        help="Date to run (YYYY-MM-DD)")
    parser.add_argument("--weights", choices=["equal", "oos"], default="oos")
    parser.add_argument("--execute", action="store_true", help="Submit to PaperBroker (TODO)")
    args = parser.parse_args()

    date = args.date
    print(f"Paper trading run for {date}")
    print("-" * 50)

    sector_positions = {}
    sector_values = {}

    for sector, (mod, path) in SECTOR_CONFIG.items():
        try:
            pv, metrics, engine = run_sector_backtest(mod, path, start=date, end=date)
            sector_positions[sector] = getattr(engine, "final_positions", {})
            if pv:
                sector_values[sector] = pv[-1]["value"] if pv else 0
            else:
                sector_values[sector] = 0
            print(f"  {sector:12} value=${sector_values.get(sector, 0):,.0f}")
        except Exception as e:
            print(f"  {sector:12} SKIP: {e}")
            continue

    # OOS weights
    oos = {s: max(SECTOR_OOS_SHARPE.get(s, 0), 0.01) for s in sector_positions}
    total_oos = sum(oos.values())
    weights = {s: oos[s] / total_oos for s in sector_positions}

    # Aggregate positions by ticker (sectors don't overlap tickers)
    all_orders = []
    for sector, positions in sector_positions.items():
        w = weights.get(sector, 1.0 / len(sector_positions))
        for ticker, pos in positions.items():
            long_qty = pos.get("long", 0)
            short_qty = pos.get("short", 0)
            if long_qty > 0:
                all_orders.append({"ticker": ticker, "side": "BUY", "quantity": long_qty, "sector": sector, "weight": f"{w:.2%}"})
            if short_qty > 0:
                all_orders.append({"ticker": ticker, "side": "SHORT", "quantity": short_qty, "sector": sector, "weight": f"{w:.2%}"})

    print("-" * 50)
    print("Suggested orders (dry run):")
    for o in all_orders:
        print(f"  {o['side']:5} {o['quantity']:4} {o['ticker']:6} ({o['sector']}, weight {o['weight']})")

    if args.execute:
        print("\n--execute not yet implemented. Use PaperBroker manually.")
        print("See src/execution/paper_broker.py")

    return 0


if __name__ == "__main__":
    sys.exit(main())
