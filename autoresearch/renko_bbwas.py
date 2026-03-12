"""
autoresearch/renko_bbwas.py — Renko + BBWAS momentum/regime signal.

Computes ATR-based Renko bricks from OHLC data, then layers Bollinger Band
Width with Area Squeeze (BBWAS) to classify momentum state:

  trending_bull  — green bricks dominating, bands expanding
  trending_bear  — red bricks dominating, bands expanding
  squeeze        — bands contracting, big move loading
  extended       — bands at max width, move may be exhausting
  neutral        — mixed or insufficient data

This is a timing/sizing overlay, not a replacement for fundamental analysis.
Designed for BTC regime detection but works on any OHLC series.

Usage:
    from autoresearch.renko_bbwas import renko_regime
    signal = renko_regime("AAPL")  # from cache
    # signal = {"regime": "trending_bear", "direction": "bear", "energy": "expanding",
    #           "brick_trend": -0.8, "bandwidth_pct": 0.12, "squeeze": False, "scale": 0.5}

CLI:
    poetry run python -m autoresearch.renko_bbwas
    poetry run python -m autoresearch.renko_bbwas --ticker NVDA
    poetry run python -m autoresearch.renko_bbwas --ticker AAPL --atr-period 14 --atr-mult 1.0
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent / "cache"


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range over OHLC DataFrame."""
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()


def build_renko_bricks(
    close: pd.Series,
    brick_size: float,
) -> list[dict]:
    """
    Build Renko bricks from a close price series.

    Each brick: {"start": price, "end": price, "direction": 1 or -1}
    A new brick prints only when price moves >= brick_size from the last brick's end.
    """
    if len(close) < 2 or brick_size <= 0:
        return []

    prices = close.dropna().values
    bricks = []
    anchor = prices[0]

    for price in prices[1:]:
        delta = price - anchor
        n_bricks = int(abs(delta) / brick_size)
        if n_bricks == 0:
            continue
        direction = 1 if delta > 0 else -1
        for _ in range(n_bricks):
            new_end = anchor + direction * brick_size
            bricks.append({
                "start": anchor,
                "end": new_end,
                "direction": direction,
            })
            anchor = new_end

    return bricks


def renko_trend_score(bricks: list[dict], lookback: int = 10) -> float:
    """
    Score from -1.0 (all red) to +1.0 (all green) over recent bricks.
    Uses the last `lookback` bricks.
    """
    if not bricks:
        return 0.0
    recent = bricks[-lookback:]
    return sum(b["direction"] for b in recent) / len(recent)


def compute_bbwas(
    renko_closes: np.ndarray,
    bb_period: int = 20,
    bb_std: float = 2.0,
) -> dict:
    """
    Bollinger Band Width + Squeeze detection on the Renko brick close series.

    Returns:
        bandwidth: current band width as fraction of midline
        squeeze: True if bandwidth is below its rolling 25th percentile
        expanding: True if bandwidth is increasing
        squeeze_threshold: rolling 25th percentile used for squeeze detection
        squeeze_quality: 0-1, deeper squeeze -> higher quality
        upper: upper band value
        lower: lower band value
        mid: midline (SMA)
    """
    if len(renko_closes) < bb_period:
        return {
            "bandwidth": 0.0,
            "squeeze": False,
            "expanding": False,
            "squeeze_threshold": 0.0,
            "squeeze_quality": 0.0,
            "upper": 0.0,
            "lower": 0.0,
            "mid": 0.0,
        }

    series = pd.Series(renko_closes)
    mid = series.rolling(bb_period).mean()
    std = series.rolling(bb_period).std()
    upper = mid + bb_std * std
    lower = mid - bb_std * std

    bandwidth = (upper - lower) / mid.replace(0, np.nan)
    bandwidth = bandwidth.fillna(0)

    current_bw = float(bandwidth.iloc[-1])

    # Squeeze: bandwidth below its rolling 25th percentile over 2x the period
    squeeze_window = min(len(bandwidth), bb_period * 2)
    recent_bw = bandwidth.tail(squeeze_window)
    squeeze_threshold = float(recent_bw.quantile(0.25))
    is_squeeze = current_bw <= squeeze_threshold and current_bw > 0
    squeeze_quality = 0.0
    if squeeze_threshold > 0 and is_squeeze:
        # 0 means just at threshold; 1 means very tight compression.
        squeeze_quality = max(0.0, min(1.0, 1.0 - (current_bw / squeeze_threshold)))

    # Expanding: bandwidth increasing over last 3 readings
    if len(bandwidth) >= 4:
        bw_tail = bandwidth.tail(4).values
        is_expanding = bw_tail[-1] > bw_tail[-2] > bw_tail[-3]
    else:
        is_expanding = False

    return {
        "bandwidth": current_bw,
        "squeeze": is_squeeze,
        "expanding": is_expanding,
        "squeeze_threshold": squeeze_threshold,
        "squeeze_quality": squeeze_quality,
        "upper": float(upper.iloc[-1]),
        "lower": float(lower.iloc[-1]),
        "mid": float(mid.iloc[-1]),
    }


