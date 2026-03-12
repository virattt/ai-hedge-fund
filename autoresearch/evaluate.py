"""
autoresearch/evaluate.py — Run ONE experiment and print the metric.

This is the script the autoresearch loop calls after each modification
to params.py. It must:
  1. Import the current params.py (with the latest changes)
  2. Run the fast backtest
  3. Print a single line: sharpe_ratio=X.XXXX
  4. Append to results.tsv

Exit code 0 = success. Non-zero = crash (the AI agent should revert).

Usage:
    poetry run python -m autoresearch.evaluate
    poetry run python -m autoresearch.evaluate --start 2025-08-01 --end 2026-03-07  # OOS window
"""

import argparse
import importlib
import sys
import types
import time
import traceback
import warnings
from datetime import datetime
from pathlib import Path

# Suppress numpy "Degrees of freedom <= 0" / "invalid value in divide" from rolling stats on short windows
warnings.filterwarnings("ignore", message="Degrees of freedom <= 0", category=RuntimeWarning, module="numpy")
warnings.filterwarnings("ignore", message="invalid value encountered", category=RuntimeWarning, module="numpy")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

RESULTS_FILE = Path(__file__).resolve().parent / "results.tsv"


def load_params():
    """Force-reload params.py to pick up any modifications."""
    import autoresearch.params as params_mod
    importlib.reload(params_mod)
    return params_mod


def make_params_override(base, **overrides):
    """Create a params-like object with overridden attributes."""
    p = types.SimpleNamespace()
    for name in dir(base):
        if not name.startswith("_"):
            setattr(p, name, getattr(base, name))
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


def run_evaluation(start=None, end=None):
    params = load_params()
    if start or end:
        params = make_params_override(
            params,
            BACKTEST_START=start or params.BACKTEST_START,
            BACKTEST_END=end or params.BACKTEST_END,
        )
    from autoresearch.fast_backtest import FastBacktestEngine

    engine = FastBacktestEngine(params)
    metrics = engine.run()
    return metrics


def append_result(metrics: dict, elapsed_ms: int):
    """Append one row to results.tsv."""
    header_needed = not RESULTS_FILE.exists() or RESULTS_FILE.stat().st_size == 0
    with open(RESULTS_FILE, "a") as f:
        if header_needed:
            f.write("timestamp\tsharpe\tsortino\tmax_dd\ttotal_ret\telapsed_ms\n")
        f.write(
            f"{datetime.now().isoformat()}\t"
            f"{metrics['sharpe_ratio']}\t"
            f"{metrics['sortino_ratio']}\t"
            f"{metrics['max_drawdown']}\t"
            f"{metrics['total_return_pct']}\t"
            f"{elapsed_ms}\n"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=str, help="Override BACKTEST_START (e.g. for OOS)")
    parser.add_argument("--end", type=str, help="Override BACKTEST_END (e.g. for OOS)")
    args = parser.parse_args()

    t0 = time.time()
    try:
        metrics = run_evaluation(start=args.start, end=args.end)
    except Exception:
        traceback.print_exc()
        print("val_sharpe=FAIL")
        sys.exit(1)

    elapsed_ms = int((time.time() - t0) * 1000)
    append_result(metrics, elapsed_ms)

    # The single metric line the autoresearch loop parses
    print(f"val_sharpe={metrics['sharpe_ratio']}")
    print(f"val_sortino={metrics['sortino_ratio']}")
    print(f"val_max_dd={metrics['max_drawdown']}")
    print(f"val_return={metrics['total_return_pct']}")
    print(f"elapsed_ms={elapsed_ms}")


if __name__ == "__main__":
    main()
