"""
autoresearch/walk_forward.py — Rolling OOS validation to detect strategy decay.

Runs portfolio backtest over rolling windows (e.g. monthly), logs Sharpe per window,
and flags degradation. Use for periodic health checks.

Usage:
    poetry run python -m autoresearch.walk_forward
    poetry run python -m autoresearch.walk_forward --window-months 3 --step-months 1
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from autoresearch.portfolio_backtest import (
    SECTOR_CONFIG,
    SECTOR_OOS_SHARPE,
    run_sector_backtest,
    portfolio_values_to_returns,
    compute_portfolio_metrics,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--window-months", type=int, default=3, help="OOS window length in months")
    parser.add_argument("--step-months", type=int, default=1, help="Step between windows")
    parser.add_argument("--start", type=str, default="2025-06-01")
    parser.add_argument("--end", type=str, default="2026-03-07")
    parser.add_argument("--output", type=str, help="Save results to CSV")
    args = parser.parse_args()

    from dateutil.relativedelta import relativedelta
    start = datetime.strptime(args.start, "%Y-%m-%d")
    end = datetime.strptime(args.end, "%Y-%m-%d")

    results = []
    w_start = start
    while w_start + relativedelta(months=args.window_months) <= end:
        w_end = w_start + relativedelta(months=args.window_months)
        ws = w_start.strftime("%Y-%m-%d")
        we = w_end.strftime("%Y-%m-%d")
        returns_by_sector = {}
        for sector, (mod, path) in SECTOR_CONFIG.items():
            try:
                pv, _, _ = run_sector_backtest(mod, path, start=ws, end=we)
                ret = portfolio_values_to_returns(pv)
                returns_by_sector[sector] = ret
            except Exception:
                continue
        if not returns_by_sector:
            w_start = w_start + relativedelta(months=args.step_months)
            continue
        import pandas as pd
        aligned = pd.DataFrame(returns_by_sector).dropna(how="all").ffill().bfill().fillna(0)
        oos = {s: max(SECTOR_OOS_SHARPE.get(s, 0), 0.01) for s in returns_by_sector}
        total_oos = sum(oos.values())
        weights = {s: oos[s] / total_oos for s in returns_by_sector}
        port_ret = pd.Series(0.0, index=aligned.index)
        for s in returns_by_sector:
            port_ret = port_ret + weights[s] * aligned[s].reindex(port_ret.index).fillna(0)
        m = compute_portfolio_metrics(port_ret)
        results.append({"start": ws, "end": we, "sharpe": m["sharpe"], "return_pct": m["total_return_pct"]})
        print(f"  {ws} → {we}: Sharpe={m['sharpe']:.2f}, Return={m['total_return_pct']:+.1f}%")
        w_start = w_start + relativedelta(months=args.step_months)

    if args.output and results:
        import csv
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["start", "end", "sharpe", "return_pct"])
            w.writeheader()
            w.writerows(results)
        print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
