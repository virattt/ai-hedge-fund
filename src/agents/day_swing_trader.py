"""Day & Swing Trader agent.

Implements a price-action / Smart-Money-Concepts (SMC) trading system adapted
from the TradingView publication "Complete system for Day & Swing Traders"
(https://www.tradingview.com/chart/BTCUSDT.P/PkQJvVm4-Complete-system-for-Day-Swing-Traders/).

The published system is intraday-oriented (H4 / M15 / M5). Because this repo's
data layer is daily OHLCV, the three-timeframe structure is mapped as:

    HTF (trend)      -> weekly  (resampled from daily)
    ITF (range)      -> daily
    LTF (entry)      -> last N daily bars

Pattern-detection heuristics (order blocks, FVG, manipulation wicks, Fib
discount/premium) are simplified proxies of the visual patterns the TradingView
author describes. Final bullish/bearish/neutral judgment is delegated to the
LLM via ``call_llm`` so that SMC-style nuance is preserved.
"""

import json
from typing import Literal

import numpy as np
import pandas as pd
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import get_prices, prices_to_df
from src.utils.api_key import get_api_key_from_state
from src.utils.llm import call_llm
from src.utils.progress import progress


class DaySwingTraderSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def day_swing_trader_agent(state: AgentState, agent_id: str = "day_swing_trader_agent"):
    """SMC-style day/swing trading agent.

    Reads HTF trend, ITF range + manipulation, order blocks, FVGs, and Fib
    discount/premium zones, then asks the LLM for a Model-1 / Model-2
    judgment per the TradingView system.
    """
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")

    results: dict[str, dict] = {}
    analysis_by_ticker: dict[str, dict] = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching price data")
        prices = get_prices(ticker=ticker, start_date=start_date, end_date=end_date, api_key=api_key)
        if not prices:
            progress.update_status(agent_id, ticker, "Failed: no price data")
            continue

        df = prices_to_df(prices)
        if df.empty or len(df) < 30:
            progress.update_status(agent_id, ticker, "Failed: insufficient history")
            continue

        progress.update_status(agent_id, ticker, "Computing SMC features")
        features = build_features(df)
        analysis_by_ticker[ticker] = features

        progress.update_status(agent_id, ticker, "Generating SMC signal via LLM")
        signal = generate_day_swing_output(ticker=ticker, features=features, state=state, agent_id=agent_id)

        results[ticker] = {
            "signal": signal.signal,
            "confidence": signal.confidence,
            "reasoning": signal.reasoning,
        }
        progress.update_status(agent_id, ticker, "Done", analysis=json.dumps(results[ticker], indent=2))

    message = HumanMessage(content=json.dumps(results), name=agent_id)

    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(results, "Day & Swing Trader")

    state["data"]["analyst_signals"][agent_id] = results
    progress.update_status(agent_id, None, "Done")

    return {
        "messages": state["messages"] + [message],
        "data": state["data"],
    }


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def build_features(df: pd.DataFrame) -> dict:
    """Compute all SMC features for a given daily OHLCV DataFrame."""
    htf = _resample_weekly(df)
    itf = df
    ltf = df.tail(10)

    htf_trend = detect_htf_trend(htf)
    itf_range = detect_itf_range(itf)
    manipulation = detect_manipulation_wick(itf, itf_range)
    zone = compute_discount_premium_zone(itf_range, float(itf["close"].iloc[-1]))
    bullish_ob = detect_order_block(itf, side="bullish")
    bearish_ob = detect_order_block(itf, side="bearish")
    bullish_fvg = detect_fair_value_gap(itf, side="bullish")
    bearish_fvg = detect_fair_value_gap(itf, side="bearish")
    bullish_confirm = detect_ltf_confirmation(ltf, side="bullish")
    bearish_confirm = detect_ltf_confirmation(ltf, side="bearish")
    invalidation_bull = check_invalidation(itf, itf_range, side="bullish")
    invalidation_bear = check_invalidation(itf, itf_range, side="bearish")

    return {
        "htf_trend": htf_trend,
        "itf_range": itf_range,
        "current_price": round(float(itf["close"].iloc[-1]), 4),
        "zone": zone,
        "manipulation": manipulation,
        "order_blocks": {"bullish": bullish_ob, "bearish": bearish_ob},
        "fair_value_gaps": {"bullish": bullish_fvg, "bearish": bearish_fvg},
        "ltf_confirmation": {"bullish": bullish_confirm, "bearish": bearish_confirm},
        "invalidation": {"bullish_scenario": invalidation_bull, "bearish_scenario": invalidation_bear},
    }


