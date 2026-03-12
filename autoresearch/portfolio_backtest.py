"""
autoresearch/portfolio_backtest.py — Combine sector strategies into a portfolio backtest.

Runs each sector's backtest, collects daily returns, weights them, and computes
portfolio-level Sharpe, Sortino, max DD, and total return.

Usage:
    poetry run python -m autoresearch.portfolio_backtest
    poetry run python -m autoresearch.portfolio_backtest --weights sharpe
    poetry run python -m autoresearch.portfolio_backtest --weights equal --exclude networking
"""

import argparse
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Sector config: (params_module, prices_path). Exclude EDA (negative) and deprecated power.
SECTOR_CONFIG = {
    "memory": ("autoresearch.params_memory", "prices_memory.json"),
    "photonics": ("autoresearch.params_photonics", "prices_photonics.json"),
    "tech": ("autoresearch.params_tech", "prices.json"),
    "equipment": ("autoresearch.params_equipment", "prices_equipment.json"),
    "platform": ("autoresearch.params_platform", "prices_platform.json"),
    "foundry": ("autoresearch.params_foundry", "prices_foundry.json"),
    "power_infra": ("autoresearch.params_power_infra", "prices_power_infra.json"),
    "energy": ("autoresearch.params_energy", "prices_energy.json"),
    "networking": ("autoresearch.params_networking", "prices_networking.json"),
    "tokenization": ("autoresearch.params_tokenization", "prices_tokenization.json"),
    "healthcare": ("autoresearch.params_healthcare", "prices_healthcare.json"),
}

# Val Sharpe for weighting (from ARR.md). EDA excluded.
SECTOR_SHARPE = {
    "memory": 2.78,
    "photonics": 2.26,
    "tech": 2.04,
    "equipment": 1.91,
    "platform": 1.21,
    "foundry": 1.03,
    "power_infra": 1.12,
    "energy": 0.88,
    "networking": 0.67,
    "tokenization": 0.58,
    "healthcare": 0.39,
}

SECTOR_OOS_SHARPE = {
    "memory": 2.98,
    "photonics": 2.53,
    "tech": 1.38,
    "equipment": 2.39,
    "platform": 0.33,
    "foundry": 1.22,
    "power_infra": 0.68,
    "energy": 1.45,
    "networking": -0.09,
    "tokenization": 0.54,
    "healthcare": 2.71,
}

# Regime-specific weights (run refresh_oos_weights --regime to update)
SECTOR_OOS_SHARPE_BULL = {
    "memory": 3.5,
    "photonics": 2.8,
    "tech": 1.8,
    "equipment": 2.6,
    "platform": 0.5,
    "foundry": 1.5,
    "power_infra": 0.9,
    "energy": 1.2,
    "networking": 0.2,
    "tokenization": 0.8,
    "healthcare": 2.2,
}
SECTOR_OOS_SHARPE_BEAR = {
    "memory": 2.2,
    "photonics": 2.0,
    "tech": 0.8,
    "equipment": 1.8,
    "platform": 0.1,
    "foundry": 0.7,
    "power_infra": 0.4,
    "energy": 1.8,
    "networking": -0.3,
    "tokenization": 0.2,
    "healthcare": 3.2,
}


def load_params(module_name: str):
    params_mod = importlib.import_module(module_name)
    importlib.reload(params_mod)
    return params_mod


def run_sector_backtest(params_module: str, prices_path: str, start=None, end=None, cost_bps=0):
    """Run one sector backtest. Returns (portfolio_values list, metrics dict)."""
    from autoresearch.fast_backtest import FastBacktestEngine

    params = load_params(params_module)
    cache_dir = Path(__file__).resolve().parent / "cache"
    full_path = cache_dir / prices_path

    overrides = {}
    if start:
        overrides["BACKTEST_START"] = start
    if end:
        overrides["BACKTEST_END"] = end
    if cost_bps != 0:
        overrides["TRANSACTION_COST_BPS"] = cost_bps

    if overrides:
        import types
        p = types.SimpleNamespace()
        for name in dir(params):
            if not name.startswith("_"):
                setattr(p, name, getattr(params, name))
        for k, v in overrides.items():
            setattr(p, k, v)
        params = p

    engine = FastBacktestEngine(params, prices_path_override=str(full_path))
    metrics = engine.run()
    return engine.portfolio_values, metrics, engine


