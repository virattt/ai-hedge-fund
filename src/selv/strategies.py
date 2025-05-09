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


# ---------------------------------------------------------------------
# 6. Bollinger Band Mean‑Reversion
def long_bband_meanrev(df: pd.DataFrame) -> pd.Series:
    """Long when price closes below lower Bollinger Band."""
    return df["close"] < df["BBL_20_2.0"]


def exit_bband_meanrev(df: pd.DataFrame) -> pd.Series:
    """Exit when price re‑touches middle band."""
    return df["close"] >= df["BBM_20_2.0"]


# 7. Golden‑Cross EMA‑21 / SMA‑50
def long_golden_cross(df: pd.DataFrame) -> pd.Series:
    return df["EMA_21"] > df["SMA_50"]


def exit_golden_cross(df: pd.DataFrame) -> pd.Series:
    return df["EMA_21"] < df["SMA_50"]


# 8. Stochastic RSI oversold bounce
def long_stochrsi(df: pd.DataFrame) -> pd.Series:
    return (df["STOCHRSIk_14_14_3_3"] > df["STOCHRSId_14_14_3_3"]) & (
        df["STOCHRSIk_14_14_3_3"] < 20
    )


def exit_stochrsi(df: pd.DataFrame) -> pd.Series:
    return (df["STOCHRSIk_14_14_3_3"] < df["STOCHRSId_14_14_3_3"]) & (
        df["STOCHRSIk_14_14_3_3"] > 80
    )


# 9. TEMA trend–following
def long_tema_trend(df: pd.DataFrame) -> pd.Series:
    return df["close"] > df["TEMA_50"]


def exit_tema_trend(df: pd.DataFrame) -> pd.Series:
    return df["close"] < df["TEMA_50"]


# 10. VWAP Pullback (intraday mean support)
def long_vwap_pullback(df: pd.DataFrame) -> pd.Series:
    return (df["close"] > df["VWAP_D"]) & (df["close"].shift(1) <= df["VWAP_D"])


def exit_vwap_pullback(df: pd.DataFrame) -> pd.Series:
    return (df["close"] < df["VWAP_D"]) & (df["close"].shift(1) >= df["VWAP_D"])


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
    "Bollinger_MeanRev": {
        "long_entry_fun": long_bband_meanrev,
        "short_entry_fun": exit_bband_meanrev,  # treated as exit
        "tp": 0.02,
        "sl": 0.01,
        "max_minutes": 720,
    },
    "Golden_Cross_21_50": {
        "long_entry_fun": long_golden_cross,
        "short_entry_fun": exit_golden_cross,
        "tp": 0.03,
        "sl": 0.015,
        "max_minutes": 2880,
    },
    "StochRSI_Bounce": {
        "long_entry_fun": long_stochrsi,
        "short_entry_fun": exit_stochrsi,
        "tp": 0.015,
        "sl": 0.0075,
        "max_minutes": 720,
    },
    "TEMA_Trend": {
        "long_entry_fun": long_tema_trend,
        "short_entry_fun": exit_tema_trend,
        "tp": 0.025,
        "sl": 0.0125,
        "max_minutes": 1440,
    },
    "VWAP_Pullback": {
        "long_entry_fun": long_vwap_pullback,
        "short_entry_fun": exit_vwap_pullback,
        "tp": 0.01,
        "sl": 0.005,
        "max_minutes": 240,
    },
}