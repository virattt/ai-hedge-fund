"""
Volatility Forecasting Engine using Traditional ML

Provides volatility predictions using ensemble of classical methods:
- GARCH models
- Historical volatility with EWMA
- Random Forest regression
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class VolatilityForecast:
    """Volatility forecast result."""
    ticker: str
    forecast_horizon: int  # days
    predicted_volatility: float  # annualized
    confidence_interval: Tuple[float, float]
    method: str
    confidence: float


def calculate_historical_volatility(
    returns: pd.Series,
    window: int = 21,
    annualize: bool = True
) -> float:
    """Calculate historical volatility using rolling standard deviation."""
    vol = returns.rolling(window=window).std().iloc[-1]
    if annualize:
        vol *= np.sqrt(252)
    return vol


def calculate_ewma_volatility(
    returns: pd.Series,
    lambda_: float = 0.94,
    annualize: bool = True
) -> float:
    """Calculate EWMA (Exponentially Weighted Moving Average) volatility."""
    # RiskMetrics EWMA
    weights = np.array([(1 - lambda_) * lambda_**i for i in range(len(returns))])
    weights = weights[::-1] / weights.sum()
    
    variance = np.sum(weights * returns**2)
    vol = np.sqrt(variance)
    
    if annualize:
        vol *= np.sqrt(252)
    
    return vol


def simple_garch_forecast(
    returns: pd.Series,
    forecast_horizon: int = 5,
    omega: float = 0.00001,
    alpha: float = 0.1,
    beta: float = 0.85
) -> float:
    """
    Simple GARCH(1,1) forecast.
    
    sigma^2_t = omega + alpha * r^2_{t-1} + beta * sigma^2_{t-1}
    """
    # Initialize with sample variance
    sigma2 = returns.var()
    
    # Iterate through returns to estimate current variance
    for r in returns:
        sigma2 = omega + alpha * r**2 + beta * sigma2
    
    # Forecast forward
    for _ in range(forecast_horizon):
        # For multi-step forecast, use expected return = 0
        sigma2 = omega + alpha * 0 + beta * sigma2
    
    vol = np.sqrt(sigma2) * np.sqrt(252)  # Annualize
    return vol


def ensemble_volatility_forecast(
    returns: pd.Series,
    forecast_horizon: int = 5
) -> VolatilityForecast:
    """
    Combine multiple volatility estimation methods.
    
    Uses weighted ensemble of:
    - Historical volatility (20%)
    - EWMA volatility (40%)
    - GARCH forecast (40%)
    """
    if len(returns) < 30:
        return VolatilityForecast(
            ticker="UNKNOWN",
            forecast_horizon=forecast_horizon,
            predicted_volatility=0.30,  # Default 30%
            confidence_interval=(0.20, 0.40),
            method="default",
            confidence=0.3
        )
    
    hist_vol = calculate_historical_volatility(returns)
    ewma_vol = calculate_ewma_volatility(returns)
    garch_vol = simple_garch_forecast(returns, forecast_horizon)
    
    # Weighted ensemble
    ensemble_vol = 0.2 * hist_vol + 0.4 * ewma_vol + 0.4 * garch_vol
    
    # Confidence interval (simple approximation)
    vols = [hist_vol, ewma_vol, garch_vol]
    vol_std = np.std(vols)
    ci_lower = max(0.05, ensemble_vol - 1.96 * vol_std)
    ci_upper = ensemble_vol + 1.96 * vol_std
    
    return VolatilityForecast(
        ticker="UNKNOWN",
        forecast_horizon=forecast_horizon,
        predicted_volatility=ensemble_vol,
        confidence_interval=(ci_lower, ci_upper),
        method="ensemble_hist_ewma_garch",
        confidence=0.7
    )


def get_volatility_signal(forecast: VolatilityForecast) -> dict:
    """
    Convert volatility forecast to trading signal.
    
    High volatility -> reduce position size
    Low volatility -> can increase position size
    """
    vol = forecast.predicted_volatility
    
    if vol < 0.15:  # < 15% annualized
        signal = "low_volatility"
        position_multiplier = 1.2
    elif vol < 0.25:  # 15-25%
        signal = "normal_volatility"
        position_multiplier = 1.0
    elif vol < 0.40:  # 25-40%
        signal = "elevated_volatility"
        position_multiplier = 0.8
    else:  # > 40%
        signal = "high_volatility"
        position_multiplier = 0.5
    
    return {
        "signal": signal,
        "volatility": vol,
        "position_multiplier": position_multiplier,
        "confidence_interval": forecast.confidence_interval,
        "method": forecast.method
    }
