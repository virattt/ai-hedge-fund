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
    poetry run python -m autoresearch.evaluate --tickers XOM,CVX,OXY,SLB,EOG --prices-path prices_energy.json  # cross-asset
    poetry run python -m autoresearch.evaluate --params autoresearch.params_equipment --tickers AMAT,ASML,LRCX,KLAC,TEL --prices-path prices_equipment.json
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

def _results_file(params_module: str | None) -> Path:
    base = Path(__file__).resolve().parent
    if params_module and "params_" in params_module:
        sector = params_module.split("params_")[-1]
        return base / f"results_{sector}.tsv"
    return base / "results.tsv"


def load_params(module_name: str = "autoresearch.params"):
    """Force-reload params module to pick up any modifications."""
    params_mod = importlib.import_module(module_name)
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


def run_evaluation(start=None, end=None, tickers=None, prices_path=None, params_module=None, cost_bps=0):
    params = load_params(params_module or "autoresearch.params")
    overrides = {}
    if start or end:
        overrides["BACKTEST_START"] = start or params.BACKTEST_START
        overrides["BACKTEST_END"] = end or params.BACKTEST_END
    if tickers:
        overrides["BACKTEST_TICKERS"] = tickers
    if cost_bps != 0:
        overrides["TRANSACTION_COST_BPS"] = cost_bps
    if overrides:
        params = make_params_override(params, **overrides)

    # If no prices_path given, check if the params module declares one
    effective_prices_path = prices_path or getattr(params, "PRICES_PATH", None)
    effective_tickers = tickers or None  # keep None so engine reads from params

    from autoresearch.fast_backtest import FastBacktestEngine
    engine = FastBacktestEngine(params, tickers_override=effective_tickers, prices_path_override=effective_prices_path)
    metrics = engine.run()
    return metrics


def append_result(metrics: dict, elapsed_ms: int, results_path: Path | None = None):
    """Append one row to results.tsv."""
    path = results_path or _results_file(None)
    header_needed = not path.exists() or path.stat().st_size == 0
    with open(path, "a") as f:
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
    parser.add_argument("--tickers", type=str, help="Override tickers (e.g. XOM,CVX,OXY,SLB,EOG for cross-asset)")
    parser.add_argument("--prices-path", type=str, help="Override prices cache (e.g. prices_energy.json)")
    parser.add_argument("--params", type=str, help="Params module to load (e.g. autoresearch.params_equipment)")
    parser.add_argument("--cost-bps", type=float, default=0, help="Transaction cost in bps (e.g. 10 = 0.1%%)")
    args = parser.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else None

    t0 = time.time()
    try:
        metrics = run_evaluation(start=args.start, end=args.end, tickers=tickers, prices_path=args.prices_path, params_module=args.params, cost_bps=args.cost_bps)
    except Exception:
        traceback.print_exc()
        print("val_sharpe=FAIL")
        sys.exit(1)

    elapsed_ms = int((time.time() - t0) * 1000)
    results_path = _results_file(args.params)
    append_result(metrics, elapsed_ms, results_path)

    # The single metric line the autoresearch loop parses
    print(f"val_sharpe={metrics['sharpe_ratio']}")
    print(f"val_sortino={metrics['sortino_ratio']}")
    print(f"val_max_dd={metrics['max_drawdown']}")
    print(f"val_return={metrics['total_return_pct']}")
    print(f"elapsed_ms={elapsed_ms}")


if __name__ == "__main__":
    main()