def classify_regime(
    trend_score: float,
    bbwas: dict,
    trend_threshold: float = 0.3,
    squeeze_override: bool = True,
) -> dict:
    """
    Combine Renko trend + BBWAS into a regime classification.

    Returns:
        regime: trending_bull | trending_bear | squeeze | extended | neutral
        direction: bull | bear | neutral
        energy: expanding | contracting | squeeze | neutral
        scale: position scale factor (0.25 to 1.0)
    """
    is_squeeze = bbwas.get("squeeze", False)
    is_expanding = bbwas.get("expanding", False)
    bandwidth = bbwas.get("bandwidth", 0)

    if is_squeeze and squeeze_override:
        return {
            "regime": "squeeze",
            "direction": "neutral",
            "energy": "squeeze",
            "scale": 0.5,
            "confidence": 0.5 + 0.5 * bbwas.get("squeeze_quality", 0.0),
        }

    if trend_score >= trend_threshold:
        direction = "bull"
    elif trend_score <= -trend_threshold:
        direction = "bear"
    else:
        direction = "neutral"

    if is_expanding:
        energy = "expanding"
    elif bandwidth > 0:
        energy = "contracting"
    else:
        energy = "neutral"

    # Confidence combines directional conviction and volatility context.
    trend_component = min(1.0, abs(trend_score))
    bw_component = min(1.0, bandwidth / 0.75) if bandwidth > 0 else 0.0
    confidence = 0.6 * trend_component + 0.4 * bw_component

    if direction == "bull" and energy == "expanding":
        return {"regime": "trending_bull", "direction": "bull", "energy": energy, "scale": 1.0, "confidence": confidence}
    if direction == "bear" and energy == "expanding":
        return {"regime": "trending_bear", "direction": "bear", "energy": energy, "scale": 0.35, "confidence": confidence}
    if direction == "bull" and energy == "contracting":
        return {"regime": "trending_bull", "direction": "bull", "energy": energy, "scale": 0.75, "confidence": confidence}
    if direction == "bear" and energy == "contracting":
        return {"regime": "trending_bear", "direction": "bear", "energy": energy, "scale": 0.5, "confidence": confidence}

    if direction == "neutral":
        return {"regime": "neutral", "direction": "neutral", "energy": energy, "scale": 0.6, "confidence": confidence}

    return {"regime": "neutral", "direction": direction, "energy": energy, "scale": 0.6, "confidence": confidence}


def combine_renko_timeframes(
    fast_sig: dict,
    slow_sig: dict,
    require_agreement: bool = True,
) -> dict:
    """
    Combine fast and slow Renko signals.

    If require_agreement=True:
    - matching directional signals -> use the more conservative (lower) scale
    - disagreement -> neutralized risk posture
    """
    fast_dir = fast_sig.get("direction", "neutral")
    slow_dir = slow_sig.get("direction", "neutral")
    fast_scale = float(fast_sig.get("scale", 0.6))
    slow_scale = float(slow_sig.get("scale", 0.6))

    if not require_agreement:
        merged = dict(fast_sig)
        merged["scale"] = min(fast_scale, slow_scale)
        merged["confidence"] = (float(fast_sig.get("confidence", 0.5)) + float(slow_sig.get("confidence", 0.5))) / 2
        return merged

    if fast_dir == slow_dir and fast_dir in {"bull", "bear"}:
        merged = dict(fast_sig)
        merged["scale"] = min(fast_scale, slow_scale)
        merged["confidence"] = (float(fast_sig.get("confidence", 0.5)) + float(slow_sig.get("confidence", 0.5))) / 2
        merged["mtf_confirmed"] = True
        return merged

    # Conflicting or neutral -> reduce risk, keep directional call neutral.
    return {
        "regime": "neutral",
        "direction": "neutral",
        "energy": "contracting",
        "scale": min(0.6, max(fast_scale, slow_scale)),
        "confidence": min(float(fast_sig.get("confidence", 0.5)), float(slow_sig.get("confidence", 0.5))),
        "brick_trend": fast_sig.get("brick_trend", 0.0),
        "bandwidth": fast_sig.get("bandwidth", 0.0),
        "squeeze": bool(fast_sig.get("squeeze", False) or slow_sig.get("squeeze", False)),
        "n_bricks": fast_sig.get("n_bricks", 0),
        "brick_size": fast_sig.get("brick_size", 0.0),
        "ticker": fast_sig.get("ticker", ""),
        "mtf_confirmed": False,
    }


