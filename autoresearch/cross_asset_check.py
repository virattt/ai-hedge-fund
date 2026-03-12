"""
autoresearch/cross_asset_check.py — Cross-asset generalization test.

Runs the same params on a different universe (energy) to test whether
the strategy generalizes or is tech-specific.

Usage:
    poetry run python -m autoresearch.cross_asset_check
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(__file__).resolve().parent / "cache"

ENERGY_TICKERS = ["XOM", "CVX", "OXY", "SLB", "EOG"]
TECH_TICKERS = ["AAPL", "NVDA", "MSFT", "GOOGL", "TSLA"]


def run_cmd(cmd: list[str], cwd: Path) -> tuple[int, str]:
    """Run command, return (exit_code, stdout+stderr)."""
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode, out


def main():
    print("=" * 60)
    print("CROSS-ASSET GENERALIZATION TEST")
    print("=" * 60)

    # Step 1: Build energy price cache (prices only, no LLM signals)
    print("\n--- Step 1: Caching energy prices ---")
    tickers_str = ",".join(ENERGY_TICKERS)
    code, out = run_cmd(
        [
            sys.executable, "-m", "autoresearch.cache_signals",
            "--tickers", tickers_str,
            "--prices-only",
            "--prices-path", "prices_energy.json",
        ],
        cwd=PROJECT_ROOT,
    )
    if code != 0:
        print(out)
        print("\nFailed to cache energy prices. Check API key / network.")
        sys.exit(1)
    print(out)

    # Step 2: Run backtest on energy (technical-only, no signals)
    print("\n--- Step 2: Backtest on energy universe ---")
    code, out = run_cmd(
        [
            sys.executable, "-m", "autoresearch.evaluate",
            "--tickers", tickers_str,
            "--prices-path", "prices_energy.json",
        ],
        cwd=PROJECT_ROOT,
    )
    if code != 0:
        print(out)
        sys.exit(1)

    # Parse energy metrics
    energy_sharpe = None
    energy_return = None
    energy_dd = None
    for line in out.splitlines():
        if line.startswith("val_sharpe="):
            energy_sharpe = float(line.split("=")[1])
        elif line.startswith("val_return="):
            energy_return = float(line.split("=")[1])
        elif line.startswith("val_max_dd="):
            energy_dd = float(line.split("=")[1])

    # Step 3: Run backtest on tech (baseline)
    print("\n--- Step 3: Backtest on tech universe (baseline) ---")
    code, out = run_cmd(
        [sys.executable, "-m", "autoresearch.evaluate"],
        cwd=PROJECT_ROOT,
    )
    if code != 0:
        print(out)
        sys.exit(1)

    tech_sharpe = None
    tech_return = None
    tech_dd = None
    for line in out.splitlines():
        if line.startswith("val_sharpe="):
            tech_sharpe = float(line.split("=")[1])
        elif line.startswith("val_return="):
            tech_return = float(line.split("=")[1])
        elif line.startswith("val_max_dd="):
            tech_dd = float(line.split("=")[1])

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"\nTech ({', '.join(TECH_TICKERS)}):")
    print(f"  Sharpe: {tech_sharpe:.4f}  Return: {tech_return:.2f}%  Max DD: {tech_dd:.2f}%")
    print(f"\nEnergy ({', '.join(ENERGY_TICKERS)}):")
    print(f"  Sharpe: {energy_sharpe:.4f}  Return: {energy_return:.2f}%  Max DD: {energy_dd:.2f}%")

    if energy_sharpe and tech_sharpe:
        ratio = energy_sharpe / tech_sharpe if tech_sharpe != 0 else 0
        print(f"\nEnergy/Tech Sharpe ratio: {ratio:.2f}")
        if ratio < 0.5:
            print("⚠ Strategy appears tech-specific — weak generalization to energy.")
        elif ratio >= 0.8:
            print("✓ Strategy generalizes reasonably to energy.")
        else:
            print("~ Partial generalization — energy underperforms tech.")


if __name__ == "__main__":
    main()
