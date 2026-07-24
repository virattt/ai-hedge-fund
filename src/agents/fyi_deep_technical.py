"""FYI Deep Technical Agent — exhaustive multi-indicator TA, informational only."""
import json
import math

import numpy as np
import pandas as pd
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.agents.technicals import (
    calculate_atr,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_rsi,
    safe_float,
)
from src.graph.state import AgentState
from src.tools.api import get_prices, prices_to_df
from src.utils.api_key import get_api_key_from_state
from src.utils.llm import call_llm
from src.utils.progress import progress


class DeepTechnicalOutput(BaseModel):
    summary: str = Field(description="3 sentences of deep TA narrative")
    key_levels: str = Field(description="1 sentence on critical support/resistance levels")
    pattern_detected: str = Field(description="1 sentence on any chart pattern or structure detected")


def _sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n).mean()


def _macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _stochastic(df: pd.DataFrame, k=14, d=3):
    low_min = df["low"].rolling(k).min()
    high_max = df["high"].rolling(k).max()
    stoch_k = 100 * (df["close"] - low_min) / (high_max - low_min + 1e-10)
    stoch_d = stoch_k.rolling(d).mean()
    return stoch_k, stoch_d


def _cci(df: pd.DataFrame, n=20):
    typical = (df["high"] + df["low"] + df["close"]) / 3
    sma_tp = typical.rolling(n).mean()
    mean_dev = typical.rolling(n).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    return (typical - sma_tp) / (0.015 * mean_dev + 1e-10)


def _williams_r(df: pd.DataFrame, n=14):
    high_max = df["high"].rolling(n).max()
    low_min = df["low"].rolling(n).min()
    return -100 * (high_max - df["close"]) / (high_max - low_min + 1e-10)


def _obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["close"].diff().fillna(0))
    return (direction * df["volume"]).cumsum()


def _fibonacci_levels(high: float, low: float) -> dict:
    diff = high - low
    return {
        "0%": round(low, 2),
        "23.6%": round(low + 0.236 * diff, 2),
        "38.2%": round(low + 0.382 * diff, 2),
        "50%": round(low + 0.500 * diff, 2),
        "61.8%": round(low + 0.618 * diff, 2),
        "78.6%": round(low + 0.786 * diff, 2),
        "100%": round(high, 2),
    }


def _pivot_points(high: float, low: float, close: float) -> dict:
    p = (high + low + close) / 3
    r1 = 2 * p - low
    s1 = 2 * p - high
    r2 = p + (high - low)
    s2 = p - (high - low)
    return {
        "P": round(p, 2),
        "R1": round(r1, 2), "R2": round(r2, 2),
        "S1": round(s1, 2), "S2": round(s2, 2),
    }


