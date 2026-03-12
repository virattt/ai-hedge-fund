"""
autoresearch/refresh_oos_weights.py — Recompute OOS Sharpe per sector and output updated weights.

Runs portfolio_backtest over the OOS window (2025-08-01 → 2026-03-07 by default),
extracts per-sector Sharpe, and prints a dict ready to paste into portfolio_backtest.py
or ARR.md. With --regime, computes separate weights for bull vs bear/sideways.

Usage:
    poetry run python -m autoresearch.refresh_oos_weights
    poetry run python -m autoresearch.refresh_oos_weights --regime
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from autoresearch.portfolio_backtest import (
    SECTOR_CONFIG,
    run_sector_backtest,
    portfolio_values_to_returns,
    compute_portfolio_metrics,
)


def _compute_sharpes(sectors, start, end):
    out = {}
    for sector in sectors:
        mod, path = SECTOR_CONFIG[sector]
        try:
            pv, _, _ = run_sector_backtest(mod, path, start=start, end=end)
            ret = portfolio_values_to_returns(pv)
            m = compute_portfolio_metrics(ret)
            out[sector] = (m["sharpe"], m["total_return_pct"])
        except Exception:
            pass
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=str, default="2025-08-01", help="OOS window start")
    parser.add_argument("--end", type=str, default="2026-03-07", help="OOS window end")
    parser.add_argument("--exclude", type=str, default="", help="Comma-separated sectors to exclude")
    parser.add_argument("--regime", action="store_true", help="Compute separate bull vs bear/sideways weights")
    args = parser.parse_args()

    exclude = {s.strip() for s in args.exclude.split(",") if s.strip()}
    sectors = [s for s in SECTOR_CONFIG if s not in exclude]

    if args.regime:
        mid = "2025-11-15"
        print(f"Computing OOS Sharpe by regime")
        print(f"  Bull (H1):   {args.start} → {mid}")
        print(f"  Bear/side:   {mid} → {args.end}")
        print("-" * 50)
        bull = _compute_sharpes(sectors, args.start, mid)
        bear = _compute_sharpes(sectors, mid, args.end)
        for s in sorted(set(bull) | set(bear)):
            b_sh, b_ret = bull.get(s, (0, 0))
            r_sh, r_ret = bear.get(s, (0, 0))
            print(f"  {s:14} bull sharpe={b_sh:5.2f} return={b_ret:+6.1f}%  bear sharpe={r_sh:5.2f} return={r_ret:+6.1f}%")
        print()
        print("SECTOR_OOS_SHARPE_BULL = {")
        for s in sorted(bull.keys()):
            print(f'    "{s}": {bull[s][0]:.2f},')
        print("}")
        print("SECTOR_OOS_SHARPE_BEAR = {")
        for s in sorted(bear.keys()):
            print(f'    "{s}": {bear[s][0]:.2f},')
        print("}")
    else:
        print(f"Computing OOS Sharpe ({args.start} → {args.end})")
        print("-" * 50)
        sharpes = _compute_sharpes(sectors, args.start, args.end)
        for s in sorted(sharpes.keys()):
            sh, ret = sharpes[s]
            print(f"  {s:14} sharpe={sh:6.2f}  return={ret:+6.1f}%")
        print()
        print("SECTOR_OOS_SHARPE = {")
        for s in sorted(sharpes.keys()):
            print(f'    "{s}": {sharpes[s][0]:.2f},')
        print("}")


if __name__ == "__main__":
    main()