def load_ohlc_from_cache(
    ticker: str,
    prices_path: Optional[Path] = None,
) -> Optional[pd.DataFrame]:
    """Load OHLC data for a ticker from the cache directory."""
    if prices_path and prices_path.exists():
        paths = [prices_path]
    else:
        paths = list(CACHE_DIR.glob("prices*.json"))

    for path in paths:
        try:
            with open(path) as f:
                raw = json.load(f)
            if ticker in raw and raw[ticker]:
                df = pd.DataFrame(raw[ticker])
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date").sort_index()
                for col in ("open", "high", "low", "close"):
                    if col not in df.columns:
                        return None
                return df
        except Exception:
            continue
    return None


def renko_regime(
    ticker: str,
    atr_period: int = 14,
    atr_mult: float = 1.0,
    bb_period: int = 20,
    bb_std: float = 2.0,
    brick_lookback: int = 10,
    trend_threshold: float = 0.3,
    prices_path: Optional[Path] = None,
    ohlc_df: Optional[pd.DataFrame] = None,
) -> dict:
    """
    Full Renko + BBWAS regime signal for a ticker.

    Args:
        ticker: Ticker symbol (used to load from cache if ohlc_df not provided)
        atr_period: ATR period for brick size
        atr_mult: Multiplier on ATR for brick size (higher = fewer bricks, smoother)
        bb_period: Bollinger Band lookback
        bb_std: Bollinger Band standard deviations
        brick_lookback: Number of recent bricks for trend scoring
        trend_threshold: Absolute trend score required for directional call
        prices_path: Override cache path
        ohlc_df: Pre-loaded OHLC DataFrame (skips cache load)

    Returns:
        dict with keys: regime, direction, energy, scale, brick_trend,
                        bandwidth, squeeze, n_bricks, brick_size, ticker
    """
    if ohlc_df is None:
        ohlc_df = load_ohlc_from_cache(ticker, prices_path)
    if ohlc_df is None or len(ohlc_df) < atr_period + 5:
        return {
            "regime": "neutral", "direction": "neutral", "energy": "neutral",
            "scale": 0.6, "brick_trend": 0.0, "bandwidth": 0.0,
            "squeeze": False, "n_bricks": 0, "brick_size": 0.0, "ticker": ticker,
        }

    atr = compute_atr(ohlc_df, period=atr_period)
    brick_size = float(atr.iloc[-1] * atr_mult)
    if brick_size <= 0:
        brick_size = float(ohlc_df["close"].iloc[-1] * 0.02)

    bricks = build_renko_bricks(ohlc_df["close"], brick_size)
    if len(bricks) < 3:
        return {
            "regime": "neutral", "direction": "neutral", "energy": "neutral",
            "scale": 0.6, "brick_trend": 0.0, "bandwidth": 0.0,
            "squeeze": False, "n_bricks": len(bricks), "brick_size": brick_size,
            "ticker": ticker,
        }

    trend = renko_trend_score(bricks, lookback=brick_lookback)
    renko_closes = np.array([b["end"] for b in bricks])
    bbwas = compute_bbwas(renko_closes, bb_period=bb_period, bb_std=bb_std)
    classification = classify_regime(trend, bbwas, trend_threshold=trend_threshold)

    return {
        **classification,
        "brick_trend": round(trend, 3),
        "bandwidth": round(bbwas["bandwidth"], 4),
        "squeeze": bbwas["squeeze"],
        "squeeze_quality": round(bbwas.get("squeeze_quality", 0.0), 3),
        "n_bricks": len(bricks),
        "brick_size": round(brick_size, 2),
        "ticker": ticker,
    }


def renko_regime_multi(
    tickers: list[str],
    **kwargs,
) -> dict[str, dict]:
    """Run renko_regime for multiple tickers."""
    return {t: renko_regime(t, **kwargs) for t in tickers}


