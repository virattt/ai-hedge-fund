"""
autoresearch/backtest_crypto_rotation.py

Directly answer "swap SOL for HYPE?" with crypto-native tests:

1) Buy & Hold SOL
2) Buy & Hold HYPE
3) Static 50/50 SOL/HYPE
4) Renko-timed SOL (SOL vs cash)
5) Renko-timed HYPE (HYPE vs cash)
6) Renko relative-strength rotation (HYPE/SOL ratio signal)

Rotation logic uses Renko MTF on ratio OHLC:
- bull  -> tilt toward HYPE
- bear  -> tilt toward SOL
- neutral -> stay near 50/50

Includes:
- execution lag (default 1 day)
- turnover/slippage cost model
- hysteresis (confirm + min-hold)
- optional 200-day MA risk guardrail
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

from autoresearch.crypto_metrics import compute_all_crypto_metrics
from autoresearch.portfolio_backtest import compute_portfolio_metrics
from autoresearch.renko_bbwas import renko_regime_mtf

CACHE_DIR = Path(__file__).resolve().parent / "cache"


def load_btc_returns() -> pd.Series | None:
    """Load BTC daily returns for capture-ratio benchmark."""
    try:
        btc = load_ohlc_from_cache("BTC")
        return btc["close"].pct_change().dropna()
    except (FileNotFoundError, ValueError):
        return None


def load_ohlc_from_cache(ticker: str) -> pd.DataFrame:
    path = CACHE_DIR / f"prices_{ticker.lower()}.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing cache file: {path}")
    with open(path) as f:
        raw = json.load(f)
    if ticker not in raw or not raw[ticker]:
        raise ValueError(f"No data for {ticker} in {path}")
    df = pd.DataFrame(raw[ticker])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    needed = {"open", "high", "low", "close", "volume"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"{ticker} missing OHLCV columns: {missing}")
    return df


def align_close_returns(sol_df: pd.DataFrame, hype_df: pd.DataFrame) -> pd.DataFrame:
    close = pd.DataFrame(
        {
            "SOL": sol_df["close"],
            "HYPE": hype_df["close"],
        }
    ).dropna()
    rets = close.pct_change().dropna()
    return rets


def ma200_flag(close: pd.Series) -> pd.Series:
    """True when close is above 200-day simple moving average."""
    ma = close.rolling(200, min_periods=200).mean()
    return (close > ma).fillna(False)


def build_ratio_ohlc(numer_df: pd.DataFrame, denom_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build synthetic ratio OHLC for numer/denom.
    """
    common = numer_df.index.intersection(denom_df.index)
    a = numer_df.loc[common]
    b = denom_df.loc[common]
    ratio = pd.DataFrame(index=common)
    ratio["open"] = a["open"] / b["open"]
    ratio["high"] = a["high"] / b["low"].replace(0, pd.NA)
    ratio["low"] = a["low"] / b["high"].replace(0, pd.NA)
    ratio["close"] = a["close"] / b["close"].replace(0, pd.NA)
    ratio["volume"] = a["volume"]
    ratio = ratio.dropna()
    return ratio


def smooth_direction(raw_direction: pd.Series, confirm_days: int, min_hold_days: int) -> pd.Series:
    """
    Hysteresis on categorical direction series.
    """
    if raw_direction.empty:
        return raw_direction
    active = raw_direction.iloc[0]
    candidate = active
    candidate_count = 0
    hold = 0
    out = []
    for v in raw_direction.values:
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
    return pd.Series(out, index=raw_direction.index)


def _forward_returns(series: pd.Series, days: int) -> pd.Series:
    """Forward N-day total return, indexed by start date."""
    cum = (1 + series).cumprod()
    fwd = cum.shift(-days) / cum - 1
    return fwd.dropna()


def apply_costs_and_lag(
    port_ret: pd.Series,
    weight_hype: pd.Series,
    lag: int,
    slippage_bps: float,
    *,
    benchmark_returns: pd.Series | None = None,
    direction: pd.Series | None = None,
    forward_ret_5d: pd.Series | None = None,
    forward_ret_10d: pd.Series | None = None,
) -> dict:
    """Apply execution lag and turnover costs. Optionally enrich with crypto metrics."""
    w = weight_hype.reindex(port_ret.index).ffill().fillna(0.5)
    w_eff = w.shift(lag).fillna(w.iloc[0] if len(w) else 0.5)
    turnover = w_eff.diff().abs().fillna(0.0)
    cost = turnover * (slippage_bps / 10000.0)
    net = port_ret - cost
    metrics = compute_portfolio_metrics(net)
    turnover_annual = float(turnover.mean() * 252) if len(turnover) > 1 else 0.0
    cost_drag_pct = float(cost.sum() * 100)
    total_return_pct = metrics["total_return_pct"]

    extra = compute_all_crypto_metrics(
        net,
        benchmark_returns=benchmark_returns,
        direction=direction,
        forward_ret_5d=forward_ret_5d,
        forward_ret_10d=forward_ret_10d,
        total_return_pct=total_return_pct,
        cost_drag_pct=cost_drag_pct,
        turnover_annual=turnover_annual,
    )
    metrics.update(extra)

    return {
        "returns": net,
        "metrics": metrics,
        "weight_hype": w_eff,
        "turnover_annual": turnover_annual,
        "cost_drag_pct": cost_drag_pct,
        "avg_weight_hype": float(w_eff.mean()) if len(w_eff) else 0.0,
    }


