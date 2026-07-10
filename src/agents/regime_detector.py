from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class RegimeState:
    regime: str        # "Bull" | "Bear" | "High-Vol" | "Risk-Off"
    trend: str         # "bull" | "bear"
    vol_level: str     # "low" | "elevated" | "crisis"
    momentum: str      # "risk_on" | "neutral" | "risk_off"


def detect_regime(spy_prices: pd.DataFrame) -> RegimeState:
    """
    Classify market regime from a SPY (or proxy) dataframe with a 'close' column.
    Falls back gracefully with less than 200 rows.
    """
    closes = spy_prices["close"].dropna()
    n = len(closes)

    # --- Trend: 50-day vs 200-day MA ---
    if n >= 200:
        ma50 = closes.iloc[-50:].mean()
        ma200 = closes.iloc[-200:].mean()
        trend = "bull" if ma50 > ma200 else "bear"
    elif n >= 50:
        ma50 = closes.iloc[-50:].mean()
        ma_long = closes.mean()
        trend = "bull" if ma50 > ma_long else "bear"
    else:
        trend = "bull"

    # --- Volatility: 20-day realized vol (annualised) ---
    daily_returns = closes.pct_change().dropna()
    lookback = min(20, len(daily_returns))
    if lookback >= 2:
        daily_vol = float(daily_returns.iloc[-lookback:].std())
        ann_vol = daily_vol * np.sqrt(252)
    else:
        ann_vol = 0.15

    if ann_vol < 0.15:
        vol_level = "low"
    elif ann_vol < 0.30:
        vol_level = "elevated"
    else:
        vol_level = "crisis"

    # --- Momentum: 63-day (≈3 month) return ---
    lookback_mom = min(63, n - 1)
    if lookback_mom >= 5:
        mom_return = float(closes.iloc[-1] / closes.iloc[-lookback_mom - 1] - 1)
    else:
        mom_return = 0.0

    if mom_return > 0.02:
        momentum = "risk_on"
    elif mom_return < -0.02:
        momentum = "risk_off"
    else:
        momentum = "neutral"

    # --- Regime classification (priority: High-Vol > Risk-Off > Bear > Bull) ---
    if vol_level == "crisis":
        regime = "High-Vol"
    elif trend == "bear" and momentum == "risk_off":
        regime = "Risk-Off"
    elif trend == "bear" or momentum == "risk_off":
        regime = "Bear"
    else:
        regime = "Bull"

    return RegimeState(regime=regime, trend=trend, vol_level=vol_level, momentum=momentum)


_MULTIPLIERS = {
    "Bull": 1.00,
    "Bear": 0.70,
    "High-Vol": 0.50,
    "Risk-Off": 0.40,
}


def regime_position_multiplier(regime: str) -> float:
    """Return the position-limit multiplier for a given regime label."""
    return _MULTIPLIERS.get(regime, 1.0)
