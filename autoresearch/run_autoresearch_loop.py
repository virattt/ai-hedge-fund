"""
Autoresearch loop: edit params → evaluate → commit/revert.
Runs one sector at a time. Uses simple heuristic tweaks (no LLM).
Schedule via cron for overnight runs.

Usage:
    poetry run python -m autoresearch.run_autoresearch_loop --sector equipment --iterations 5
    poetry run python -m autoresearch.run_autoresearch_loop --sector equipment --dry-run
"""

import argparse
import importlib
import random
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Default technical indicators to tweak for sector params (e.g. equipment, tech).
TWEAKABLE = [
    ("RSI_OVERSOLD", 25, 35, 1),
    ("RSI_OVERBOUGHT", 65, 80, 1),
    ("RSI_LOOKBACK", 12, 18, 1),
    ("EMA_SHORT", 3, 10, 1),
    ("EMA_MEDIUM", 15, 30, 1),
    ("EMA_LONG", 40, 60, 1),
]

# Sleeve-specific knobs: only factor/tier-related parameters, not core technicals.
SLEEVE_TWEAKABLE = {
    # Tastytrade AI infra sleeve (params_tastytrade_sleeve.py)
    "tastytrade_sleeve": [
        ("MIN_VALUE_SCORE", 0.0, 0.6, 0.05),
        ("MIN_QUALITY_SCORE", 0.0, 0.6, 0.05),
        ("INSIDER_NET_SELL_THRESHOLD", -0.2, 0.2, 0.05),
        ("INSIDER_SIZE_MULTIPLIER", 0.4, 1.0, 0.05),
    ],
    # Hyperliquid HIP-3 equity sleeve (params_hl_hip3_sleeve.py)
    "hl_hip3_sleeve": [
        ("MIN_VALUE_SCORE", 0.0, 0.6, 0.05),
        ("MIN_QUALITY_SCORE", 0.0, 0.6, 0.05),
        ("INSIDER_NET_SELL_THRESHOLD", -0.2, 0.2, 0.05),
        ("INSIDER_SIZE_MULTIPLIER", 0.4, 1.0, 0.05),
    ],
}


def get_param_value(mod, name: str):
    return getattr(mod, name, None)


def set_param_in_file(path: Path, name: str, value) -> bool:
    content = path.read_text()
    lines = content.splitlines()
    out = []
    found = False
    for line in lines:
        if line.strip().startswith(f"{name} ") or line.strip().startswith(f"{name}="):
            out.append(f"{name} = {value}")
            found = True
        else:
            out.append(line)
    if not found:
        return False
    path.write_text("\n".join(out) + "\n")
    return True


def run_eval(sector: str, oos: bool = False) -> float | None:
    cmd = ["poetry", "run", "python", "-m", "autoresearch.evaluate", "--params", f"autoresearch.params_{sector}"]
    if oos:
        cmd.extend(["--start", "2025-08-01", "--end", "2026-03-07"])
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if "val_sharpe=" in line or "sharpe=" in line:
            try:
                return float(line.split("=")[-1].strip())
            except ValueError:
                pass
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sector", type=str, required=True, help="Sector name (e.g. equipment, memory)")
    parser.add_argument("--iterations", type=int, default=10, help="Max iterations per run")
    parser.add_argument("--dry-run", action="store_true", help="Only run eval, no edits/commits")
    parser.add_argument("--oos", action="store_true", help="Use OOS window for eval")
    args = parser.parse_args()

    sector = args.sector
    params_path = PROJECT_ROOT / "autoresearch" / f"params_{sector}.py"
    results_path = PROJECT_ROOT / "autoresearch" / f"results_{sector}.tsv"
    if not params_path.exists():
        print(f"Params not found: {params_path}")
        return 1

    mod = importlib.import_module(f"autoresearch.params_{sector}")
    tweakables = SLEEVE_TWEAKABLE.get(sector, TWEAKABLE)
    baseline = run_eval(sector, oos=args.oos)
    if baseline is None:
        print("Baseline eval failed.")
        return 1
    print(f"Baseline Sharpe: {baseline:.4f}")

    if args.dry_run:
        return 0

    best = baseline
    for i in range(args.iterations):
        tweak = random.choice(tweakables)
        name, lo, hi, step = tweak
        val = get_param_value(mod, name)
        if val is None:
            continue
        delta = random.choice([-step, step])
        new_val = max(lo, min(hi, val + delta))
        if new_val == val:
            continue
        if not set_param_in_file(params_path, name, new_val):
            continue
        sharpe = run_eval(sector, oos=args.oos)
        if sharpe is None:
            subprocess.run(["git", "checkout", str(params_path)], cwd=PROJECT_ROOT, capture_output=True)
            mod = importlib.reload(importlib.import_module(f"autoresearch.params_{sector}"))
            continue
        if sharpe > best:
            best = sharpe
            subprocess.run(
                ["git", "add", str(params_path), str(results_path)],
                cwd=PROJECT_ROOT,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", f"autoresearch[{sector}]: {name}={new_val} sharpe={sharpe:.4f}"],
                cwd=PROJECT_ROOT,
                capture_output=True,
            )
            print(f"  Commit: {name}={new_val} sharpe={sharpe:.4f}")
        else:
            subprocess.run(["git", "checkout", str(params_path)], cwd=PROJECT_ROOT, capture_output=True)
            mod = importlib.reload(importlib.import_module(f"autoresearch.params_{sector}"))
    print(f"Best Sharpe: {best:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
