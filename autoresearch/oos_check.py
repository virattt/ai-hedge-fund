"""
autoresearch/oos_check.py — Out-of-sample validation.

Runs the backtest on different date windows to check robustness.
Split: first half vs second half of the full backtest window.

Usage:
    poetry run python -m autoresearch.oos_check
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import types
import autoresearch.params as params_mod


def make_params_override(**overrides):
    """Create a params-like object with overridden attributes."""
    p = types.SimpleNamespace()
    for name in dir(params_mod):
        if not name.startswith("_"):
            setattr(p, name, getattr(params_mod, name))
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


def run_backtest(p):
    """Run backtest and return metrics."""
    from autoresearch.fast_backtest import FastBacktestEngine
    engine = FastBacktestEngine(p)
    return engine.run()


def main():
    print("=" * 60)
    print("OUT-OF-SAMPLE VALIDATION")
    print("=" * 60)

    # Full window (baseline)
    p_full = params_mod
    m_full = run_backtest(p_full)
    print(f"\nFull window (2025-01-02 → 2026-03-07):")
    print(f"  Sharpe: {m_full['sharpe_ratio']:.4f}  Sortino: {m_full['sortino_ratio']:.4f}")
    print(f"  Return: {m_full['total_return_pct']:.2f}%  Max DD: {m_full['max_drawdown']:.2f}%")

    # First half
    p_h1 = make_params_override(BACKTEST_START="2025-01-02", BACKTEST_END="2025-07-31")
    m_h1 = run_backtest(p_h1)
    print(f"\nFirst half (2025-01-02 → 2025-07-31):")
    print(f"  Sharpe: {m_h1['sharpe_ratio']:.4f}  Sortino: {m_h1['sortino_ratio']:.4f}")
    print(f"  Return: {m_h1['total_return_pct']:.2f}%  Max DD: {m_h1['max_drawdown']:.2f}%")

    # Second half (out-of-sample)
    p_h2 = make_params_override(BACKTEST_START="2025-08-01", BACKTEST_END="2026-03-07")
    m_h2 = run_backtest(p_h2)
    print(f"\nSecond half (2025-08-01 → 2026-03-07) [OOS]:")
    print(f"  Sharpe: {m_h2['sharpe_ratio']:.4f}  Sortino: {m_h2['sortino_ratio']:.4f}")
    print(f"  Return: {m_h2['total_return_pct']:.2f}%  Max DD: {m_h2['max_drawdown']:.2f}%")

    print("\n" + "=" * 60)
    sharpe_full = m_full["sharpe_ratio"]
    sharpe_oos = m_h2["sharpe_ratio"]
    if sharpe_oos >= sharpe_full * 0.8:
        print("✓ OOS holds: second-half Sharpe within 80% of full-window")
    else:
        print("⚠ OOS degradation: second-half Sharpe < 80% of full-window")
    print("=" * 60)


if __name__ == "__main__":
    main()