def portfolio_values_to_returns(pv: list) -> pd.Series:
    """Convert portfolio_values [{date, value}, ...] to daily returns Series."""
    if len(pv) < 2:
        return pd.Series(dtype=float)
    df = pd.DataFrame(pv)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    returns = df["value"].pct_change().dropna()
    return returns


def compute_portfolio_metrics(returns: pd.Series) -> dict:
    """Compute Sharpe, Sortino, max DD, total return."""
    if len(returns) < 2:
        return {"sharpe": 0.0, "sortino": 0.0, "max_dd": 0.0, "total_return_pct": 0.0}

    daily_rf = 0.0434 / 252
    excess = returns - daily_rf
    mean_ex = excess.mean()
    std_ex = excess.std()
    sharpe = float(np.sqrt(252) * mean_ex / std_ex) if std_ex > 1e-12 else 0.0

    downside = np.minimum(excess, 0)
    dd_std = float(np.sqrt(np.mean(downside ** 2)))
    sortino = float(np.sqrt(252) * mean_ex / dd_std) if dd_std > 1e-12 else 0.0

    cum = (1 + returns).cumprod()
    cummax = cum.cummax()
    drawdown = (cum - cummax) / cummax
    max_dd = float(drawdown.min() * 100)

    total_ret = (cum.iloc[-1] - 1) * 100 if len(cum) > 0 else 0.0

    return {
        "sharpe": round(sharpe, 4),
        "sortino": round(sortino, 4),
        "max_dd": round(max_dd, 2),
        "total_return_pct": round(total_ret, 2),
    }