def _resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    agg = df.resample("W").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    return agg.dropna()


def detect_htf_trend(htf: pd.DataFrame, ema_span: int = 20) -> dict:
    """Higher-timeframe trend via EMA slope + price location + swing structure."""
    if len(htf) < max(ema_span, 6):
        return {"direction": "neutral", "ema_slope": 0.0, "above_ema": None, "structure": "insufficient"}

    close = htf["close"]
    ema = close.ewm(span=ema_span, adjust=False).mean()
    ema_slope = float((ema.iloc[-1] - ema.iloc[-5]) / max(abs(ema.iloc[-5]), 1e-9))
    above_ema = bool(close.iloc[-1] > ema.iloc[-1])

    recent = htf.tail(6)
    higher_highs = bool(recent["high"].iloc[-1] > recent["high"].iloc[-3] > recent["high"].iloc[-5])
    higher_lows = bool(recent["low"].iloc[-1] > recent["low"].iloc[-3] > recent["low"].iloc[-5])
    lower_highs = bool(recent["high"].iloc[-1] < recent["high"].iloc[-3] < recent["high"].iloc[-5])
    lower_lows = bool(recent["low"].iloc[-1] < recent["low"].iloc[-3] < recent["low"].iloc[-5])

    if ema_slope > 0.005 and above_ema and (higher_highs or higher_lows):
        direction = "bullish"
    elif ema_slope < -0.005 and not above_ema and (lower_highs or lower_lows):
        direction = "bearish"
    else:
        direction = "neutral"

    return {
        "direction": direction,
        "ema_slope": round(ema_slope, 5),
        "above_ema": above_ema,
        "structure": "HH_HL" if (higher_highs or higher_lows) else ("LH_LL" if (lower_highs or lower_lows) else "mixed"),
    }


def detect_itf_range(itf: pd.DataFrame, lookback: int = 20) -> dict:
    """Rolling range on the ITF: high/low/mid over the lookback window."""
    window = itf.tail(lookback)
    high = float(window["high"].max())
    low = float(window["low"].min())
    mid = (high + low) / 2.0
    width = high - low
    return {"high": round(high, 4), "low": round(low, 4), "mid": round(mid, 4), "width": round(width, 4), "lookback": lookback}


def detect_manipulation_wick(itf: pd.DataFrame, range_bounds: dict) -> dict:
    """Did the most recent ITF bar stop-hunt the range and close back inside?"""
    last = itf.iloc[-1]
    high = range_bounds["high"]
    low = range_bounds["low"]
    width = max(range_bounds["width"], 1e-9)

    # Bullish manipulation: wicked below range low, closed back above
    if last["low"] < low and last["close"] > low:
        strength = (low - float(last["low"])) / width
        return {"side": "bullish", "wick_strength": round(float(strength), 4), "wick_level": round(float(last["low"]), 4)}

    # Bearish manipulation: wicked above range high, closed back below
    if last["high"] > high and last["close"] < high:
        strength = (float(last["high"]) - high) / width
        return {"side": "bearish", "wick_strength": round(float(strength), 4), "wick_level": round(float(last["high"]), 4)}

    return {"side": None, "wick_strength": 0.0, "wick_level": None}


