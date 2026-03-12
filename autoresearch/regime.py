"""
autoresearch/regime.py — Simple regime detection for robustness.

Returns bull/bear/sideways based on recent price action. Can be used to:
- Scale down position size in bear regimes
- Adjust RSI thresholds (30/70 vs 25/75 in bear)
- Pause new longs when regime is bearish

Usage:
    from autoresearch.regime import get_regime
    regime = get_regime(prices_df, lookback=20)
    # "bull" | "bear" | "sideways"
"""

import numpy as np
import pandas as pd
from pathlib import Path


def get_regime(close_series: pd.Series, lookback: int = 20, threshold: float = 0.02) -> str:
    """
    Classify regime from recent price action.
    - bull: cumulative return > threshold
    - bear: cumulative return < -threshold
    - sideways: else
    """
    if len(close_series) < lookback:
        return "sideways"
    recent = close_series.tail(lookback)
    ret = (recent.iloc[-1] / recent.iloc[0]) - 1.0
    if ret > threshold:
        return "bull"
    if ret < -threshold:
        return "bear"
    return "sideways"


def get_regime_from_cache(benchmark_ticker: str = "SPY", lookback: int = 20) -> str:
    """
    Load benchmark from cache and return regime.
    Requires prices_benchmark.json or similar. Falls back to sideways if not found.
    """
    cache_dir = Path(__file__).resolve().parent / "cache"
    path = cache_dir / "prices.json"
    if benchmark_ticker != "SPY":
        path = cache_dir / f"prices_{benchmark_ticker.lower()}.json"
    if not path.exists():
        return "sideways"
    import json
    with open(path) as f:
        raw = json.load(f)
    if benchmark_ticker not in raw or not raw[benchmark_ticker]:
        return "sideways"
    df = pd.DataFrame(raw[benchmark_ticker])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return get_regime(df["close"], lookback=lookback)


def regime_scale(regime: str, bull_scale: float = 1.0, bear_scale: float = 0.5, sideways_scale: float = 0.75) -> float:
    """Return position scale factor for given regime."""
    return {"bull": bull_scale, "bear": bear_scale, "sideways": sideways_scale}.get(regime, sideways_scale)
