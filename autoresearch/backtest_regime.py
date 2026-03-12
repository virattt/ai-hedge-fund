"""
autoresearch/backtest_regime.py — Regime / Renko backtest and walk-forward optimizer.

Compares:
  1) Baseline         (no scaling)
  2) Regime only      (benchmark bull/bear/sideways scaling)
  3) Regime + Renko   (benchmark * Renko scale)

Adds realism:
  - execution lag (default 1 day)
  - turnover/slippage cost model
  - hysteresis state machine (confirm + min-hold to reduce whipsaw)

Also supports walk-forward parameter search for Renko settings.
"""

from __future__ import annotations

import argparse
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


def build_regime_scale_series(
    dates: pd.DatetimeIndex,
    benchmark_ticker: str,
    renko_ticker: str | None,
    cache_dir: Path,
    lookback: int = 20,
    trend_threshold: float = 0.3,
    atr_mult_fast: float = 1.0,
    atr_mult_slow: float = 2.0,
    use_mtf: bool = True,
    require_mtf_agreement: bool = True,
) -> pd.Series:
    """
    Build daily scale series using:
      base regime scale from benchmark
      optional Renko overlay from renko_ticker
    """
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
                from autoresearch.renko_bbwas import renko_regime, renko_regime_mtf

                if use_mtf:
                    sig = renko_regime_mtf(
                        renko_ticker,
                        atr_mult_fast=atr_mult_fast,
                        atr_mult_slow=atr_mult_slow,
                        require_agreement=require_mtf_agreement,
                        ohlc_df=ohlc_up_to,
                        trend_threshold=trend_threshold,
                    )
                else:
                    sig = renko_regime(
                        renko_ticker,
                        ohlc_df=ohlc_up_to,
                        atr_mult=atr_mult_fast,
                        trend_threshold=trend_threshold,
                    )
                renko_sf = sig.get("scale", 1.0)
                base_scale *= renko_sf

        scales.append(base_scale)

    return pd.Series(scales, index=dates)


def apply_hysteresis(
    scales: pd.Series,
    confirm_days: int = 2,
    min_hold_days: int = 5,
) -> pd.Series:
    """
    Apply a simple state machine to reduce whipsaw:
      - a new scale must persist `confirm_days` before taking effect
      - after a switch, hold at least `min_hold_days`
    """
    if scales.empty:
        return scales

    rounded = scales.round(3).copy()
    out = []
    active = float(rounded.iloc[0])
    hold = 0
    candidate = active
    candidate_count = 0

    for val in rounded.values:
        v = float(val)
        hold += 1

        if v == active:
            candidate = active
            candidate_count = 0
            out.append(active)
            continue

        if hold < min_hold_days:
            out.append(active)
            continue

        if v == candidate:
            candidate_count += 1
        else:
            candidate = v
            candidate_count = 1

        if candidate_count >= confirm_days:
            active = candidate
            hold = 0
            candidate_count = 0

        out.append(active)

    return pd.Series(out, index=scales.index)