def run_ratio_rotation(
    sol_df: pd.DataFrame,
    hype_df: pd.DataFrame,
    atr_mult_fast: float,
    atr_mult_slow: float,
    confirm_days: int,
    min_hold_days: int,
    lag: int,
    slippage_bps: float,
    use_200dma_filter: bool = False,
    benchmark_returns: pd.Series | None = None,
) -> dict:
    ratio_ohlc = build_ratio_ohlc(hype_df, sol_df)  # HYPE/SOL
    rets = align_close_returns(sol_df, hype_df)
    dates = rets.index.intersection(ratio_ohlc.index)
    rets = rets.loc[dates]
    ratio_ohlc = ratio_ohlc.loc[dates]
    ratio_ret = ratio_ohlc["close"].pct_change().dropna()

    dirs = []
    confs = []
    for d in dates:
        sig = renko_regime_mtf(
            ticker="HYPE/SOL",
            atr_mult_fast=atr_mult_fast,
            atr_mult_slow=atr_mult_slow,
            require_agreement=True,
            ohlc_df=ratio_ohlc.loc[:d],
        )
        dirs.append(sig.get("direction", "neutral"))
        confs.append(float(sig.get("confidence", 0.5)))

    raw_dir = pd.Series(dirs, index=dates)
    conf = pd.Series(confs, index=dates).clip(lower=0.0, upper=1.0)
    smooth_dir = smooth_direction(raw_dir, confirm_days=confirm_days, min_hold_days=min_hold_days)

    fwd_5 = _forward_returns(ratio_ret, 5)
    fwd_10 = _forward_returns(ratio_ret, 10)

    # Map direction+confidence to weights:
    # neutral=50/50, bull tilts to HYPE up to 90/10, bear tilts to SOL up to 10/90.
    w_hype = pd.Series(0.5, index=dates)
    tilt = 0.4 * conf  # max +/- 40%
    w_hype[smooth_dir == "bull"] = 0.5 + tilt[smooth_dir == "bull"]
    w_hype[smooth_dir == "bear"] = 0.5 - tilt[smooth_dir == "bear"]
    w_hype = w_hype.clip(lower=0.1, upper=0.9)

    exposure = pd.Series(1.0, index=dates)
    if use_200dma_filter:
        sol_above = ma200_flag(sol_df["close"]).reindex(dates).fillna(False)
        hype_above = ma200_flag(hype_df["close"]).reindex(dates).fillna(False)
        # Reallocate toward the asset that is above 200DMA, and de-risk if both are below.
        w_hype = w_hype.copy()
        w_hype[(~hype_above) & sol_above] = w_hype[(~hype_above) & sol_above].clip(upper=0.25)
        w_hype[hype_above & (~sol_above)] = w_hype[hype_above & (~sol_above)].clip(lower=0.75)
        exposure[(~hype_above) & (~sol_above)] = 0.40
        exposure[(hype_above ^ sol_above)] = 0.90
        exposure[hype_above & sol_above] = 1.00

    gross = exposure * (w_hype * rets["HYPE"] + (1.0 - w_hype) * rets["SOL"])
    out = apply_costs_and_lag(
        gross,
        w_hype,
        lag=lag,
        slippage_bps=slippage_bps,
        benchmark_returns=benchmark_returns,
        direction=smooth_dir,
        forward_ret_5d=fwd_5,
        forward_ret_10d=fwd_10,
    )
    out["name"] = "Renko Rotation (HYPE/SOL)"
    if use_200dma_filter:
        out["name"] += " + 200DMA"
    out["avg_exposure"] = float(exposure.mean()) if len(exposure) else 1.0
    return out


