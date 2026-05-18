"""Pure-pandas technical indicators. No external TA libraries — just numpy/pandas."""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window=window, min_periods=window).mean()


def ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (macd_line, signal_line, histogram)."""
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def bollinger(
    close: pd.Series, window: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (lower_band, mid_band, upper_band)."""
    mid = sma(close, window)
    std = close.rolling(window=window, min_periods=window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return lower, mid, upper


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def relative_volume(volume: pd.Series, window: int = 50) -> float:
    """Latest volume divided by trailing `window`-day average volume."""
    avg = volume.rolling(window=window, min_periods=1).mean().iloc[-1]
    latest = volume.iloc[-1]
    if avg <= 0 or pd.isna(avg):
        return float("nan")
    return float(latest / avg)


def period_return(close: pd.Series, days_back: int) -> float:
    """Return between latest close and `days_back` trading days earlier."""
    if len(close) <= days_back:
        return float("nan")
    latest = close.iloc[-1]
    past = close.iloc[-1 - days_back]
    if pd.isna(latest) or pd.isna(past) or past == 0:
        return float("nan")
    return float(latest / past - 1.0)


# Trading-day approximations for period lookbacks
PERIOD_DAYS = {
    "1D": 1,
    "1W": 5,
    "1M": 21,
    "6M": 126,
    "1Y": 252,
    "3Y": 756,
}


def compute_period_returns(close: pd.Series) -> dict[str, float]:
    """Map of period label -> total return (decimal, e.g. 0.123 = +12.3%)."""
    return {label: period_return(close, days) for label, days in PERIOD_DAYS.items()}