def apply_execution_model(
    raw_returns: pd.Series,
    scale_series: pd.Series,
    execution_lag_days: int = 1,
    slippage_bps: float = 0.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Apply lag + turnover/slippage cost model.

    Returns:
      net_returns, effective_scale, trade_cost_returns
    """
    if raw_returns.empty:
        idx = raw_returns.index
        zero = pd.Series(0.0, index=idx)
        return raw_returns, zero, zero

    scale = scale_series.reindex(raw_returns.index).ffill().fillna(1.0)
    eff_scale = scale.shift(execution_lag_days).fillna(1.0)
    gross = raw_returns * eff_scale

    # Turnover = absolute exposure change.
    turnover = eff_scale.diff().abs().fillna(0.0)
    cost = turnover * (slippage_bps / 10000.0)
    net = gross - cost
    return net, eff_scale, cost


def compose_portfolio_returns(
    sectors: list[str],
    returns_by_sector: dict[str, pd.Series],
    weights: dict[str, float],
) -> pd.Series:
    aligned = pd.DataFrame(returns_by_sector).dropna(how="all").ffill().bfill().fillna(0.0)
    portfolio_ret = pd.Series(0.0, index=aligned.index)
    for s in sectors:
        if s in aligned.columns and s in weights:
            portfolio_ret = portfolio_ret + weights[s] * aligned[s].fillna(0.0)
    return portfolio_ret


def compute_weights(
    returns_by_sector: dict[str, pd.Series],
    mode: str = "oos",
) -> dict[str, float]:
    if not returns_by_sector:
        return {}
    if mode == "equal":
        n = len(returns_by_sector)
        return {s: 1.0 / n for s in returns_by_sector}
    oos = {s: max(SECTOR_OOS_SHARPE.get(s, 0), 0.01) for s in returns_by_sector}
    total = sum(oos.values())
    return {s: oos[s] / total for s in returns_by_sector}


def evaluate_config(
    portfolio_ret: pd.Series,
    cache_dir: Path,
    benchmark: str,
    renko_ticker: str,
    lookback: int,
    trend_threshold: float,
    atr_mult_fast: float,
    atr_mult_slow: float,
    use_mtf: bool,
    require_mtf_agreement: bool,
    confirm_days: int,
    min_hold_days: int,
    execution_lag_days: int,
    slippage_bps: float,
) -> dict:
    dates = portfolio_ret.index
    if dates.empty:
        return {
            "metrics": compute_portfolio_metrics(portfolio_ret),
            "net_returns": portfolio_ret,
            "effective_scale": pd.Series(dtype=float),
            "cost": pd.Series(dtype=float),
            "avg_scale": 1.0,
            "turnover_annual": 0.0,
        }

    raw_scales = build_regime_scale_series(
        dates,
        benchmark_ticker=benchmark,
        renko_ticker=renko_ticker,
        cache_dir=cache_dir,
        lookback=lookback,
        trend_threshold=trend_threshold,
        atr_mult_fast=atr_mult_fast,
        atr_mult_slow=atr_mult_slow,
        use_mtf=use_mtf,
        require_mtf_agreement=require_mtf_agreement,
    )
    smooth_scales = apply_hysteresis(raw_scales, confirm_days=confirm_days, min_hold_days=min_hold_days)
    net_ret, eff_scale, cost = apply_execution_model(
        portfolio_ret,
        smooth_scales,
        execution_lag_days=execution_lag_days,
        slippage_bps=slippage_bps,
    )
    metrics = compute_portfolio_metrics(net_ret)
    turnover_annual = float(eff_scale.diff().abs().mean() * 252) if len(eff_scale) > 1 else 0.0
    avg_scale = float(eff_scale.mean()) if len(eff_scale) else 1.0
    return {
        "metrics": metrics,
        "net_returns": net_ret,
        "effective_scale": eff_scale,
        "cost": cost,
        "avg_scale": avg_scale,
        "turnover_annual": turnover_annual,
    }


def run_walk_forward(
    portfolio_ret: pd.Series,
    cache_dir: Path,
    benchmark: str,
    renko_ticker: str,
    train_days: int,
    test_days: int,
    trend_threshold_grid: list[float],
    atr_mult_fast_grid: list[float],
    atr_mult_slow_grid: list[float],
    confirm_days_grid: list[int],
    min_hold_days_grid: list[int],
    execution_lag_days: int,
    slippage_bps: float,
) -> None:
    """
    Walk-forward grid search.
    Train on one window, choose best Sharpe, evaluate on next test window.
    """
    if len(portfolio_ret) < train_days + test_days + 30:
        print("Not enough history for walk-forward.")
        return

    dates = portfolio_ret.index
    start = 0
    fold = 0
    oos_results = []

    while start + train_days + test_days <= len(dates):
        fold += 1
        tr_idx = dates[start : start + train_days]
        te_idx = dates[start + train_days : start + train_days + test_days]
        train_ret = portfolio_ret.reindex(tr_idx).dropna()
        test_ret = portfolio_ret.reindex(te_idx).dropna()

        best = None
        for thr in trend_threshold_grid:
            for amf in atr_mult_fast_grid:
                for ams in atr_mult_slow_grid:
                    for cdays in confirm_days_grid:
                        for hdays in min_hold_days_grid:
                            eval_train = evaluate_config(
                                train_ret,
                                cache_dir=cache_dir,
                                benchmark=benchmark,
                                renko_ticker=renko_ticker,
                                lookback=20,
                                trend_threshold=thr,
                                atr_mult_fast=amf,
                                atr_mult_slow=ams,
                                use_mtf=True,
                                require_mtf_agreement=True,
                                confirm_days=cdays,
                                min_hold_days=hdays,
                                execution_lag_days=execution_lag_days,
                                slippage_bps=slippage_bps,
                            )
                            score = float(eval_train["metrics"]["sharpe"])
                            if best is None or score > best["score"]:
                                best = {
                                    "score": score,
                                    "trend_threshold": thr,
                                    "atr_mult_fast": amf,
                                    "atr_mult_slow": ams,
                                    "confirm_days": cdays,
                                    "min_hold_days": hdays,
                                }

        eval_test = evaluate_config(
            test_ret,
            cache_dir=cache_dir,
            benchmark=benchmark,
            renko_ticker=renko_ticker,
            lookback=20,
            trend_threshold=float(best["trend_threshold"]),
            atr_mult_fast=float(best["atr_mult_fast"]),
            atr_mult_slow=float(best["atr_mult_slow"]),
            use_mtf=True,
            require_mtf_agreement=True,
            confirm_days=int(best["confirm_days"]),
            min_hold_days=int(best["min_hold_days"]),
            execution_lag_days=execution_lag_days,
            slippage_bps=slippage_bps,
        )
        m = eval_test["metrics"]
        oos_results.append(m)
        print(
            f"Fold {fold:02d} train={tr_idx[0].date()}..{tr_idx[-1].date()} "
            f"test={te_idx[0].date()}..{te_idx[-1].date()}  "
            f"params(thr={best['trend_threshold']}, fast={best['atr_mult_fast']}, "
            f"slow={best['atr_mult_slow']}, c={best['confirm_days']}, hold={best['min_hold_days']})  "
            f"OOS Sharpe={m['sharpe']:.3f} DD={m['max_dd']:.2f}% Ret={m['total_return_pct']:+.2f}%"
        )
        start += test_days

    if oos_results:
        avg_sh = float(np.mean([r["sharpe"] for r in oos_results]))
        avg_dd = float(np.mean([r["max_dd"] for r in oos_results]))
        avg_ret = float(np.mean([r["total_return_pct"] for r in oos_results]))
        print("-" * 90)
        print(f"Walk-forward OOS avg: Sharpe={avg_sh:.3f}  Max DD={avg_dd:.2f}%  Return={avg_ret:+.2f}%")


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
    parser.add_argument("--trend-threshold", type=float, default=0.3)
    parser.add_argument("--atr-mult-fast", type=float, default=1.0)
    parser.add_argument("--atr-mult-slow", type=float, default=2.0)
    parser.add_argument("--no-mtf", action="store_true", help="Disable multi-timeframe Renko confirmation")
    parser.add_argument("--no-mtf-agreement", action="store_true", help="When MTF enabled, do not require agreement")
    parser.add_argument("--confirm-days", type=int, default=2, help="Hysteresis: consecutive days to confirm switch")
    parser.add_argument("--min-hold-days", type=int, default=5, help="Hysteresis: minimum days to hold state")
    parser.add_argument("--execution-lag-days", type=int, default=1, help="Signal->execution lag in business days")
    parser.add_argument("--slippage-bps", type=float, default=5.0, help="Turnover cost in bps per 1.0 notional traded")
    parser.add_argument("--walk-forward", action="store_true", help="Run walk-forward optimization mode")
    parser.add_argument("--wf-train-days", type=int, default=252)
    parser.add_argument("--wf-test-days", type=int, default=63)
    parser.add_argument("--grid-trend-threshold", type=str, default="0.25,0.30,0.35,0.40")
    parser.add_argument("--grid-atr-fast", type=str, default="1.0,1.5")
    parser.add_argument("--grid-atr-slow", type=str, default="2.0,2.5")
    parser.add_argument("--grid-confirm-days", type=str, default="1,2,3")
    parser.add_argument("--grid-min-hold-days", type=str, default="3,5,8")
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

    w = compute_weights(returns_by_sector, mode=args.weights)
    portfolio_ret = compose_portfolio_returns(sectors, returns_by_sector, w)

    if args.walk_forward:
        trend_grid = [float(x.strip()) for x in args.grid_trend_threshold.split(",") if x.strip()]
        fast_grid = [float(x.strip()) for x in args.grid_atr_fast.split(",") if x.strip()]
        slow_grid = [float(x.strip()) for x in args.grid_atr_slow.split(",") if x.strip()]
        conf_grid = [int(x.strip()) for x in args.grid_confirm_days.split(",") if x.strip()]
        hold_grid = [int(x.strip()) for x in args.grid_min_hold_days.split(",") if x.strip()]
        run_walk_forward(
            portfolio_ret=portfolio_ret,
            cache_dir=cache_dir,
            benchmark=args.benchmark,
            renko_ticker=args.renko_ticker,
            train_days=args.wf_train_days,
            test_days=args.wf_test_days,
            trend_threshold_grid=trend_grid,
            atr_mult_fast_grid=fast_grid,
            atr_mult_slow_grid=slow_grid,
            confirm_days_grid=conf_grid,
            min_hold_days_grid=hold_grid,
            execution_lag_days=args.execution_lag_days,
            slippage_bps=args.slippage_bps,
        )
        return

    base_eval = evaluate_config(
        portfolio_ret=portfolio_ret,
        cache_dir=cache_dir,
        benchmark=args.benchmark,
        renko_ticker=None,
        lookback=20,
        trend_threshold=args.trend_threshold,
        atr_mult_fast=args.atr_mult_fast,
        atr_mult_slow=args.atr_mult_slow,
        use_mtf=not args.no_mtf,
        require_mtf_agreement=not args.no_mtf_agreement,
        confirm_days=args.confirm_days,
        min_hold_days=args.min_hold_days,
        execution_lag_days=args.execution_lag_days,
        slippage_bps=args.slippage_bps,
    )
    renko_eval = evaluate_config(
        portfolio_ret=portfolio_ret,
        cache_dir=cache_dir,
        benchmark=args.benchmark,
        renko_ticker=args.renko_ticker,
        lookback=20,
        trend_threshold=args.trend_threshold,
        atr_mult_fast=args.atr_mult_fast,
        atr_mult_slow=args.atr_mult_slow,
        use_mtf=not args.no_mtf,
        require_mtf_agreement=not args.no_mtf_agreement,
        confirm_days=args.confirm_days,
        min_hold_days=args.min_hold_days,
        execution_lag_days=args.execution_lag_days,
        slippage_bps=args.slippage_bps,
    )
    # Baseline: no regime scaling, still apply execution lag/slippage for apples-to-apples.
    baseline_net, baseline_eff_scale, baseline_cost = apply_execution_model(
        portfolio_ret,
        pd.Series(1.0, index=portfolio_ret.index),
        execution_lag_days=args.execution_lag_days,
        slippage_bps=args.slippage_bps,
    )
    m0 = compute_portfolio_metrics(baseline_net)
    m1 = base_eval["metrics"]
    m2 = renko_eval["metrics"]

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
    print(
        f"Exposure/turnover: regime+Renko avg scale={renko_eval['avg_scale']:.2f}, "
        f"annual turnover={renko_eval['turnover_annual']:.2f}x, "
        f"cost drag={(renko_eval['cost'].sum() * 100):.2f}%"
    )


if __name__ == "__main__":
    main()
