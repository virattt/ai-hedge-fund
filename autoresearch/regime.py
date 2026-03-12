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


def get_regime_with_drawdown(
    close_series: pd.Series,
    lookback: int = 20,
    return_threshold: float = 0.02,
    drawdown_threshold: float = 0.05,
) -> str:
    """
    Regime using return + drawdown. Bear if recent drawdown > drawdown_threshold
    even when return is not deeply negative (e.g. recovery from crash).
    """
    if len(close_series) < lookback:
        return "sideways"
    recent = close_series.tail(lookback)
    ret = (recent.iloc[-1] / recent.iloc[0]) - 1.0
    rolling_max = recent.expanding().max()
    drawdown = (recent / rolling_max - 1.0).min()
    if drawdown < -drawdown_threshold:
        return "bear"
    if ret > return_threshold:
        return "bull"
    if ret < -return_threshold:
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


def get_regime_for_paper_trading(
    benchmark_tickers: list[str] | None = None,
    lookback: int = 20,
    use_drawdown: bool = False,
    use_renko: bool = False,
    renko_ticker: str = "AAPL",
) -> str:
    """
    Get regime for paper trading. Tries benchmark tickers in order.
    Default: SPY (prices_benchmark.json), then AAPL (tech proxy).

    With use_renko=True, overlays Renko+BBWAS signal from renko_ticker.
    The Renko regime can override to bear if momentum is clearly bearish,
    or upgrade confidence in bull if Renko confirms.
    """
    import json
    cache_dir = Path(__file__).resolve().parent / "cache"

    base_regime = "sideways"
    for ticker in benchmark_tickers or ["SPY", "AAPL", "NVDA"]:
        path = cache_dir / "prices.json"
        if ticker == "SPY":
            path = cache_dir / "prices_benchmark.json"
        elif ticker not in ("AAPL", "NVDA"):
            path = cache_dir / f"prices_{ticker.lower()}.json"
        if not path.exists():
            continue
        with open(path) as f:
            raw = json.load(f)
        if ticker not in raw or not raw[ticker]:
            continue
        df = pd.DataFrame(raw[ticker])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        if use_drawdown:
            base_regime = get_regime_with_drawdown(df["close"], lookback=lookback)
        else:
            base_regime = get_regime(df["close"], lookback=lookback)
        break

    if not use_renko:
        return base_regime

    return renko_overlay(base_regime, renko_ticker)


def renko_overlay(base_regime: str, renko_ticker: str = "AAPL") -> str:
    """
    Overlay Renko+BBWAS on a base regime. Renko can downgrade bull→sideways
    or sideways→bear, but never upgrades bear→bull (FA-first, TA as guardrail).
    """
    try:
        from autoresearch.renko_bbwas import renko_regime
        sig = renko_regime(renko_ticker)
    except Exception:
        return base_regime

    renko_dir = sig.get("direction", "neutral")

    if base_regime == "bull" and renko_dir == "bear":
        return "sideways"
    if base_regime == "sideways" and renko_dir == "bear" and sig.get("energy") == "expanding":
        return "bear"
    return base_regime


def renko_scale_factor(ticker: str = "AAPL") -> float:
    """
    Return a Renko-derived scale factor (0.35–1.0) for position sizing.
    Can be multiplied with the base regime_scale.
    """
    try:
        from autoresearch.renko_bbwas import renko_regime
        sig = renko_regime(ticker)
        return sig.get("scale", 0.6)
    except Exception:
        return 1.0
