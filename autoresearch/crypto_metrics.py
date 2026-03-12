"""
autoresearch/crypto_metrics.py

Extended risk and performance metrics for crypto strategies:
- Ulcer Index + Ulcer Performance Index
- VaR(95/99), CVaR(95/99)
- Skew / Kurtosis
- Regime Hit Rate (direction vs next 5/10d return sign)
- Turnover-adjusted alpha
- Capture Ratios vs benchmark (BTC)
- Rolling stability (60/90d Sharpe, DD, hit rate)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_calmar_tuw(returns: pd.Series) -> dict:
    """Calmar (CAGR/|MaxDD|) and Time Under Water (% days below prior high)."""
    if len(returns) < 2:
        return {"calmar": 0.0, "tuw_pct": 0.0}

    n = len(returns)
    cum = (1 + returns).cumprod()
    cummax = cum.cummax()
    max_dd = float((cum - cummax).min() / cummax.max()) if cummax.max() > 1e-12 else 0.0
    total_ret = float(cum.iloc[-1] - 1) if len(cum) > 0 else 0.0
    years = n / 252.0
    cagr = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0.0
    calmar = float(cagr / abs(max_dd)) if max_dd != 0 else 0.0
    under_water = (cum < cummax).sum()
    tuw_pct = float(under_water / n * 100) if n > 0 else 0.0
    return {"calmar": round(calmar, 4), "tuw_pct": round(tuw_pct, 2)}


def compute_ulcer_metrics(returns: pd.Series) -> dict:
    """
    Ulcer Index: sqrt(mean of squared % drawdowns from running high).
    Ulcer Perf Index: (CAGR - rf) / Ulcer, annualized.
    """
    if len(returns) < 2:
        return {"ulcer_index": 0.0, "ulcer_perf_index": 0.0}

    cum = (1 + returns).cumprod()
    cummax = cum.cummax()
    dd_pct = (cum - cummax) / cummax.replace(0, np.nan).fillna(1.0)
    dd_sq = (dd_pct ** 2).replace([np.inf, -np.inf], 0).fillna(0)
    ulcer = float(np.sqrt(dd_sq.mean()) * 100) if dd_sq.mean() > 0 else 0.0

    n = len(returns)
    total_ret = float(cum.iloc[-1] - 1) if len(cum) > 0 else 0.0
    years = n / 252.0
    cagr = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0.0
    rf = 0.0434  # annual
    ulcer_perf = (cagr - rf / 100) / (ulcer / 100) if ulcer > 1e-6 else 0.0

    return {
        "ulcer_index": round(ulcer, 2),
        "ulcer_perf_index": round(float(ulcer_perf), 4),
    }


def compute_var_cvar(returns: pd.Series) -> dict:
    """VaR(95), VaR(99), CVaR(95), CVaR(99) in percent."""
    if len(returns) < 2:
        return {"var95_pct": 0.0, "var99_pct": 0.0, "cvar95_pct": 0.0, "cvar99_pct": 0.0}

    arr = np.sort(returns.values)
    n = len(arr)

    # VaR: percentile loss (e.g. 5th percentile = worst 5%)
    var95 = float(np.percentile(arr, 5) * 100) if n > 0 else 0.0
    var99 = float(np.percentile(arr, 1) * 100) if n > 0 else 0.0

    # CVaR: mean of worst 5% and 1%
    worst_5pct = max(1, int(n * 0.05))
    worst_1pct = max(1, int(n * 0.01))
    cvar95 = float(np.mean(arr[:worst_5pct]) * 100) if worst_5pct > 0 else 0.0
    cvar99 = float(np.mean(arr[:worst_1pct]) * 100) if worst_1pct > 0 else 0.0

    return {
        "var95_pct": round(var95, 2),
        "var99_pct": round(var99, 2),
        "cvar95_pct": round(cvar95, 2),
        "cvar99_pct": round(cvar99, 2),
    }


def compute_skew_kurtosis(returns: pd.Series) -> dict:
    """Skewness and excess kurtosis of daily returns."""
    if len(returns) < 3:
        return {"skew": 0.0, "kurtosis": 0.0}

    arr = returns.dropna().values
    if len(arr) < 3:
        return {"skew": 0.0, "kurtosis": 0.0}

    mean = np.mean(arr)
    std = np.std(arr)
    if std < 1e-12:
        return {"skew": 0.0, "kurtosis": 0.0}

    n = len(arr)
    skew = float(np.mean(((arr - mean) / std) ** 3))
    # Excess kurtosis (normal = 0)
    kurt = float(np.mean(((arr - mean) / std) ** 4) - 3.0)

    return {"skew": round(skew, 4), "kurtosis": round(kurt, 4)}


def compute_regime_hit_rate(
    direction: pd.Series,
    forward_ret_5d: pd.Series,
    forward_ret_10d: pd.Series,
) -> dict:
    """
    % of days where model direction matches next 5/10-day return sign.
    direction: 'bull' | 'bear' | 'neutral'
    Excludes neutral from denominator for cleaner signal.
    """
    common = direction.index.intersection(forward_ret_5d.index).intersection(forward_ret_10d.index)
    if len(common) == 0:
        return {"hit_rate_5d": 0.0, "hit_rate_10d": 0.0, "hit_rate_5d_n": 0, "hit_rate_10d_n": 0}

    d = direction.reindex(common).ffill().fillna("neutral")
    f5 = forward_ret_5d.reindex(common).dropna()
    f10 = forward_ret_10d.reindex(common).dropna()

    # Align: direction at t, forward return from t+1
    # forward_ret is already the return over next 5/10 days, indexed by start date
    def hit_rate(dir_ser: pd.Series, fwd_ser: pd.Series) -> tuple[float, int]:
        idx = dir_ser.index.intersection(fwd_ser.index)
        idx = idx[dir_ser.loc[idx] != "neutral"]
        if len(idx) == 0:
            return 0.0, 0
        d_sub = dir_ser.loc[idx]
        f_sub = fwd_ser.loc[idx]
        sign_match = ((d_sub == "bull") & (f_sub > 0)) | ((d_sub == "bear") & (f_sub < 0))
        return float(sign_match.mean() * 100), len(idx)

    hr5, n5 = hit_rate(d, f5)
    hr10, n10 = hit_rate(d, f10)

    return {
        "hit_rate_5d": round(hr5, 2),
        "hit_rate_10d": round(hr10, 2),
        "hit_rate_5d_n": n5,
        "hit_rate_10d_n": n10,
    }


def compute_turnover_adjusted_alpha(
    total_return_pct: float,
    cost_drag_pct: float,
    turnover_annual: float,
) -> float:
    """Return net of costs per unit turnover. Higher = more efficient."""
    if turnover_annual < 1e-6:
        return 0.0
    net_ret = total_return_pct - cost_drag_pct
    return net_ret / turnover_annual


def compute_capture_ratios(port_returns: pd.Series, bench_returns: pd.Series) -> dict:
    """
    Up-capture: portfolio mean return when benchmark > 0 / benchmark mean when benchmark > 0.
    Down-capture: portfolio mean when benchmark < 0 / benchmark mean when benchmark < 0.
    """
    common = port_returns.index.intersection(bench_returns.index)
    if len(common) < 2:
        return {"up_capture": 0.0, "down_capture": 0.0}

    pr = port_returns.reindex(common).dropna()
    br = bench_returns.reindex(common).dropna()
    common = pr.index.intersection(br.index)
    pr = pr.loc[common]
    br = br.loc[common]

    up_mask = br > 0
    down_mask = br < 0
    bench_up_mean = br[up_mask].mean()
    bench_down_mean = br[down_mask].mean()

    if up_mask.sum() > 0 and abs(bench_up_mean) > 1e-12:
        port_up_mean = pr[up_mask].mean()
        up_capture = float(port_up_mean / bench_up_mean * 100)
    else:
        up_capture = 0.0

    if down_mask.sum() > 0 and abs(bench_down_mean) > 1e-12:
        port_down_mean = pr[down_mask].mean()
        down_capture = float(port_down_mean / bench_down_mean * 100)
    else:
        down_capture = 0.0

    return {
        "up_capture": round(up_capture, 2),
        "down_capture": round(down_capture, 2),
    }


def compute_rolling_stability(returns: pd.Series, windows: tuple[int, ...] = (60, 90)) -> dict:
    """
    Rolling Sharpe, Max DD, hit rate over 60d and 90d windows.
    Reports mean, std, min of rolling metrics.
    """
    daily_rf = 0.0434 / 252
    out = {}

    for w in windows:
        if len(returns) < w:
            out[f"roll{w}_sharpe_mean"] = 0.0
            out[f"roll{w}_sharpe_std"] = 0.0
            out[f"roll{w}_sharpe_min"] = 0.0
            out[f"roll{w}_dd_mean"] = 0.0
            out[f"roll{w}_dd_min"] = 0.0
            out[f"roll{w}_hit_mean"] = 0.0
            continue

        sharpes = []
        dds = []
        hits = []

        for i in range(w, len(returns) + 1):
            window = returns.iloc[i - w : i]
            excess = window - daily_rf
            std = excess.std()
            sharpe = float(np.sqrt(252) * excess.mean() / std) if std > 1e-12 else 0.0
            sharpes.append(sharpe)

            cum = (1 + window).cumprod()
            dd = float((cum / cum.cummax() - 1).min() * 100) if len(cum) > 0 else 0.0
            dds.append(dd)

            hit = (window > 0).mean() * 100
            hits.append(hit)

        sharpes = np.array(sharpes)
        dds = np.array(dds)
        hits = np.array(hits)

        out[f"roll{w}_sharpe_mean"] = round(float(np.mean(sharpes)), 4)
        out[f"roll{w}_sharpe_std"] = round(float(np.std(sharpes)), 4)
        out[f"roll{w}_sharpe_min"] = round(float(np.min(sharpes)), 4)
        out[f"roll{w}_dd_mean"] = round(float(np.mean(dds)), 2)
        out[f"roll{w}_dd_min"] = round(float(np.min(dds)), 2)
        out[f"roll{w}_hit_mean"] = round(float(np.mean(hits)), 2)

    return out


def compute_all_crypto_metrics(
    returns: pd.Series,
    benchmark_returns: pd.Series | None = None,
    direction: pd.Series | None = None,
    forward_ret_5d: pd.Series | None = None,
    forward_ret_10d: pd.Series | None = None,
    total_return_pct: float | None = None,
    cost_drag_pct: float | None = None,
    turnover_annual: float | None = None,
) -> dict:
    """
    Aggregate all crypto metrics. Pass optional series for regime hit rate,
    capture ratios, and turnover-adjusted alpha.
    """
    metrics = {}

    # Always compute from returns
    metrics.update(compute_calmar_tuw(returns))
    metrics.update(compute_ulcer_metrics(returns))
    metrics.update(compute_var_cvar(returns))
    metrics.update(compute_skew_kurtosis(returns))
    metrics.update(compute_rolling_stability(returns))

    if benchmark_returns is not None:
        metrics.update(compute_capture_ratios(returns, benchmark_returns))

    if direction is not None and forward_ret_5d is not None and forward_ret_10d is not None:
        metrics.update(compute_regime_hit_rate(direction, forward_ret_5d, forward_ret_10d))

    if total_return_pct is not None and cost_drag_pct is not None and turnover_annual is not None:
        metrics["turnover_adj_alpha"] = round(
            compute_turnover_adjusted_alpha(total_return_pct, cost_drag_pct, turnover_annual), 4
        )

    return metrics
