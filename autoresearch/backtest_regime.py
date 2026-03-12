"""
autoresearch/backtest_regime.py — Backtest regime and Renko overlay impact.

Runs the portfolio backtest three ways:
  1. Baseline — no regime scaling
  2. Regime only — benchmark-based bull/bear/sideways scaling
  3. Regime + Renko — benchmark + Renko+BBWAS overlay

Regime scaling simulates holding (1 - scale) in cash when bear/sideways:
  scaled_return[date] = raw_return[date] * regime_scale[date]

Usage:
    poetry run python -m autoresearch.backtest_regime
    poetry run python -m autoresearch.backtest_regime --renko-ticker NVDA
    poetry run python -m autoresearch.backtest_regime --weights oos --cost-bps 10
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from autoresearch.portfolio_backtest import (
    SECTOR_CONFIG,
    SECTOR_OOS_SHARPE,
    compute_portfolio_metrics,
    load_params,
    portfolio_values_to_returns,
    run_sector_backtest,
)


def load_benchmark_ohlc(ticker: str, cache_dir: Path) -> pd.DataFrame | None:
    """Load benchmark OHLC from cache. Tries prices.json, prices_benchmark.json, prices_{ticker}.json."""
    for name in ["prices.json", "prices_benchmark.json", f"prices_{ticker.lower()}.json"]:
        path = cache_dir / name
        if not path.exists():
            continue
        with open(path) as f:
            raw = json.load(f)
        if ticker not in raw or not raw[ticker]:
            continue
        df = pd.DataFrame(raw[ticker])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        for col in ("open", "high", "low", "close"):
            if col not in df.columns:
                return None
        return df
    return None


def get_regime_scale_for_date(
    date: pd.Timestamp,
    benchmark_close: pd.Series,
    lookback: int = 20,
) -> float:
    """Regime scale for a given date using only data up to that date."""
    from autoresearch.regime import get_regime, regime_scale

    mask = benchmark_close.index <= date
    close_up_to = benchmark_close[mask].tail(lookback + 5)
    if len(close_up_to) < lookback:
        return 0.75
    regime = get_regime(close_up_to, lookback=lookback)
    return regime_scale(regime)


def get_renko_scale_for_date(
    date: pd.Timestamp,
    ohlc_df: pd.DataFrame,
    **kwargs,
) -> float:
    """Renko scale for a given date using only OHLC up to that date."""
    from autoresearch.renko_bbwas import renko_regime

    mask = ohlc_df.index <= date
    ohlc_up_to = ohlc_df[mask]
    if len(ohlc_up_to) < 30:
        return 1.0
    sig = renko_regime("_", ohlc_df=ohlc_up_to, **kwargs)
    return sig.get("scale", 1.0)


def build_regime_scale_series(
    dates: pd.DatetimeIndex,
    benchmark_ticker: str,
    renko_ticker: str | None,
    cache_dir: Path,
    lookback: int = 20,
) -> pd.Series:
    """Build regime_scale for each date. Uses benchmark for base regime; optionally Renko overlay."""
    from autoresearch.regime import get_regime, regime_scale

    bench_df = load_benchmark_ohlc(benchmark_ticker, cache_dir)
    if bench_df is None:
        return pd.Series(1.0, index=dates)

    renko_df = load_benchmark_ohlc(renko_ticker, cache_dir) if renko_ticker else None

    scales = []
    for date in dates:
        mask = bench_df.index <= date
        close_up_to = bench_df["close"][mask].tail(lookback + 5)
        if len(close_up_to) < lookback:
            base_scale = 0.75
        else:
            regime = get_regime(close_up_to, lookback=lookback)
            base_scale = regime_scale(regime)

        if renko_ticker and renko_df is not None:
            mask_r = renko_df.index <= date
            ohlc_up_to = renko_df[mask_r]
            if len(ohlc_up_to) >= 30:
                from autoresearch.renko_bbwas import renko_regime

                sig = renko_regime(renko_ticker, ohlc_df=ohlc_up_to)
                renko_sf = sig.get("scale", 1.0)
                base_scale *= renko_sf

        scales.append(base_scale)

    return pd.Series(scales, index=dates)


def main():
    parser = argparse.ArgumentParser(description="Backtest regime and Renko overlay impact")
    parser.add_argument("--weights", choices=["equal", "oos"], default="oos")
    parser.add_argument("--exclude", type=str, default="")
    parser.add_argument("--start", type=str, help="Override BACKTEST_START")
    parser.add_argument("--end", type=str, help="Override BACKTEST_END")
    parser.add_argument("--cost-bps", type=float, default=0)
    parser.add_argument("--benchmark", type=str, default="AAPL",
                        help="Benchmark for regime (SPY or AAPL; SPY needs prices_benchmark.json)")
    parser.add_argument("--renko-ticker", type=str, default="AAPL",
                        help="Ticker for Renko overlay (default AAPL)")
    args = parser.parse_args()

    cache_dir = Path(__file__).resolve().parent / "cache"
    exclude = {s.strip() for s in args.exclude.split(",") if s.strip()}
    sectors = [s for s in SECTOR_CONFIG if s not in exclude]

    print("Backtest regime impact: baseline vs regime vs regime+Renko")
    print(f"  Sectors: {len(sectors)}, weights={args.weights}, benchmark={args.benchmark}")
    print("-" * 70)

    returns_by_sector = {}
    for sector in sectors:
        mod, path = SECTOR_CONFIG[sector]
        try:
            pv, metrics, _ = run_sector_backtest(mod, path, start=args.start, end=args.end, cost_bps=args.cost_bps)
            ret = portfolio_values_to_returns(pv)
            returns_by_sector[sector] = ret
        except Exception as e:
            print(f"  {sector}: SKIP {e}")
            continue

    if not returns_by_sector:
        print("No sectors succeeded.")
        sys.exit(1)

    aligned = pd.DataFrame(returns_by_sector).dropna(how="all").ffill().bfill().fillna(0)
    oos = {s: max(SECTOR_OOS_SHARPE.get(s, 0), 0.01) for s in returns_by_sector}
    total = sum(oos.values())
    w = {s: oos[s] / total for s in returns_by_sector}

    portfolio_ret = pd.Series(0.0, index=aligned.index)
    for s in returns_by_sector:
        portfolio_ret = portfolio_ret + w[s] * aligned[s].reindex(portfolio_ret.index).fillna(0)

    dates = portfolio_ret.index

    regime_scale_baseline = pd.Series(1.0, index=dates)
    regime_scale_regime = build_regime_scale_series(dates, args.benchmark, None, cache_dir)
    regime_scale_renko = build_regime_scale_series(dates, args.benchmark, args.renko_ticker, cache_dir)

    ret_baseline = portfolio_ret
    ret_regime = portfolio_ret * regime_scale_regime.reindex(dates).fillna(1.0)
    ret_renko = portfolio_ret * regime_scale_renko.reindex(dates).fillna(1.0)

    m0 = compute_portfolio_metrics(ret_baseline)
    m1 = compute_portfolio_metrics(ret_regime)
    m2 = compute_portfolio_metrics(ret_renko)

    print(f"{'Variant':<22} {'Sharpe':>8} {'Sortino':>8} {'Max DD %':>10} {'Return %':>10}")
    print("-" * 70)
    print(f"{'Baseline (no regime)':<22} {m0['sharpe']:>8.4f} {m0['sortino']:>8.4f} {m0['max_dd']:>10.2f} {m0['total_return_pct']:>+10.2f}")
    print(f"{'Regime only':<22} {m1['sharpe']:>8.4f} {m1['sortino']:>8.4f} {m1['max_dd']:>10.2f} {m1['total_return_pct']:>+10.2f}")
    print(f"{'Regime + Renko':<22} {m2['sharpe']:>8.4f} {m2['sortino']:>8.4f} {m2['max_dd']:>10.2f} {m2['total_return_pct']:>+10.2f}")

    print("-" * 70)
    dd_improve = m2["max_dd"] - m0["max_dd"]
    sharpe_delta = m2["sharpe"] - m0["sharpe"]
    ret_delta = m2["total_return_pct"] - m0["total_return_pct"]
    print(f"Regime+Renko vs baseline: Sharpe {sharpe_delta:+.4f}  Max DD {dd_improve:+.2f}%  Return {ret_delta:+.2f}%")
    if m0["max_dd"] != 0:
        dd_pct = 100 * (m2["max_dd"] - m0["max_dd"]) / abs(m0["max_dd"])
        print(f"  (Max DD change: {dd_pct:+.1f}%)")


if __name__ == "__main__":
    main()
