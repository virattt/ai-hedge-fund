"""
autoresearch/sector_correlation.py — Analyze return correlations between sector strategies.

Runs each sector backtest, collects daily returns, and computes the correlation matrix.
Useful for diversification, risk parity, and understanding sector overlap.

Usage:
    poetry run python -m autoresearch.sector_correlation
    poetry run python -m autoresearch.sector_correlation --output autoresearch/logs/sector_corr.csv
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from autoresearch.portfolio_backtest import SECTOR_CONFIG, run_sector_backtest, portfolio_values_to_returns


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=str, help="Override BACKTEST_START")
    parser.add_argument("--end", type=str, help="Override BACKTEST_END")
    parser.add_argument("--exclude", type=str, default="", help="Comma-separated sectors to exclude")
    parser.add_argument("--output", type=str, help="Save correlation matrix to CSV")
    args = parser.parse_args()

    exclude = {s.strip() for s in args.exclude.split(",") if s.strip()}
    sectors = [s for s in SECTOR_CONFIG if s not in exclude]

    print("Sector correlation analysis")
    print("-" * 50)

    returns_by_sector = {}
    for sector in sectors:
        mod, path = SECTOR_CONFIG[sector]
        try:
            pv, metrics, _ = run_sector_backtest(mod, path, start=args.start, end=args.end)
            ret = portfolio_values_to_returns(pv)
            returns_by_sector[sector] = ret
            print(f"  {sector:14} sharpe={metrics['sharpe_ratio']:6.2f}  return={metrics['total_return_pct']:+6.1f}%")
        except Exception as e:
            print(f"  {sector:14} SKIP: {e}")

    if len(returns_by_sector) < 2:
        print("Need at least 2 sectors.")
        sys.exit(1)

    import pandas as pd
    aligned = pd.DataFrame(returns_by_sector)
    aligned = aligned.dropna(how="all").ffill().bfill().fillna(0)
    corr = aligned.corr()

    print()
    print("Correlation matrix (daily returns):")
    print(corr.round(2).to_string())

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        corr.to_csv(out_path)
        print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
