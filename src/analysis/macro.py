"""Live macro context: VIX, yield curve, S&P regime.

Pulls a handful of free yfinance series and assembles a `MacroSnapshot`
the UI can render in a compact panel. Cached for 5 minutes to avoid
hammering Yahoo on every page load.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class MacroSnapshot:
    vix: Optional[float] = None
    vix_label: Optional[str] = None         # "Calm" / "Normal" / "Elevated" / "Stressed"
    vix_change_1d: Optional[float] = None   # decimal

    us_10y: Optional[float] = None          # decimal pct, e.g. 0.0445 = 4.45%
    us_2y: Optional[float] = None
    yield_curve_spread: Optional[float] = None  # 10y - 2y, in percentage points
    yield_curve_label: Optional[str] = None     # "Inverted" / "Flat" / "Normal" / "Steep"

    spx_price: Optional[float] = None
    spx_change_1d: Optional[float] = None
    spx_above_200dma: Optional[bool] = None
    spx_pct_from_52w_high: Optional[float] = None
    spx_200dma_slope_positive: Optional[bool] = None

    fear_greed: Optional[int] = None        # CNN Fear & Greed (optional / fragile)
    fear_greed_label: Optional[str] = None

    regime_label: str = "Unknown"           # "Risk-on" / "Risk-on cautious" / "Mixed" / "Risk-off"
    regime_emoji: str = "🟡"
    regime_color: str = "var(--hold)"
    regime_blurb: str = ""

    fetched_at: float = 0.0


_CACHE: dict[str, tuple[float, MacroSnapshot]] = {}
_TTL = 300  # seconds


def _last_close(symbol: str, period: str = "5d") -> Optional[float]:
    try:
        import yfinance as yf
        h = yf.Ticker(symbol).history(period=period)
        if h is None or h.empty:
            return None
        return float(h["Close"].iloc[-1])
    except Exception:
        return None


def _two_closes(symbol: str, period: str = "5d") -> tuple[Optional[float], Optional[float]]:
    try:
        import yfinance as yf
        h = yf.Ticker(symbol).history(period=period)
        if h is None or h.empty:
            return None, None
        if len(h) < 2:
            return float(h["Close"].iloc[-1]), None
        return float(h["Close"].iloc[-1]), float(h["Close"].iloc[-2])
    except Exception:
        return None, None


def _spx_features() -> dict:
    try:
        import yfinance as yf
        h = yf.Ticker("^GSPC").history(period="2y")
        if h is None or h.empty:
            return {}
        close = h["Close"]
        last = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) >= 2 else None
        chg_1d = (last / prev - 1) if prev else None
        sma200 = close.rolling(200, min_periods=200).mean()
        above = bool(last > float(sma200.iloc[-1])) if not pd.isna(sma200.iloc[-1]) else None
        slope_pos = None
        if len(sma200.dropna()) >= 21:
            slope_pos = bool(sma200.iloc[-1] > sma200.iloc[-21])
        pct_from_high = last / float(close.tail(252).max()) - 1 if len(close) >= 252 else None
        return {
            "price": last,
            "change_1d": chg_1d,
            "above_200dma": above,
            "slope_positive": slope_pos,
            "pct_from_52w_high": pct_from_high,
        }
    except Exception:
        return {}


def _vix_label(vix: Optional[float]) -> Optional[str]:
    if vix is None:
        return None
    if vix < 14:
        return "Calm"
    if vix < 20:
        return "Normal"
    if vix < 28:
        return "Elevated"
    return "Stressed"


def _yield_curve_label(spread: Optional[float]) -> Optional[str]:
    if spread is None:
        return None
    if spread < -0.10:
        return "Inverted"
    if spread < 0.30:
        return "Flat"
    if spread < 1.50:
        return "Normal"
    return "Steep"


def get_macro_snapshot(force_refresh: bool = False) -> MacroSnapshot:
    """Build (or fetch from cache) the live macro snapshot."""
    now = time.time()
    cached = _CACHE.get("snap")
    if cached and not force_refresh and now - cached[0] < _TTL:
        return cached[1]

    snap = MacroSnapshot(fetched_at=now)

    # VIX
    vix_latest, vix_prev = _two_closes("^VIX")
    if vix_latest is not None:
        snap.vix = vix_latest
        snap.vix_label = _vix_label(vix_latest)
        if vix_prev:
            snap.vix_change_1d = (vix_latest - vix_prev) / vix_prev

    # 10y and 2y yields. ^TNX = 10y × 10, ^FVX = 5y × 10, ^IRX = 13w × 10
    # 2y is sometimes ^DGS2 (FRED). Try both, fall back to 5y as proxy.
    tnx = _last_close("^TNX")
    if tnx is not None:
        snap.us_10y = tnx / 100  # ^TNX quoted as e.g. 44.5 → 4.45%
    two_y = None
    for sym in ("^IRX",):  # 13-week T-bill — short-end proxy
        v = _last_close(sym)
        if v is not None:
            two_y = v / 100
            break
    if two_y is None:
        # Fallback: 5y
        fvx = _last_close("^FVX")
        if fvx is not None:
            two_y = fvx / 100
    snap.us_2y = two_y
    if snap.us_10y is not None and snap.us_2y is not None:
        snap.yield_curve_spread = (snap.us_10y - snap.us_2y) * 100  # in percentage points
        snap.yield_curve_label = _yield_curve_label(snap.us_10y - snap.us_2y)

    # SPX
    spx = _spx_features()
    snap.spx_price = spx.get("price")
    snap.spx_change_1d = spx.get("change_1d")
    snap.spx_above_200dma = spx.get("above_200dma")
    snap.spx_pct_from_52w_high = spx.get("pct_from_52w_high")
    snap.spx_200dma_slope_positive = spx.get("slope_positive")

    # CNN Fear & Greed (best-effort, may fail)
    try:
        import json as _json
        from urllib.request import Request, urlopen
        req = Request(
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urlopen(req, timeout=4) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
            score = data.get("fear_and_greed", {}).get("score")
            rating = data.get("fear_and_greed", {}).get("rating")
            if score is not None:
                snap.fear_greed = int(round(float(score)))
                snap.fear_greed_label = rating.replace("_", " ").title() if rating else None
    except Exception:
        pass

    # Regime synthesis
    flags = {
        "vix_calm": snap.vix is not None and snap.vix < 18,
        "vix_stressed": snap.vix is not None and snap.vix > 28,
        "spx_above_200": snap.spx_above_200dma is True,
        "spx_uptrending": snap.spx_200dma_slope_positive is True,
        "curve_inverted": snap.yield_curve_label == "Inverted",
        "fear_greedy": snap.fear_greed is not None and snap.fear_greed >= 65,
        "fear_fearful": snap.fear_greed is not None and snap.fear_greed <= 25,
    }
    if flags["vix_stressed"] or not flags["spx_above_200"]:
        snap.regime_label = "Risk-off"
        snap.regime_emoji = "🔴"
        snap.regime_color = "var(--sell)"
    elif flags["vix_calm"] and flags["spx_above_200"] and flags["spx_uptrending"]:
        snap.regime_label = "Risk-on"
        snap.regime_emoji = "🟢"
        snap.regime_color = "var(--buy)"
    else:
        snap.regime_label = "Mixed"
        snap.regime_emoji = "🟡"
        snap.regime_color = "var(--hold)"

    blurb_parts = []
    if snap.vix is not None:
        blurb_parts.append(f"VIX {snap.vix:.1f} ({snap.vix_label.lower()})")
    if snap.us_10y is not None:
        blurb_parts.append(f"10Y {snap.us_10y*100:.2f}%")
    if snap.yield_curve_label:
        blurb_parts.append(f"curve {snap.yield_curve_label.lower()}")
    if snap.spx_above_200dma is not None:
        blurb_parts.append("S&P > 200DMA" if snap.spx_above_200dma else "S&P < 200DMA")
    if snap.fear_greed is not None:
        blurb_parts.append(f"F&G {snap.fear_greed}")
    snap.regime_blurb = " · ".join(blurb_parts)

    _CACHE["snap"] = (now, snap)
    return snap
