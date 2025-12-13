"""
Technical Analysis 技术分析算法 Demo

综合技术分析系统，包含5种交易策略：
1. 趋势跟踪 (Trend Following) - 25%权重
2. 均值回归 (Mean Reversion) - 20%权重
3. 动量策略 (Momentum) - 25%权重
4. 波动率分析 (Volatility) - 15%权重
5. 统计套利 (Statistical Arbitrage) - 15%权重

输入参数：
- ticker: 股票代码
- prices: OHLCV价格数据列表 (至少200天)

输出结果：
- signal: "bullish", "bearish", or "neutral"
- confidence: 0-100
- 每个策略的详细指标
"""

import math
from typing import List, Dict, Any
import pandas as pd
import numpy as np


def calculate_ema(prices_df: pd.DataFrame, window: int) -> pd.Series:
    """计算指数移动平均线"""
    return prices_df["close"].ewm(span=window, adjust=False).mean()


def calculate_adx(prices_df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    计算平均方向指数 (ADX)
    ADX用于衡量趋势强度
    """
    df = prices_df.copy()

    # 计算真实波动范围
    df["high_low"] = df["high"] - df["low"]
    df["high_close"] = abs(df["high"] - df["close"].shift())
    df["low_close"] = abs(df["low"] - df["close"].shift())
    df["tr"] = df[["high_low", "high_close", "low_close"]].max(axis=1)

    # 计算方向运动
    df["up_move"] = df["high"] - df["high"].shift()
    df["down_move"] = df["low"].shift() - df["low"]

    df["plus_dm"] = np.where(
        (df["up_move"] > df["down_move"]) & (df["up_move"] > 0), df["up_move"], 0
    )
    df["minus_dm"] = np.where(
        (df["down_move"] > df["up_move"]) & (df["down_move"] > 0), df["down_move"], 0
    )

    # 计算ADX
    df["+di"] = 100 * (df["plus_dm"].ewm(span=period).mean() / df["tr"].ewm(span=period).mean())
    df["-di"] = 100 * (df["minus_dm"].ewm(span=period).mean() / df["tr"].ewm(span=period).mean())
    df["dx"] = 100 * abs(df["+di"] - df["-di"]) / (df["+di"] + df["-di"])
    df["adx"] = df["dx"].ewm(span=period).mean()

    return df[["adx", "+di", "-di"]]


def calculate_rsi(prices_df: pd.DataFrame, period: int = 14) -> pd.Series:
    """计算相对强弱指数 (RSI)"""
    delta = prices_df["close"].diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_bollinger_bands(prices_df: pd.DataFrame, window: int = 20) -> tuple:
    """计算布林带"""
    sma = prices_df["close"].rolling(window).mean()
    std_dev = prices_df["close"].rolling(window).std()
    upper_band = sma + (std_dev * 2)
    lower_band = sma - (std_dev * 2)
    return upper_band, lower_band


def calculate_atr(prices_df: pd.DataFrame, period: int = 14) -> pd.Series:
    """计算平均真实波动幅度 (ATR)"""
    high_low = prices_df["high"] - prices_df["low"]
    high_close = abs(prices_df["high"] - prices_df["close"].shift())
    low_close = abs(prices_df["low"] - prices_df["close"].shift())

    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)

    return true_range.rolling(period).mean()


def calculate_hurst_exponent(price_series: pd.Series, max_lag: int = 20) -> float:
    """
    计算Hurst指数以确定时间序列的长期记忆
    H < 0.5: 均值回归序列
    H = 0.5: 随机游走
    H > 0.5: 趋势序列
    """
    lags = range(2, max_lag)
    tau = [
        max(1e-8, np.sqrt(np.std(np.subtract(price_series[lag:], price_series[:-lag]))))
        for lag in lags
    ]

    try:
        reg = np.polyfit(np.log(lags), np.log(tau), 1)
        return reg[0]  # Hurst指数是斜率
    except (ValueError, RuntimeWarning):
        return 0.5  # 如果计算失败，返回0.5（随机游走）


# ============================================================================
# 策略1: 趋势跟踪
# ============================================================================

def calculate_trend_signals(prices_df: pd.DataFrame) -> Dict[str, Any]:
    """
    使用多时间框架和指标的高级趋势跟踪策略

    使用EMA(8, 21, 55)和ADX(14)
    """
    # 计算多个时间框架的EMA
    ema_8 = calculate_ema(prices_df, 8)
    ema_21 = calculate_ema(prices_df, 21)
    ema_55 = calculate_ema(prices_df, 55)

    # 计算ADX以测量趋势强度
    adx = calculate_adx(prices_df, 14)

    # 确定趋势方向和强度
    short_trend = ema_8 > ema_21
    medium_trend = ema_21 > ema_55

    # 结合信号与置信度加权
    trend_strength = adx["adx"].iloc[-1] / 100.0

    if short_trend.iloc[-1] and medium_trend.iloc[-1]:
        signal = "bullish"
        confidence = trend_strength
    elif not short_trend.iloc[-1] and not medium_trend.iloc[-1]:
        signal = "bearish"
        confidence = trend_strength
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "adx": float(adx["adx"].iloc[-1]),
            "trend_strength": float(trend_strength),
        },
    }


# ============================================================================
# 策略2: 均值回归
# ============================================================================

def calculate_mean_reversion_signals(prices_df: pd.DataFrame) -> Dict[str, Any]:
    """
    使用统计指标和布林带的均值回归策略
    """
    # 计算相对于移动平均的价格Z-score
    ma_50 = prices_df["close"].rolling(window=50).mean()
    std_50 = prices_df["close"].rolling(window=50).std()
    z_score = (prices_df["close"] - ma_50) / std_50

    # 计算布林带
    bb_upper, bb_lower = calculate_bollinger_bands(prices_df)

    # 计算多时间框架RSI
    rsi_14 = calculate_rsi(prices_df, 14)
    rsi_28 = calculate_rsi(prices_df, 28)

    # 均值回归信号
    price_vs_bb = (prices_df["close"].iloc[-1] - bb_lower.iloc[-1]) / (
        bb_upper.iloc[-1] - bb_lower.iloc[-1]
    )

    # 组合信号
    if z_score.iloc[-1] < -2 and price_vs_bb < 0.2:
        signal = "bullish"
        confidence = min(abs(z_score.iloc[-1]) / 4, 1.0)
    elif z_score.iloc[-1] > 2 and price_vs_bb > 0.8:
        signal = "bearish"
        confidence = min(abs(z_score.iloc[-1]) / 4, 1.0)
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "z_score": float(z_score.iloc[-1]),
            "price_vs_bb": float(price_vs_bb),
            "rsi_14": float(rsi_14.iloc[-1]),
            "rsi_28": float(rsi_28.iloc[-1]),
        },
    }


# ============================================================================
# 策略3: 动量
# ============================================================================

def calculate_momentum_signals(prices_df: pd.DataFrame) -> Dict[str, Any]:
    """
    多因子动量策略
    """
    # 价格动量
    returns = prices_df["close"].pct_change()
    mom_1m = returns.rolling(21).sum()
    mom_3m = returns.rolling(63).sum()
    mom_6m = returns.rolling(126).sum()

    # 成交量动量
    volume_ma = prices_df["volume"].rolling(21).mean()
    volume_momentum = prices_df["volume"] / volume_ma

    # 计算动量分数
    momentum_score = (0.4 * mom_1m + 0.3 * mom_3m + 0.3 * mom_6m).iloc[-1]

    # 成交量确认
    volume_confirmation = volume_momentum.iloc[-1] > 1.0

    if momentum_score > 0.05 and volume_confirmation:
        signal = "bullish"
        confidence = min(abs(momentum_score) * 5, 1.0)
    elif momentum_score < -0.05 and volume_confirmation:
        signal = "bearish"
        confidence = min(abs(momentum_score) * 5, 1.0)
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "momentum_1m": float(mom_1m.iloc[-1]),
            "momentum_3m": float(mom_3m.iloc[-1]),
            "momentum_6m": float(mom_6m.iloc[-1]),
            "volume_momentum": float(volume_momentum.iloc[-1]),
        },
    }


# ============================================================================
# 策略4: 波动率分析
# ============================================================================

def calculate_volatility_signals(prices_df: pd.DataFrame) -> Dict[str, Any]:
    """
    基于波动率的交易策略
    """
    returns = prices_df["close"].pct_change()

    # 历史波动率
    hist_vol = returns.rolling(21).std() * math.sqrt(252)

    # 波动率体制检测
    vol_ma = hist_vol.rolling(63).mean()
    vol_regime = hist_vol / vol_ma

    # 波动率均值回归
    vol_z_score = (hist_vol - vol_ma) / hist_vol.rolling(63).std()

    # ATR比率
    atr = calculate_atr(prices_df)
    atr_ratio = atr / prices_df["close"]

    # 基于波动率体制生成信号
    current_vol_regime = vol_regime.iloc[-1]
    vol_z = vol_z_score.iloc[-1]

    if current_vol_regime < 0.8 and vol_z < -1:
        signal = "bullish"  # 低波动体制，可能扩张
        confidence = min(abs(vol_z) / 3, 1.0)
    elif current_vol_regime > 1.2 and vol_z > 1:
        signal = "bearish"  # 高波动体制，可能收缩
        confidence = min(abs(vol_z) / 3, 1.0)
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "historical_volatility": float(hist_vol.iloc[-1]),
            "volatility_regime": float(current_vol_regime),
            "volatility_z_score": float(vol_z),
            "atr_ratio": float(atr_ratio.iloc[-1]),
        },
    }


# ============================================================================
# 策略5: 统计套利
# ============================================================================

def calculate_stat_arb_signals(prices_df: pd.DataFrame) -> Dict[str, Any]:
    """
    基于价格行为分析的统计套利信号
    """
    returns = prices_df["close"].pct_change()

    # 偏度和峰度
    skew = returns.rolling(63).skew()
    kurt = returns.rolling(63).kurt()

    # 使用Hurst指数测试均值回归
    hurst = calculate_hurst_exponent(prices_df["close"])

    # 基于统计特性生成信号
    if hurst < 0.4 and skew.iloc[-1] > 1:
        signal = "bullish"
        confidence = (0.5 - hurst) * 2
    elif hurst < 0.4 and skew.iloc[-1] < -1:
        signal = "bearish"
        confidence = (0.5 - hurst) * 2
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "hurst_exponent": float(hurst),
            "skewness": float(skew.iloc[-1]),
            "kurtosis": float(kurt.iloc[-1]),
        },
    }


# ============================================================================
# 加权信号组合
# ============================================================================

def weighted_signal_combination(signals: Dict, weights: Dict) -> Dict[str, Any]:
    """
    使用加权方法组合多个交易信号
    """
    signal_values = {"bullish": 1, "neutral": 0, "bearish": -1}

    weighted_sum = 0
    total_confidence = 0

    for strategy, signal in signals.items():
        numeric_signal = signal_values[signal["signal"]]
        weight = weights[strategy]
        confidence = signal["confidence"]

        weighted_sum += numeric_signal * weight * confidence
        total_confidence += weight * confidence

    # 标准化加权和
    if total_confidence > 0:
        final_score = weighted_sum / total_confidence
    else:
        final_score = 0

    # 转换回信号
    if final_score > 0.2:
        signal = "bullish"
    elif final_score < -0.2:
        signal = "bearish"
    else:
        signal = "neutral"

    return {"signal": signal, "confidence": abs(final_score)}


# ============================================================================
# 主算法函数
# ============================================================================

def technical_analysis_algorithm(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    技术分析算法主函数

    输入参数:
        data = {
            "ticker": str,
            "prices": List[Dict]  # OHLCV数据
        }

    输出结果:
        {
            "signal": "bullish" | "bearish" | "neutral",
            "confidence": float (0-100),
            "strategy_signals": {
                "trend_following": {...},
                "mean_reversion": {...},
                "momentum": {...},
                "volatility": {...},
                "statistical_arbitrage": {...}
            }
        }
    """
    ticker = data["ticker"]
    prices = data["prices"]

    # 转换为DataFrame
    prices_df = pd.DataFrame(prices)

    # 计算各策略信号
    trend_signals = calculate_trend_signals(prices_df)
    mean_reversion_signals = calculate_mean_reversion_signals(prices_df)
    momentum_signals = calculate_momentum_signals(prices_df)
    volatility_signals = calculate_volatility_signals(prices_df)
    stat_arb_signals = calculate_stat_arb_signals(prices_df)

    # 策略权重
    strategy_weights = {
        "trend": 0.25,
        "mean_reversion": 0.20,
        "momentum": 0.25,
        "volatility": 0.15,
        "stat_arb": 0.15,
    }

    # 组合信号
    combined_signal = weighted_signal_combination(
        {
            "trend": trend_signals,
            "mean_reversion": mean_reversion_signals,
            "momentum": momentum_signals,
            "volatility": volatility_signals,
            "stat_arb": stat_arb_signals,
        },
        strategy_weights,
    )

    return {
        "ticker": ticker,
        "signal": combined_signal["signal"],
        "confidence": round(combined_signal["confidence"] * 100),
        "strategy_signals": {
            "trend_following": {
                "signal": trend_signals["signal"],
                "confidence": round(trend_signals["confidence"] * 100),
                "metrics": trend_signals["metrics"],
            },
            "mean_reversion": {
                "signal": mean_reversion_signals["signal"],
                "confidence": round(mean_reversion_signals["confidence"] * 100),
                "metrics": mean_reversion_signals["metrics"],
            },
            "momentum": {
                "signal": momentum_signals["signal"],
                "confidence": round(momentum_signals["confidence"] * 100),
                "metrics": momentum_signals["metrics"],
            },
            "volatility": {
                "signal": volatility_signals["signal"],
                "confidence": round(volatility_signals["confidence"] * 100),
                "metrics": volatility_signals["metrics"],
            },
            "statistical_arbitrage": {
                "signal": stat_arb_signals["signal"],
                "confidence": round(stat_arb_signals["confidence"] * 100),
                "metrics": stat_arb_signals["metrics"],
            },
        },
    }


# ============================================================================
# Demo 示例
# ============================================================================

if __name__ == "__main__":
    # 生成示例价格数据（模拟200天的上涨趋势）
    np.random.seed(42)
    dates = pd.date_range(end=pd.Timestamp.today(), periods=200)

    # 模拟价格数据：上涨趋势 + 随机波动
    trend = np.linspace(100, 150, 200)
    noise = np.random.normal(0, 2, 200).cumsum()
    close_prices = trend + noise

    sample_prices = []
    for i in range(200):
        daily_range = abs(np.random.normal(0, 1.5))
        sample_prices.append({
            "date": dates[i].strftime("%Y-%m-%d"),
            "open": close_prices[i] - daily_range/2,
            "high": close_prices[i] + daily_range,
            "low": close_prices[i] - daily_range,
            "close": close_prices[i],
            "volume": np.random.randint(10_000_000, 50_000_000)
        })

    sample_data = {
        "ticker": "AAPL",
        "prices": sample_prices
    }

    # 运行算法
    print("=" * 80)
    print("Technical Analysis 技术分析算法 Demo")
    print("=" * 80)
    print(f"\n分析股票: {sample_data['ticker']}")
    print(f"数据点数: {len(sample_data['prices'])}天\n")

    result = technical_analysis_algorithm(sample_data)

    # 打印结果
    print(f"综合交易信号: {result['signal'].upper()}")
    print(f"综合置信度: {result['confidence']}%\n")

    print("-" * 80)
    print("各策略详细信号:")
    print("-" * 80)

    strategies = result['strategy_signals']

    print(f"\n1. 趋势跟踪 (25%权重):")
    print(f"   信号: {strategies['trend_following']['signal'].upper()}")
    print(f"   置信度: {strategies['trend_following']['confidence']}%")
    print(f"   ADX: {strategies['trend_following']['metrics']['adx']:.2f}")
    print(f"   趋势强度: {strategies['trend_following']['metrics']['trend_strength']:.2f}")

    print(f"\n2. 均值回归 (20%权重):")
    print(f"   信号: {strategies['mean_reversion']['signal'].upper()}")
    print(f"   置信度: {strategies['mean_reversion']['confidence']}%")
    print(f"   Z-Score: {strategies['mean_reversion']['metrics']['z_score']:.2f}")
    print(f"   价格位置(布林带): {strategies['mean_reversion']['metrics']['price_vs_bb']:.2%}")
    print(f"   RSI(14): {strategies['mean_reversion']['metrics']['rsi_14']:.2f}")

    print(f"\n3. 动量策略 (25%权重):")
    print(f"   信号: {strategies['momentum']['signal'].upper()}")
    print(f"   置信度: {strategies['momentum']['confidence']}%")
    print(f"   1个月动量: {strategies['momentum']['metrics']['momentum_1m']:.2%}")
    print(f"   3个月动量: {strategies['momentum']['metrics']['momentum_3m']:.2%}")
    print(f"   成交量动量: {strategies['momentum']['metrics']['volume_momentum']:.2f}")

    print(f"\n4. 波动率分析 (15%权重):")
    print(f"   信号: {strategies['volatility']['signal'].upper()}")
    print(f"   置信度: {strategies['volatility']['confidence']}%")
    print(f"   历史波动率: {strategies['volatility']['metrics']['historical_volatility']:.2%}")
    print(f"   波动率体制: {strategies['volatility']['metrics']['volatility_regime']:.2f}")

    print(f"\n5. 统计套利 (15%权重):")
    print(f"   信号: {strategies['statistical_arbitrage']['signal'].upper()}")
    print(f"   置信度: {strategies['statistical_arbitrage']['confidence']}%")
    print(f"   Hurst指数: {strategies['statistical_arbitrage']['metrics']['hurst_exponent']:.2f}")
    print(f"   偏度: {strategies['statistical_arbitrage']['metrics']['skewness']:.2f}")

    print("\n" + "=" * 80)
    print(f"最终决策: {result['signal'].upper()} (置信度: {result['confidence']}%)")
    print("=" * 80)