def run_timed_single_asset(
    asset_df: pd.DataFrame,
    asset_name: str,
    atr_mult_fast: float,
    atr_mult_slow: float,
    confirm_days: int,
    min_hold_days: int,
    lag: int,
    slippage_bps: float,
    use_200dma_filter: bool = False,
    benchmark_returns: pd.Series | None = None,
) -> dict:
    r = asset_df["close"].pct_change().dropna()
    dates = r.index
    dirs = []
    scales = []
    for d in dates:
        sig = renko_regime_mtf(
            ticker=asset_name,
            atr_mult_fast=atr_mult_fast,
            atr_mult_slow=atr_mult_slow,
            require_agreement=True,
            ohlc_df=asset_df.loc[:d],
        )
        dirs.append(sig.get("direction", "neutral"))
        scales.append(float(sig.get("scale", 0.6)))
    raw_dir = pd.Series(dirs, index=dates)
    scale = pd.Series(scales, index=dates).clip(lower=0.0, upper=1.0)
    smooth_dir = smooth_direction(raw_dir, confirm_days=confirm_days, min_hold_days=min_hold_days)

    fwd_5 = _forward_returns(r, 5)
    fwd_10 = _forward_returns(r, 10)

    # Long-only exposure model:
    # bull: hold according to scale
    # neutral: reduced hold
    # bear: defensive minimum hold
    exposure = pd.Series(0.25, index=dates)
    exposure[smooth_dir == "neutral"] = (0.5 * scale[smooth_dir == "neutral"]).clip(lower=0.2, upper=0.8)
    exposure[smooth_dir == "bull"] = scale[smooth_dir == "bull"].clip(lower=0.4, upper=1.0)
    exposure[smooth_dir == "bear"] = (0.3 * scale[smooth_dir == "bear"]).clip(lower=0.05, upper=0.4)
    if use_200dma_filter:
        above = ma200_flag(asset_df["close"]).reindex(dates).fillna(False)
        # If under 200DMA, halve risk.
        exposure = exposure.where(above, exposure * 0.5)
    gross = exposure * r
    out = apply_costs_and_lag(
        gross,
        exposure,
        lag=lag,
        slippage_bps=slippage_bps,
        benchmark_returns=benchmark_returns,
        direction=smooth_dir,
        forward_ret_5d=fwd_5,
        forward_ret_10d=fwd_10,
    )
    out["name"] = f"Renko Timed {asset_name}"
    if use_200dma_filter:
        out["name"] += " + 200DMA"
    out["avg_exposure"] = float(exposure.mean()) if len(exposure) else 1.0
    return out


def run_constant_weight_strategy(
    rets: pd.DataFrame,
    w_hype: float,
    name: str,
    lag: int,
    slippage_bps: float,
    benchmark_returns: pd.Series | None = None,
) -> dict:
    w = pd.Series(w_hype, index=rets.index)
    gross = w * rets["HYPE"] + (1.0 - w) * rets["SOL"]
    out = apply_costs_and_lag(gross, w, lag=lag, slippage_bps=slippage_bps, benchmark_returns=benchmark_returns)
    out["name"] = name
    out["avg_exposure"] = 1.0
    return out


def print_table(results: list[dict], extended: bool = False) -> None:
    """Main metrics table."""
    print(
        f"{'Strategy':<36} {'Sharpe':>8} {'Sortino':>8} {'Max DD %':>10} {'Return %':>10} "
        f"{'Calmar':>8} {'CVaR99%':>10} {'TUW%':>8} {'UpCap%':>8} {'DnCap%':>8} {'Hit5d%':>8} {'TurnAdj':>10}"
    )
    print("-" * 130)
    for r in results:
        m = r["metrics"]
        print(
            f"{r['name']:<36} "
            f"{m['sharpe']:>8.4f} {m['sortino']:>8.4f} {m['max_dd']:>10.2f} {m['total_return_pct']:>+10.2f} "
            f"{m.get('calmar', 0):>8.4f} {m.get('cvar99_pct', 0):>10.2f} {m.get('tuw_pct', 0):>8.2f} "
            f"{m.get('up_capture', 0):>8.2f} {m.get('down_capture', 0):>8.2f} "
            f"{m.get('hit_rate_5d', 0):>8.2f} {m.get('turnover_adj_alpha', 0):>10.4f}"
        )

    if extended:
        print_extended_table(results)


def print_extended_table(results: list[dict]) -> None:
    """Ulcer, VaR/CVaR, Skew, Kurtosis, Rolling stability."""
    print("\n--- Extended metrics ---")
    print(
        f"{'Strategy':<36} {'Ulcer':>8} {'Var95%':>8} {'Var99%':>8} {'Skew':>8} {'Kurt':>8} "
        f"{'R60Sharpe':>10} {'R90Sharpe':>10} {'R60Hit%':>10}"
    )
    print("-" * 120)
    for r in results:
        m = r["metrics"]
        print(
            f"{r['name']:<36} "
            f"{m.get('ulcer_index', 0):>8.2f} {m.get('var95_pct', 0):>8.2f} {m.get('var99_pct', 0):>8.2f} "
            f"{m.get('skew', 0):>8.4f} {m.get('kurtosis', 0):>8.4f} "
            f"{m.get('roll60_sharpe_mean', 0):>10.4f} {m.get('roll90_sharpe_mean', 0):>10.4f} "
            f"{m.get('roll60_hit_mean', 0):>10.2f}"
        )