def load_benchmark_returns(benchmark_ticker: str = "SPY", start: str | None = None, end: str | None = None) -> pd.Series | None:
    """Load benchmark daily returns from cache."""
    import json
    cache_dir = Path(__file__).resolve().parent / "cache"
    path = cache_dir / "prices_benchmark.json"
    if benchmark_ticker != "SPY":
        path = cache_dir / "prices.json"
    if not path.exists():
        return None
    with open(path) as f:
        raw = json.load(f)
    if benchmark_ticker not in raw or not raw[benchmark_ticker]:
        return None
    df = pd.DataFrame(raw[benchmark_ticker])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    ret = df["close"].pct_change().dropna()
    if start:
        ret = ret.loc[ret.index >= pd.Timestamp(start)]
    if end:
        ret = ret.loc[ret.index <= pd.Timestamp(end)]
    return ret


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", choices=["equal", "sharpe", "oos", "risk_parity", "min_vol"], default="equal",
                        help="Allocation: equal, sharpe, oos, risk_parity (inv vol), min_vol")
    parser.add_argument("--exclude", type=str, default="",
                        help="Comma-separated sectors to exclude (e.g. networking,eda)")
    parser.add_argument("--start", type=str, help="Override BACKTEST_START (OOS window)")
    parser.add_argument("--end", type=str, help="Override BACKTEST_END (OOS window)")
    parser.add_argument("--cost-bps", type=float, default=0, help="Transaction cost in bps (e.g. 10 = 0.1%%)")
    parser.add_argument("--benchmark", type=str, default="SPY", help="Benchmark ticker for alpha/beta (default SPY)")
    parser.add_argument("--no-benchmark", action="store_true", help="Disable benchmark comparison")
    args = parser.parse_args()

    exclude = {s.strip() for s in args.exclude.split(",") if s.strip()}
    sectors = [s for s in SECTOR_CONFIG if s not in exclude]

    print(f"Running portfolio backtest: {len(sectors)} sectors, weights={args.weights}")
    print("-" * 60)

    returns_by_sector = {}
    metrics_by_sector = {}

    for sector in sectors:
        mod, path = SECTOR_CONFIG[sector]
        try:
            pv, metrics, _ = run_sector_backtest(mod, path, start=args.start, end=args.end, cost_bps=args.cost_bps)
            ret = portfolio_values_to_returns(pv)
            returns_by_sector[sector] = ret
            metrics_by_sector[sector] = metrics
            print(f"  {sector:12} sharpe={metrics['sharpe_ratio']:6.2f}  return={metrics['total_return_pct']:+6.1f}%")
        except Exception as e:
            print(f"  {sector:12} SKIP: {e}")
            continue

    if not returns_by_sector:
        print("No sectors succeeded.")
        sys.exit(1)

    # Align returns on common dates
    aligned = pd.DataFrame(returns_by_sector)
    aligned = aligned.dropna(how="all").ffill().bfill().fillna(0)

    # Weights
    if args.weights == "equal":
        w = {s: 1.0 / len(returns_by_sector) for s in returns_by_sector}
    elif args.weights == "sharpe":
        sharpes = {s: max(SECTOR_SHARPE.get(s, 0), 0.01) for s in returns_by_sector}
        total = sum(sharpes.values())
        w = {s: sharpes[s] / total for s in returns_by_sector}
    elif args.weights == "oos":
        oos = {s: max(SECTOR_OOS_SHARPE.get(s, 0), 0.01) for s in returns_by_sector}
        total = sum(oos.values())
        w = {s: oos[s] / total for s in returns_by_sector}
    elif args.weights == "risk_parity":
        vols = aligned.std()
        inv_vol = {s: 1.0 / max(vols[s], 1e-8) for s in returns_by_sector if s in vols.index}
        total = sum(inv_vol.values())
        w = {s: inv_vol[s] / total for s in inv_vol}
    elif args.weights == "min_vol":
        cov = aligned.cov().fillna(0)
        sectors_list = list(aligned.columns)
        n = len(sectors_list)
        try:
            inv_cov = np.linalg.inv(cov.values + np.eye(n) * 1e-4)
            ones = np.ones(n)
            w_vec = inv_cov @ ones
            w_vec = np.maximum(w_vec, 0)
            w_vec = w_vec / w_vec.sum()
            w = {sectors_list[i]: float(w_vec[i]) for i in range(n)}
        except Exception:
            w = {s: 1.0 / len(returns_by_sector) for s in returns_by_sector}
    else:
        w = {s: 1.0 / len(returns_by_sector) for s in returns_by_sector}

    # Portfolio returns
    portfolio_ret = pd.Series(0.0, index=aligned.index)
    for s in returns_by_sector:
        portfolio_ret = portfolio_ret + w[s] * aligned[s].reindex(portfolio_ret.index).fillna(0)

    metrics = compute_portfolio_metrics(portfolio_ret)

    print("-" * 60)
    print("PORTFOLIO (combined):")
    print(f"  Sharpe:    {metrics['sharpe']:.4f}")
    print(f"  Sortino:   {metrics['sortino']:.4f}")
    print(f"  Max DD:    {metrics['max_dd']:.2f}%")
    print(f"  Return:   {metrics['total_return_pct']:+.2f}%")

    if args.benchmark and not args.no_benchmark:
        bench = load_benchmark_returns(args.benchmark, args.start, args.end)
        if bench is not None and len(portfolio_ret) > 0:
            common = portfolio_ret.index.intersection(bench.index)
            if len(common) >= 2:
                p = portfolio_ret.reindex(common).fillna(0)
                b = bench.reindex(common).fillna(0)
                cov = np.cov(p, b)
                beta = cov[0, 1] / (cov[1, 1] + 1e-12)
                alpha_ann = (p.mean() - beta * b.mean()) * 252 * 100
                bench_ret = (1 + b).prod() - 1
                port_ret_cum = (1 + p).prod() - 1
                print(f"  vs {args.benchmark}: alpha(ann)={alpha_ann:+.1f}%  beta={beta:.2f}  port={port_ret_cum*100:+.1f}%  bench={bench_ret*100:+.1f}%")
        else:
            print(f"  (No {args.benchmark} benchmark in cache. Run refresh_all_prices.sh)")

    print()
    print("Weights:", {s: f"{w[s]:.2%}" for s in sorted(w.keys())})


if __name__ == "__main__":
    main()