def renko_regime_mtf(
    ticker: str,
    atr_mult_fast: float = 1.0,
    atr_mult_slow: float = 2.0,
    require_agreement: bool = True,
    **kwargs,
) -> dict:
    """Run fast+slow Renko and combine into a single multi-timeframe signal."""
    fast_sig = renko_regime(ticker, atr_mult=atr_mult_fast, **kwargs)
    slow_sig = renko_regime(ticker, atr_mult=atr_mult_slow, **kwargs)
    merged = combine_renko_timeframes(fast_sig, slow_sig, require_agreement=require_agreement)
    merged["atr_mult_fast"] = atr_mult_fast
    merged["atr_mult_slow"] = atr_mult_slow
    return merged


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Renko + BBWAS regime signal")
    parser.add_argument("--ticker", type=str, default="AAPL", help="Ticker symbol")
    parser.add_argument("--all-tickers", action="store_true", help="Run on all tickers in all caches")
    parser.add_argument("--atr-period", type=int, default=14)
    parser.add_argument("--atr-mult", type=float, default=1.0,
                        help="ATR multiplier for brick size (higher = smoother, fewer bricks)")
    parser.add_argument("--bb-period", type=int, default=20)
    parser.add_argument("--lookback", type=int, default=10, help="Recent bricks for trend scoring")
    parser.add_argument("--atr-mult-slow", type=float, default=0.0,
                        help="Optional slow ATR multiplier for MTF confirmation (e.g. 2.0)")
    parser.add_argument("--no-mtf-confirm", action="store_true",
                        help="When using --atr-mult-slow, do not require fast/slow agreement")
    args = parser.parse_args()

    if args.all_tickers:
        all_tickers = set()
        for path in CACHE_DIR.glob("prices*.json"):
            try:
                with open(path) as f:
                    raw = json.load(f)
                all_tickers.update(raw.keys())
            except Exception:
                continue
        tickers = sorted(all_tickers)
    else:
        tickers = [t.strip() for t in args.ticker.split(",")]

    print(f"{'Ticker':>8} {'Regime':>16} {'Dir':>8} {'Energy':>12} {'Scale':>6} {'Trend':>7} {'BW':>7} {'Sqz':>5} {'Bricks':>7}")
    print("-" * 95)

    last_sig = None
    for ticker in tickers:
        if args.atr_mult_slow and args.atr_mult_slow > 0:
            sig = renko_regime_mtf(
                ticker,
                atr_mult_fast=args.atr_mult,
                atr_mult_slow=args.atr_mult_slow,
                require_agreement=not args.no_mtf_confirm,
                atr_period=args.atr_period,
                bb_period=args.bb_period,
                brick_lookback=args.lookback,
            )
        else:
            sig = renko_regime(
                ticker,
                atr_period=args.atr_period,
                atr_mult=args.atr_mult,
                bb_period=args.bb_period,
                brick_lookback=args.lookback,
            )
        last_sig = sig
        sqz = "YES" if sig["squeeze"] else ""
        print(f"{sig['ticker']:>8} {sig['regime']:>16} {sig['direction']:>8} {sig['energy']:>12} "
              f"{sig['scale']:>6.2f} {sig['brick_trend']:>+7.3f} {sig['bandwidth']:>7.4f} {sqz:>5} {sig['n_bricks']:>7}")

    if len(tickers) == 1 and last_sig is not None:
        print()
        print(_format_conclusion(last_sig))


def _format_conclusion(sig: dict) -> str:
    """Human-readable conclusion from Renko+BBWAS signal."""
    regime = sig.get("regime", "neutral")
    direction = sig.get("direction", "neutral")
    energy = sig.get("energy", "neutral")
    scale = sig.get("scale", 0.6)
    squeeze = sig.get("squeeze", False)
    confidence = float(sig.get("confidence", 0.5))
    ticker = sig.get("ticker", "")

    if regime == "squeeze":
        return (
            f"Conclusion: {ticker} in squeeze. Bands compressed — big move loading. "
            f"Scale to {scale:.0%} until direction clears (confidence {confidence:.0%})."
        )
    if regime == "trending_bear":
        return (
            f"Conclusion: Bearish. Red bricks dominate, bands expanding. "
            f"Momentum down — scale position to {scale:.0%} (confidence {confidence:.0%})."
        )
    if regime == "trending_bull":
        return (
            f"Conclusion: Bullish. Green bricks dominate, bands expanding. "
            f"Momentum up — scale position to {scale:.0%} (confidence {confidence:.0%})."
        )
    if direction == "bear" and energy == "contracting":
        return f"Conclusion: Bearish but energy contracting. Move may be exhausting — scale to {scale:.0%}."
    if direction == "bull" and energy == "contracting":
        return f"Conclusion: Bullish but energy contracting. Move may be exhausting — scale to {scale:.0%}."
    return f"Conclusion: Neutral. Mixed or insufficient conviction — scale to {scale:.0%}."


if __name__ == "__main__":
    main()