def main():
    parser = argparse.ArgumentParser(description="Backtest SOL vs HYPE and Renko rotation")
    parser.add_argument("--start", type=str, default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--execution-lag-days", type=int, default=1)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--confirm-days", type=int, default=2)
    parser.add_argument("--min-hold-days", type=int, default=5)
    parser.add_argument("--atr-mult-fast", type=float, default=1.0)
    parser.add_argument("--atr-mult-slow", type=float, default=2.0)
    parser.add_argument("--use-200dma-filter", action="store_true", help="Apply 200-day MA risk guardrail")
    parser.add_argument("--extended", action="store_true", help="Print extended metrics (Ulcer, VaR, Skew, Rolling)")
    parser.add_argument("--liquidity-stress", action="store_true", help="Run slippage stress at 5/10/20/50 bps")
    args = parser.parse_args()

    sol_df = load_ohlc_from_cache("SOL")
    hype_df = load_ohlc_from_cache("HYPE")
    btc_ret = load_btc_returns()
    if btc_ret is None:
        btc_ret = None  # capture ratios will be skipped

    if args.start:
        start_ts = pd.Timestamp(args.start)
        sol_df = sol_df.loc[sol_df.index >= start_ts]
        hype_df = hype_df.loc[hype_df.index >= start_ts]
    if args.end:
        end_ts = pd.Timestamp(args.end)
        sol_df = sol_df.loc[sol_df.index <= end_ts]
        hype_df = hype_df.loc[hype_df.index <= end_ts]

    rets = align_close_returns(sol_df, hype_df)
    if btc_ret is not None:
        btc_ret = btc_ret.reindex(rets.index).dropna()
    common_start = rets.index.min().date()
    common_end = rets.index.max().date()
    print(f"Crypto rotation backtest window: {common_start} -> {common_end} ({len(rets)} trading days)")
    print(
        f"Settings: lag={args.execution_lag_days}d slippage={args.slippage_bps}bps "
        f"confirm={args.confirm_days} hold={args.min_hold_days} "
        f"atr_fast={args.atr_mult_fast} atr_slow={args.atr_mult_slow} "
        f"200dma_filter={args.use_200dma_filter}"
    )
    print("-" * 100)

    def run_all(slippage: float):
        return [
            run_constant_weight_strategy(rets, 0.0, "Buy & Hold SOL", args.execution_lag_days, slippage, benchmark_returns=btc_ret),
            run_constant_weight_strategy(rets, 1.0, "Buy & Hold HYPE", args.execution_lag_days, slippage, benchmark_returns=btc_ret),
            run_constant_weight_strategy(rets, 0.5, "Static 50/50 SOL/HYPE", args.execution_lag_days, slippage, benchmark_returns=btc_ret),
            run_timed_single_asset(sol_df, "SOL", args.atr_mult_fast, args.atr_mult_slow, args.confirm_days, args.min_hold_days, args.execution_lag_days, slippage, args.use_200dma_filter, benchmark_returns=btc_ret),
            run_timed_single_asset(hype_df, "HYPE", args.atr_mult_fast, args.atr_mult_slow, args.confirm_days, args.min_hold_days, args.execution_lag_days, slippage, args.use_200dma_filter, benchmark_returns=btc_ret),
            run_ratio_rotation(sol_df, hype_df, args.atr_mult_fast, args.atr_mult_slow, args.confirm_days, args.min_hold_days, args.execution_lag_days, slippage, args.use_200dma_filter, benchmark_returns=btc_ret),
        ]

    if args.liquidity_stress:
        print("\n=== Liquidity stress: slippage at 5, 10, 20, 50 bps ===\n")
        for bps in (5.0, 10.0, 20.0, 50.0):
            print(f"--- Slippage {bps} bps ---")
            stress_results = run_all(bps)
            for r in stress_results:
                m = r["metrics"]
                print(f"  {r['name']:<36} Sharpe={m['sharpe']:.4f} Return={m['total_return_pct']:+.2f}% CostDrag={r['cost_drag_pct']:.2f}%")
            print()
        return

    results = run_all(args.slippage_bps)
    print_table(results, extended=args.extended)

    best_sharpe = max(results, key=lambda x: x["metrics"]["sharpe"])
    best_dd = max(results, key=lambda x: x["metrics"]["max_dd"])  # less negative is better
    print("-" * 100)
    print(
        f"Best Sharpe: {best_sharpe['name']} ({best_sharpe['metrics']['sharpe']:.4f}) | "
        f"Best MaxDD: {best_dd['name']} ({best_dd['metrics']['max_dd']:.2f}%)"
    )


if __name__ == "__main__":
    main()