def detect_order_block(itf: pd.DataFrame, side: str, lookback: int = 30) -> dict | None:
    """Last opposing candle before the most recent impulsive move in ``side`` direction.

    Bullish OB = last down-candle before an up-impulse.
    Bearish OB = last up-candle before a down-impulse.
    """
    window = itf.tail(lookback).reset_index(drop=True)
    if len(window) < 4:
        return None

    closes = window["close"].to_numpy()
    opens = window["open"].to_numpy()
    bodies = closes - opens
    atr = float(np.mean(np.abs(bodies[-20:]))) if len(bodies) >= 20 else float(np.mean(np.abs(bodies)))
    impulse_threshold = max(atr * 1.5, 1e-9)

    for i in range(len(window) - 1, 0, -1):
        body = bodies[i]
        if side == "bullish" and body > impulse_threshold:
            for j in range(i - 1, -1, -1):
                if bodies[j] < 0:
                    return {
                        "high": round(float(window["high"].iloc[j]), 4),
                        "low": round(float(window["low"].iloc[j]), 4),
                        "age_bars": int(len(window) - 1 - j),
                    }
        if side == "bearish" and body < -impulse_threshold:
            for j in range(i - 1, -1, -1):
                if bodies[j] > 0:
                    return {
                        "high": round(float(window["high"].iloc[j]), 4),
                        "low": round(float(window["low"].iloc[j]), 4),
                        "age_bars": int(len(window) - 1 - j),
                    }
    return None


def detect_fair_value_gap(itf: pd.DataFrame, side: str, lookback: int = 30) -> dict | None:
    """Three-bar FVG. Bullish: bar[i-2].high < bar[i].low. Bearish: bar[i-2].low > bar[i].high."""
    window = itf.tail(lookback).reset_index(drop=True)
    if len(window) < 3:
        return None

    current_price = float(window["close"].iloc[-1])
    latest: dict | None = None
    for i in range(2, len(window)):
        h_prev = float(window["high"].iloc[i - 2])
        l_prev = float(window["low"].iloc[i - 2])
        h_curr = float(window["high"].iloc[i])
        l_curr = float(window["low"].iloc[i])
        if side == "bullish" and h_prev < l_curr:
            gap_low, gap_high = h_prev, l_curr
            inside = bool(gap_low <= current_price <= gap_high)
            latest = {"gap_low": round(gap_low, 4), "gap_high": round(gap_high, 4), "age_bars": int(len(window) - 1 - i), "price_inside": inside}
        elif side == "bearish" and l_prev > h_curr:
            gap_low, gap_high = h_curr, l_prev
            inside = bool(gap_low <= current_price <= gap_high)
            latest = {"gap_low": round(gap_low, 4), "gap_high": round(gap_high, 4), "age_bars": int(len(window) - 1 - i), "price_inside": inside}
    return latest


def compute_discount_premium_zone(range_bounds: dict, current_price: float) -> dict:
    """Locate price within the range and compute the 61.8%-80% Fib sub-zones."""
    low = range_bounds["low"]
    high = range_bounds["high"]
    span = max(high - low, 1e-9)
    position = (current_price - low) / span  # 0 = at low, 1 = at high

    discount_618 = low + span * (1 - 0.618)
    discount_80 = low + span * (1 - 0.80)
    premium_618 = low + span * 0.618
    premium_80 = low + span * 0.80

    if position < 0.5:
        label = "discount"
    elif position > 0.5:
        label = "premium"
    else:
        label = "equilibrium"

    in_discount_zone = bool(discount_80 <= current_price <= discount_618)
    in_premium_zone = bool(premium_618 <= current_price <= premium_80)

    return {
        "label": label,
        "position_in_range": round(float(position), 4),
        "discount_zone_61_80": [round(discount_80, 4), round(discount_618, 4)],
        "premium_zone_61_80": [round(premium_618, 4), round(premium_80, 4)],
        "in_discount_zone": in_discount_zone,
        "in_premium_zone": in_premium_zone,
    }


