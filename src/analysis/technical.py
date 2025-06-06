"""
Technical analysis module with various indicators and signal generation.
"""

import pandas as pd
import numpy as np
import talib
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

def calculate_sma(data: pd.DataFrame, period: int = 20) -> pd.Series:
    """Calculate Simple Moving Average."""
    return talib.SMA(data['CLOSE'], timeperiod=period)

def calculate_ema(data: pd.DataFrame, period: int = 20) -> pd.Series:
    """Calculate Exponential Moving Average."""
    return talib.EMA(data['CLOSE'], timeperiod=period)

def calculate_rsi(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index."""
    return talib.RSI(data['CLOSE'], timeperiod=period)

def calculate_macd(data: pd.DataFrame) -> tuple:
    """Calculate MACD (12,26,9)."""
    macd, signal, hist = talib.MACD(
        data['CLOSE'],
        fastperiod=12,
        slowperiod=26,
        signalperiod=9
    )
    return macd, signal, hist

def calculate_bollinger_bands(data: pd.DataFrame, period: int = 20) -> tuple:
    """Calculate Bollinger Bands."""
    upper, middle, lower = talib.BBANDS(
        data['CLOSE'],
        timeperiod=period,
        nbdevup=2,
        nbdevdn=2,
        matype=0
    )
    return upper, middle, lower

def calculate_stochastic(data: pd.DataFrame) -> tuple:
    """Calculate Stochastic Oscillator."""
    slowk, slowd = talib.STOCH(
        data['HIGH'],
        data['LOW'],
        data['CLOSE'],
        fastk_period=14,
        slowk_period=3,
        slowk_matype=0,
        slowd_period=3,
        slowd_matype=0
    )
    return slowk, slowd

def analyze_trend(data: pd.DataFrame) -> Dict[str, Any]:
    """Analyze price trend using multiple indicators."""
    try:
        # Calculate indicators
        sma20 = calculate_sma(data, 20)
        sma50 = calculate_sma(data, 50)
        sma200 = calculate_sma(data, 200)
        ema20 = calculate_ema(data, 20)
        
        current_price = data['CLOSE'].iloc[-1]
        
        # Determine trend
        short_trend = "BULLISH" if current_price > sma20.iloc[-1] else "BEARISH"
        medium_trend = "BULLISH" if sma20.iloc[-1] > sma50.iloc[-1] else "BEARISH"
        long_trend = "BULLISH" if sma50.iloc[-1] > sma200.iloc[-1] else "BEARISH"
        
        # Calculate trend strength
        trend_strength = 0
        if short_trend == "BULLISH": trend_strength += 1
        if medium_trend == "BULLISH": trend_strength += 1
        if long_trend == "BULLISH": trend_strength += 1
        
        return {
            "short_term": short_trend,
            "medium_term": medium_trend,
            "long_term": long_trend,
            "strength": trend_strength / 3.0  # Normalized to [0,1]
        }
        
    except Exception as e:
        logger.error(f"Error analyzing trend: {e}")
        return {
            "short_term": "UNKNOWN",
            "medium_term": "UNKNOWN",
            "long_term": "UNKNOWN",
            "strength": 0.0
        }

def analyze_momentum(data: pd.DataFrame) -> Dict[str, Any]:
    """Analyze momentum using RSI and Stochastic."""
    try:
        rsi = calculate_rsi(data)
        slowk, slowd = calculate_stochastic(data)
        
        # RSI signals
        rsi_value = rsi.iloc[-1]
        rsi_signal = (
            "OVERSOLD" if rsi_value < 30
            else "OVERBOUGHT" if rsi_value > 70
            else "NEUTRAL"
        )
        
        # Stochastic signals
        stoch_k = slowk.iloc[-1]
        stoch_d = slowd.iloc[-1]
        stoch_signal = (
            "OVERSOLD" if stoch_k < 20 and stoch_d < 20
            else "OVERBOUGHT" if stoch_k > 80 and stoch_d > 80
            else "NEUTRAL"
        )
        
        return {
            "rsi": {
                "value": rsi_value,
                "signal": rsi_signal
            },
            "stochastic": {
                "k": stoch_k,
                "d": stoch_d,
                "signal": stoch_signal
            }
        }
        
    except Exception as e:
        logger.error(f"Error analyzing momentum: {e}")
        return {
            "rsi": {"value": 0, "signal": "UNKNOWN"},
            "stochastic": {"k": 0, "d": 0, "signal": "UNKNOWN"}
        }

def analyze_volatility(data: pd.DataFrame) -> Dict[str, Any]:
    """Analyze volatility using Bollinger Bands."""
    try:
        upper, middle, lower = calculate_bollinger_bands(data)
        current_price = data['CLOSE'].iloc[-1]
        
        # Calculate bandwidth and %B
        bandwidth = (upper.iloc[-1] - lower.iloc[-1]) / middle.iloc[-1]
        percent_b = (current_price - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1])
        
        # Determine volatility state
        if bandwidth > 0.1:  # High volatility threshold
            volatility = "HIGH"
        elif bandwidth < 0.05:  # Low volatility threshold
            volatility = "LOW"
        else:
            volatility = "MEDIUM"
        
        return {
            "bandwidth": bandwidth,
            "percent_b": percent_b,
            "state": volatility
        }
        
    except Exception as e:
        logger.error(f"Error analyzing volatility: {e}")
        return {
            "bandwidth": 0,
            "percent_b": 0,
            "state": "UNKNOWN"
        }

def generate_signals(data: pd.DataFrame) -> List[Dict[str, Any]]:
    """Generate trading signals based on technical analysis."""
    signals = []
    
    try:
        # MACD signals
        macd, signal, hist = calculate_macd(data)
        if hist.iloc[-1] > 0 and hist.iloc[-2] <= 0:
            signals.append({
                "type": "MACD",
                "signal": "BUY",
                "reason": "MACD histogram crossed above zero",
                "strength": 0.6
            })
        elif hist.iloc[-1] < 0 and hist.iloc[-2] >= 0:
            signals.append({
                "type": "MACD",
                "signal": "SELL",
                "reason": "MACD histogram crossed below zero",
                "strength": 0.6
            })
        
        # RSI signals
        rsi = calculate_rsi(data)
        if rsi.iloc[-1] < 30:
            signals.append({
                "type": "RSI",
                "signal": "BUY",
                "reason": "RSI indicates oversold conditions",
                "strength": 0.7
            })
        elif rsi.iloc[-1] > 70:
            signals.append({
                "type": "RSI",
                "signal": "SELL",
                "reason": "RSI indicates overbought conditions",
                "strength": 0.7
            })
        
        # Bollinger Bands signals
        upper, middle, lower = calculate_bollinger_bands(data)
        current_price = data['CLOSE'].iloc[-1]
        if current_price < lower.iloc[-1]:
            signals.append({
                "type": "BB",
                "signal": "BUY",
                "reason": "Price below lower Bollinger Band",
                "strength": 0.65
            })
        elif current_price > upper.iloc[-1]:
            signals.append({
                "type": "BB",
                "signal": "SELL",
                "reason": "Price above upper Bollinger Band",
                "strength": 0.65
            })
        
        # Moving Average signals
        sma20 = calculate_sma(data, 20)
        sma50 = calculate_sma(data, 50)
        if sma20.iloc[-1] > sma50.iloc[-1] and sma20.iloc[-2] <= sma50.iloc[-2]:
            signals.append({
                "type": "MA",
                "signal": "BUY",
                "reason": "20-day SMA crossed above 50-day SMA",
                "strength": 0.75
            })
        elif sma20.iloc[-1] < sma50.iloc[-1] and sma20.iloc[-2] >= sma50.iloc[-2]:
            signals.append({
                "type": "MA",
                "signal": "SELL",
                "reason": "20-day SMA crossed below 50-day SMA",
                "strength": 0.75
            })
        
    except Exception as e:
        logger.error(f"Error generating signals: {e}")
    
    return signals

def analyze_stock(data: pd.DataFrame) -> Dict[str, Any]:
    """
    Perform comprehensive technical analysis on a stock.
    
    Args:
        data: DataFrame with OHLCV data
        
    Returns:
        Dictionary with analysis results
    """
    try:
        # Get all components
        trend = analyze_trend(data)
        momentum = analyze_momentum(data)
        volatility = analyze_volatility(data)
        signals = generate_signals(data)
        
        # Determine overall recommendation
        buy_signals = [s for s in signals if s['signal'] == 'BUY']
        sell_signals = [s for s in signals if s['signal'] == 'SELL']
        
        if len(buy_signals) > len(sell_signals):
            recommendation = "BUY"
            confidence = sum(s['strength'] for s in buy_signals) / len(buy_signals)
        elif len(sell_signals) > len(buy_signals):
            recommendation = "SELL"
            confidence = sum(s['strength'] for s in sell_signals) / len(sell_signals)
        else:
            recommendation = "HOLD"
            confidence = 0.5
        
        # Adjust confidence based on trend strength
        confidence = (confidence + trend['strength']) / 2
        
        return {
            "recommendation": recommendation,
            "confidence": confidence,
            "trend": trend,
            "momentum": momentum,
            "volatility": volatility,
            "signals": signals
        }
        
    except Exception as e:
        logger.error(f"Error in technical analysis: {e}")
        return {
            "recommendation": "HOLD",
            "confidence": 0.0,
            "trend": {},
            "momentum": {},
            "volatility": {},
            "signals": []
        } 