def fyi_deep_technical_agent(state: AgentState, agent_id: str = "fyi_deep_technical_agent"):
    """
    FYI-only deep technical analysis with 15+ indicators across multiple timeframes.
    Does NOT influence trading decisions.
    """
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")

    deep_ta = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Loading price data")

        prices = get_prices(ticker, start_date, end_date, api_key=api_key)
        if not prices:
            deep_ta[ticker] = {"signal": "neutral", "confidence": 50, "summary": "No price data available.",
                               "key_levels": "", "pattern_detected": ""}
            continue

        df = prices_to_df(prices).copy()
        if len(df) < 30:
            deep_ta[ticker] = {"signal": "neutral", "confidence": 50, "summary": "Insufficient price history.",
                               "key_levels": "", "pattern_detected": ""}
            continue

        progress.update_status(agent_id, ticker, "Computing indicators")
        close = df["close"]
        cur = float(close.iloc[-1])

        # --- Moving Averages ---
        sma20 = _sma(close, 20); sma50 = _sma(close, 50)
        sma100 = _sma(close, 100); sma200 = _sma(close, 200)
        ema8 = calculate_ema(df, 8); ema21 = calculate_ema(df, 21)

        above_sma20 = cur > safe_float(sma20.iloc[-1])
        above_sma50 = cur > safe_float(sma50.iloc[-1])
        above_sma200 = cur > safe_float(sma200.iloc[-1])
        golden_cross = (safe_float(sma50.iloc[-1]) > safe_float(sma200.iloc[-1])
                        and len(sma50.dropna()) > 1 and len(sma200.dropna()) > 1)
        death_cross = (safe_float(sma50.iloc[-1]) < safe_float(sma200.iloc[-1])
                       and not golden_cross)

        # --- Momentum ---
        rsi14 = calculate_rsi(df, 14); rsi7 = calculate_rsi(df, 7)
        macd_line, macd_sig, macd_hist = _macd(close)
        stoch_k, stoch_d = _stochastic(df)
        cci20 = _cci(df)
        willr = _williams_r(df)

        rsi14_val = safe_float(rsi14.iloc[-1])
        macd_bull = safe_float(macd_line.iloc[-1]) > safe_float(macd_sig.iloc[-1])
        macd_cross_up = (safe_float(macd_line.iloc[-1]) > safe_float(macd_sig.iloc[-1])
                         and safe_float(macd_line.iloc[-2]) <= safe_float(macd_sig.iloc[-2]))
        stoch_k_val = safe_float(stoch_k.iloc[-1]); stoch_d_val = safe_float(stoch_d.iloc[-1])
        cci_val = safe_float(cci20.iloc[-1])
        willr_val = safe_float(willr.iloc[-1])

        # --- Volatility ---
        bb_upper, bb_lower = calculate_bollinger_bands(df, 20)
        bb_mid = _sma(close, 20)
        bb_pos = (cur - safe_float(bb_lower.iloc[-1])) / max(
            safe_float(bb_upper.iloc[-1]) - safe_float(bb_lower.iloc[-1]), 1e-10)
        bb_width = (safe_float(bb_upper.iloc[-1]) - safe_float(bb_lower.iloc[-1])) / max(safe_float(bb_mid.iloc[-1]), 1e-10)

        atr14 = calculate_atr(df, 14)
        atr_pct = safe_float(atr14.iloc[-1]) / cur * 100 if cur > 0 else 0

        hist_vol = close.pct_change().rolling(21).std() * math.sqrt(252)
        hist_vol_val = safe_float(hist_vol.iloc[-1]) * 100

        # --- Volume ---
        vol_avg20 = df["volume"].rolling(20).mean()
        vol_ratio = safe_float(df["volume"].iloc[-1]) / max(safe_float(vol_avg20.iloc[-1]), 1)
        obv_series = _obv(df)
        obv_trend_bull = safe_float(obv_series.iloc[-1]) > safe_float(obv_series.iloc[-5])

        # --- 52-week range ---
        window_252 = df.iloc[-252:] if len(df) >= 252 else df
        high_52w = float(window_252["high"].max())
        low_52w = float(window_252["low"].min())
        range_pos_52w = (cur - low_52w) / max(high_52w - low_52w, 1e-10)

        # --- Fibonacci & Pivot ---
        fib = _fibonacci_levels(high_52w, low_52w)
        prev_day = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]
        pivots = _pivot_points(float(prev_day["high"]), float(prev_day["low"]), float(prev_day["close"]))

        # --- Pattern detection: higher highs / lower lows ---
        recent = df.iloc[-20:]
        highs = recent["high"].values; lows = recent["low"].values
        hh = all(highs[i] >= highs[i - 1] for i in range(1, len(highs)))
        ll = all(lows[i] <= lows[i - 1] for i in range(1, len(lows)))
        hl = all(lows[i] >= lows[i - 1] for i in range(1, len(lows)))  # higher lows = uptrend base
        lh = all(highs[i] <= highs[i - 1] for i in range(1, len(highs)))  # lower highs = downtrend

        # --- Composite scoring ---
        bull_pts = sum([
            above_sma20, above_sma50, above_sma200,
            golden_cross,
            macd_bull, macd_cross_up,
            rsi14_val > 50, rsi14_val < 70,
            stoch_k_val > stoch_d_val,
            cci_val > 0, cci_val < 100,
            willr_val > -80,
            bb_pos > 0.4,
            vol_ratio > 1.1 and above_sma20,
            obv_trend_bull,
            range_pos_52w > 0.5,
            hh and hl,
        ])
        bear_pts = sum([
            not above_sma20, not above_sma50, not above_sma200,
            death_cross,
            not macd_bull,
            rsi14_val < 50, rsi14_val > 70,
            stoch_k_val < stoch_d_val,
            cci_val < 0, cci_val > 100,
            willr_val < -80,
            bb_pos < 0.3,
            vol_ratio > 1.1 and not above_sma20,
            not obv_trend_bull,
            range_pos_52w < 0.3,
            ll and lh,
        ])
        total = bull_pts + bear_pts
        net = (bull_pts - bear_pts) / max(total, 1)
        if net > 0.15:
            signal = "bullish"; confidence = min(int(50 + net * 50), 95)
        elif net < -0.15:
            signal = "bearish"; confidence = min(int(50 + abs(net) * 50), 95)
        else:
            signal = "neutral"; confidence = 50

        metrics_for_llm = {
            "ticker": ticker, "current_price": round(cur, 2),
            "sma_20": round(safe_float(sma20.iloc[-1]), 2),
            "sma_50": round(safe_float(sma50.iloc[-1]), 2),
            "sma_200": round(safe_float(sma200.iloc[-1]), 2),
            "ema_8": round(safe_float(ema8.iloc[-1]), 2),
            "ema_21": round(safe_float(ema21.iloc[-1]), 2),
            "above_sma20": above_sma20, "above_sma50": above_sma50, "above_sma200": above_sma200,
            "golden_cross": golden_cross, "death_cross": death_cross,
            "rsi_14": round(rsi14_val, 1), "rsi_7": round(safe_float(rsi7.iloc[-1]), 1),
            "macd_line": round(safe_float(macd_line.iloc[-1]), 4),
            "macd_signal": round(safe_float(macd_sig.iloc[-1]), 4),
            "macd_histogram": round(safe_float(macd_hist.iloc[-1]), 4),
            "macd_bullish": macd_bull, "macd_crossover": macd_cross_up,
            "stoch_k": round(stoch_k_val, 1), "stoch_d": round(stoch_d_val, 1),
            "cci_20": round(cci_val, 1),
            "williams_r_14": round(willr_val, 1),
            "bb_position_0_to_1": round(bb_pos, 3), "bb_width": round(bb_width, 4),
            "atr_pct": round(atr_pct, 2),
            "hist_vol_annualized_pct": round(hist_vol_val, 1),
            "volume_ratio_vs_20d_avg": round(vol_ratio, 2),
            "obv_trend_bullish": obv_trend_bull,
            "52w_high": round(high_52w, 2), "52w_low": round(low_52w, 2),
            "52w_range_position_0_to_1": round(range_pos_52w, 3),
            "fibonacci_levels": fib,
            "daily_pivot_points": pivots,
            "pattern": ("higher_highs_higher_lows" if hh and hl else
                        "lower_lows_lower_highs" if ll and lh else "mixed"),
            "bull_score": bull_pts, "bear_score": bear_pts,
        }

        progress.update_status(agent_id, ticker, "Generating deep TA narrative")

        template = ChatPromptTemplate.from_messages([
            ("system",
             "You are a professional technical analyst with 20 years of experience. "
             "Given comprehensive indicator data, write a deep, specific technical analysis. "
             "summary = 3 sentences (trend structure, momentum state, what to watch). "
             "key_levels = 1 sentence naming exact price levels (support/resistance/pivots). "
             "pattern_detected = 1 sentence on the dominant chart structure or pattern. "
             "Be precise with numbers. No filler."),
            ("human", "Technical data:\n{metrics}\n\nsignal={signal}, confidence={confidence}"),
        ])

        prompt = template.invoke({
            "metrics": json.dumps(metrics_for_llm, indent=2),
            "signal": signal, "confidence": confidence,
        })

        out = call_llm(prompt=prompt, pydantic_model=DeepTechnicalOutput, agent_name=agent_id, state=state)

        deep_ta[ticker] = {
            "signal": signal,
            "confidence": confidence,
            "summary": (out.summary if out else "Deep TA unavailable."),
            "key_levels": (out.key_levels if out else ""),
            "pattern_detected": (out.pattern_detected if out else ""),
            "metrics": metrics_for_llm,
            "reasoning": (out.summary if out else ""),
        }
        progress.update_status(agent_id, ticker, "Done")

    message = HumanMessage(content=json.dumps(deep_ta, default=str), name=agent_id)
    state["data"]["analyst_signals"][agent_id] = deep_ta
    progress.update_status(agent_id, None, "Done")
    return {"messages": state["messages"] + [message], "data": data}