def detect_ltf_confirmation(ltf: pd.DataFrame, side: str) -> dict:
    """Simplified LTF confirmation.

    Bullish: most recent bar closes above the high of the most recent prior
    down-candle. Bearish: mirror.
    """
    if len(ltf) < 3:
        return {"confirmed": False, "reference_bar": None}

    closes = ltf["close"].to_numpy()
    opens = ltf["open"].to_numpy()
    highs = ltf["high"].to_numpy()
    lows = ltf["low"].to_numpy()

    last_close = float(closes[-1])
    for j in range(len(ltf) - 2, -1, -1):
        is_down = closes[j] < opens[j]
        is_up = closes[j] > opens[j]
        if side == "bullish" and is_down:
            confirmed = bool(last_close > float(highs[j]))
            return {"confirmed": confirmed, "reference_bar_high": round(float(highs[j]), 4), "age_bars": int(len(ltf) - 1 - j)}
        if side == "bearish" and is_up:
            confirmed = bool(last_close < float(lows[j]))
            return {"confirmed": confirmed, "reference_bar_low": round(float(lows[j]), 4), "age_bars": int(len(ltf) - 1 - j)}

    return {"confirmed": False, "reference_bar": None}


def check_invalidation(itf: pd.DataFrame, range_bounds: dict, side: str) -> dict:
    """The scenario is invalidated if an ITF candle closes decisively outside the range in the wrong direction."""
    last_close = float(itf["close"].iloc[-1])
    high = range_bounds["high"]
    low = range_bounds["low"]
    if side == "bullish":
        invalidated = bool(last_close < low)
    else:
        invalidated = bool(last_close > high)
    return {"invalidated": invalidated, "last_close": round(last_close, 4)}


# ---------------------------------------------------------------------------
# LLM judgment
# ---------------------------------------------------------------------------

def generate_day_swing_output(
    ticker: str,
    features: dict,
    state: AgentState,
    agent_id: str,
) -> DaySwingTraderSignal:
    """Turn the SMC feature bundle into a bullish/bearish/neutral signal via LLM."""
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a Day & Swing Trader AI agent applying a Smart-Money-Concepts (SMC) price-action system.

                Methodology (top-down, 3 timeframes):
                - HTF sets directional bias (trend).
                - ITF defines the range to trade around.
                - LTF provides confirmation for entries.

                Valid setups:
                - Long Model 1: HTF bullish + ITF range established + bullish manipulation wick below range low into a bullish order block + LTF bullish confirmation. Target = 50% of range.
                - Long Model 2: after Model 1 plays out, pullback into discount zone (61.8%-80%) at a key level + LTF confirmation. Target = full range.
                - Short Model 1 / 2: mirror of the above, operating in the premium zone.

                Invalidation: if an ITF candle closes opposite to the scenario's range bound, the setup is invalidated.

                Rules for grading the signal:
                - Require HTF trend alignment with the direction. If HTF is neutral, default toward neutral unless the manipulation + order block + LTF confirmation are all present.
                - Confidence should scale with the number of confluences met (trend, zone, manipulation, order block, FVG, LTF confirmation) and be lowered heavily if invalidation is triggered.
                - Prefer "neutral" when no valid Model-1 or Model-2 pattern is present.
                - Output JSON with: signal (bullish|bearish|neutral), confidence (0-100 float), reasoning (string citing which Model applied, which confluences fired, and the key levels).
                """,
            ),
            (
                "human",
                """Evaluate this SMC setup and return a trading signal.

                Ticker: {ticker}

                SMC Features:
                {features}

                Return JSON only:
                {{
                  "signal": "bullish" | "bearish" | "neutral",
                  "confidence": float (0-100),
                  "reasoning": "string"
                }}
                """,
            ),
        ]
    )

    prompt = template.invoke({"ticker": ticker, "features": json.dumps(features, indent=2, default=str)})

    def default_signal():
        return DaySwingTraderSignal(signal="neutral", confidence=0.0, reasoning="Error in analysis, defaulting to neutral")

    return call_llm(
        prompt=prompt,
        pydantic_model=DaySwingTraderSignal,
        agent_name=agent_id,
        state=state,
        default_factory=default_signal,
    )
