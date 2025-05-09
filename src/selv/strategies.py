# Each strategy dict now includes risk-management parameters:
#  - "tp": Take-profit (fractional return, e.g. 0.02 for +2%)
#  - "sl": Stop-loss (fractional return, e.g. 0.01 for -1%)
#  - "max_minutes": Maximum holding period (minutes)
# These are used by run_strategy_on_df for position sizing and risk control.

# Strategy 1: EMA Crossover (10/30 min)
import pandas as pd


def long_ema_10_30_cross(df: pd.DataFrame) -> pd.Series:
    """Long entry for EMA 10/30 crossover."""
    return df["EMA_10"] > df["EMA_30"]


def short_ema_10_30_cross(df: pd.DataFrame) -> pd.Series:
    """Short entry for EMA 10/30 crossover."""
    return df["EMA_10"] < df["EMA_30"]


# Strategy 2: SMA Crossover (50/200 min - Golden/Death Cross)
def long_sma_50_200_cross(df: pd.DataFrame) -> pd.Series:
    """Long entry for SMA 50/200 crossover."""
    return df["SMA_50"] > df["SMA_200"]


def short_sma_50_200_cross(df: pd.DataFrame) -> pd.Series:
    """Short entry for SMA 50/200 crossover."""
    return df["SMA_50"] < df["SMA_200"]


# Strategy 3: RSI (Oversold/Overbought)
def long_rsi_30_70(df: pd.DataFrame) -> pd.Series:
    """Long entry for RSI < 30."""
    return df["rsi"] < 30


def short_rsi_30_70(df: pd.DataFrame) -> pd.Series:
    """Short entry for RSI > 70."""
    return df["rsi"] > 70


# Strategy 4: MACD Crossover (Standard)
def long_macd_cross(df: pd.DataFrame) -> pd.Series:
    """Long entry for MACD crossover."""
    return df["MACD_12_26_9"] > df["MACDs_12_26_9"]


def short_macd_cross(df: pd.DataFrame) -> pd.Series:
    """Short entry for MACD crossunder."""
    return df["MACD_12_26_9"] < df["MACDs_12_26_9"]


# Strategy 5: MACD + RSI (Confirmation)
def long_macd_rsi_confirm(df: pd.DataFrame) -> pd.Series:
    """Long entry for MACD crossover and RSI > 55."""
    return (df["MACD_12_26_9"] > df["MACDs_12_26_9"]) & (df["rsi"] > 55)


def short_macd_rsi_confirm(df: pd.DataFrame) -> pd.Series:
    """Short entry for MACD crossunder and RSI < 45."""
    return (df["MACD_12_26_9"] < df["MACDs_12_26_9"]) & (df["rsi"] < 45)


STRATEGIES = {
    "EMA_10_30_Cross": {
        "long_entry_fun": long_ema_10_30_cross,
        "short_entry_fun": short_ema_10_30_cross,
        "tp": 0.015,
        "sl": 0.0075,
        "max_minutes": 720,
    },
    "SMA_50_200_Cross": {
        "long_entry_fun": long_sma_50_200_cross,
        "short_entry_fun": short_sma_50_200_cross,
        "tp": 0.04,
        "sl": 0.02,
        "max_minutes": 4320,
    },
    "RSI_30_70": {
        "long_entry_fun": long_rsi_30_70,
        "short_entry_fun": short_rsi_30_70,
        "tp": 0.025,
        "sl": 0.0125,
        "max_minutes": 1440,
    },
    "MACD_Cross": {
        "long_entry_fun": long_macd_cross,
        "short_entry_fun": short_macd_cross,
        "tp": 0.03,
        "sl": 0.015,
        "max_minutes": 2880,
    },
    "MACD_RSI_Confirm": {  # This is the original default
        "long_entry_fun": long_macd_rsi_confirm,
        "short_entry_fun": short_macd_rsi_confirm,
        "tp": 0.02,
        "sl": 0.01,
        "max_minutes": 1440,
    },
}