"""
Nassim Taleb Antifragile Volatility Agent

Evaluates long strangle positions through a Talebian lens:
- Does NOT recommend directional buy/short on the underlying
- Instead scores each ticker for long-strangle attractiveness based on:

1. Implied-vs-Realised Vol Gap  – Is vol cheap? (IV rank as proxy)
2. Tail Thickness (Kurtosis)    – Are fat tails present in the return distribution?
3. Vega-per-Dollar Efficiency   – How much vega exposure does $1 of premium buy?
4. Convexity Score              – Asymmetric payoff potential (skewness of returns)
5. Fragility / Antifragility    – Does the asset benefit from disorder?

Output: a strangle recommendation with signal in {strong_buy_vol, buy_vol, neutral, sell_vol}
"""

from __future__ import annotations

import math
import json
from datetime import datetime, timedelta
from typing_extensions import Literal

import numpy as np
from scipy import stats as sp_stats

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import get_prices, get_company_news, get_insider_trades, prices_to_df
from src.utils.llm import call_llm
from src.utils.progress import progress
from src.utils.api_key import get_api_key_from_state


# ---------------------------------------------------------------------------
# Pydantic output schema
# ---------------------------------------------------------------------------

class TalebStrangleSignal(BaseModel):
    signal: Literal["strong_buy_vol", "buy_vol", "neutral", "sell_vol"]
    confidence: float          # 0–100
    reasoning: str
    iv_rank_proxy: float       # 0–100, estimated IV rank
    kurtosis: float            # excess kurtosis of returns
    skewness: float            # skewness of returns
    vega_efficiency: float     # relative vega-per-dollar score
    convexity_score: float     # 0–10
    antifragility_score: float # 0–10


# ---------------------------------------------------------------------------
# Main agent entry-point
# ---------------------------------------------------------------------------

def nassim_taleb_agent(state: AgentState, agent_id: str = "nassim_taleb_agent"):
    """Evaluate long strangle vega attractiveness using Nassim Taleb's framework."""

    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    data = state["data"]
    end_date: str = data["end_date"]
    tickers: list[str] = data["tickers"]

    start_date = (datetime.fromisoformat(end_date) - timedelta(days=365)).date().isoformat()

    analysis_data: dict[str, dict] = {}
    taleb_analysis: dict[str, dict] = {}

    for ticker in tickers:
        # ==============================================================
        # Fetch data
        # ==============================================================
        progress.update_status(agent_id, ticker, "Fetching prices")
        prices = get_prices(ticker, start_date, end_date, api_key=api_key)

        progress.update_status(agent_id, ticker, "Fetching company news")
        news = get_company_news(ticker, end_date=end_date, start_date=start_date, limit=100)

        progress.update_status(agent_id, ticker, "Fetching insider trades")
        insider_trades = get_insider_trades(ticker, end_date=end_date, start_date=start_date)

        # ==============================================================
        # Run the five Talebian sub-analyses
        # ==============================================================
        progress.update_status(agent_id, ticker, "Analysing IV rank proxy")
        iv_analysis = _iv_rank_proxy_analysis(prices)

        progress.update_status(agent_id, ticker, "Analysing tail thickness")
        tail_analysis = _tail_thickness_analysis(prices)

        progress.update_status(agent_id, ticker, "Analysing vega efficiency")
        vega_analysis = _vega_efficiency_analysis(prices)

        progress.update_status(agent_id, ticker, "Analysing convexity")
        convexity_analysis = _convexity_analysis(prices, news, insider_trades)

        progress.update_status(agent_id, ticker, "Analysing antifragility")
        antifragility_analysis = _antifragility_analysis(prices)

        # ==============================================================
        # Aggregate
        # ==============================================================
        total_score = (
            iv_analysis["score"]
            + tail_analysis["score"]
            + vega_analysis["score"]
            + convexity_analysis["score"]
            + antifragility_analysis["score"]
        )
        max_score = (
            iv_analysis["max_score"]
            + tail_analysis["max_score"]
            + vega_analysis["max_score"]
            + convexity_analysis["max_score"]
            + antifragility_analysis["max_score"]
        )

        if max_score == 0:
            signal = "neutral"
        elif total_score >= 0.75 * max_score:
            signal = "strong_buy_vol"
        elif total_score >= 0.55 * max_score:
            signal = "buy_vol"
        elif total_score >= 0.35 * max_score:
            signal = "neutral"
        else:
            signal = "sell_vol"

        analysis_data[ticker] = {
            "signal": signal,
            "score": total_score,
            "max_score": max_score,
            "iv_rank_proxy": iv_analysis,
            "tail_thickness": tail_analysis,
            "vega_efficiency": vega_analysis,
            "convexity": convexity_analysis,
            "antifragility": antifragility_analysis,
        }

        progress.update_status(agent_id, ticker, "Generating LLM output")
        taleb_output = _generate_taleb_output(
            ticker=ticker,
            analysis_data=analysis_data,
            state=state,
            agent_id=agent_id,
        )

        taleb_analysis[ticker] = {
            "signal": taleb_output.signal,
            "confidence": taleb_output.confidence,
            "reasoning": taleb_output.reasoning,
            "iv_rank_proxy": taleb_output.iv_rank_proxy,
            "kurtosis": taleb_output.kurtosis,
            "skewness": taleb_output.skewness,
            "vega_efficiency": taleb_output.vega_efficiency,
            "convexity_score": taleb_output.convexity_score,
            "antifragility_score": taleb_output.antifragility_score,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=taleb_output.reasoning)

    # ------------------------------------------------------------------
    # Return to the graph
    # ------------------------------------------------------------------
    message = HumanMessage(content=json.dumps(taleb_analysis), name=agent_id)

    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(taleb_analysis, "Nassim Taleb Antifragile Vol Agent")

    state["data"]["analyst_signals"][agent_id] = taleb_analysis

    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}


###############################################################################
# 1. IV Rank Proxy — Is Volatility Cheap?
#
#    We don't have real IV data, so we approximate IV rank by looking at where
#    current realised vol sits relative to its own 1-year range.
#    Low IV rank = cheap strangles = Taleb likes it.
###############################################################################

def _iv_rank_proxy_analysis(prices):
    max_score = 5
    score = 0
    details: list[str] = []

    if not prices or len(prices) < 60:
        details.append("Insufficient price data for IV rank proxy")
        return {"score": score, "max_score": max_score, "details": "; ".join(details), "iv_rank": 50.0}

    df = prices_to_df(prices)
    returns = df["close"].pct_change().dropna()

    # Rolling 20-day realised vol over the full period
    rolling_vol = returns.rolling(20).std() * math.sqrt(252)
    rolling_vol = rolling_vol.dropna()

    if len(rolling_vol) < 20:
        details.append("Not enough rolling vol data")
        return {"score": score, "max_score": max_score, "details": "; ".join(details), "iv_rank": 50.0}

    current_vol = rolling_vol.iloc[-1]
    vol_min = rolling_vol.min()
    vol_max = rolling_vol.max()

    if vol_max - vol_min > 0:
        iv_rank = (current_vol - vol_min) / (vol_max - vol_min) * 100
    else:
        iv_rank = 50.0

    details.append(f"Current 20d realised vol: {current_vol:.1%}")
    details.append(f"1Y vol range: {vol_min:.1%} – {vol_max:.1%}")
    details.append(f"IV rank proxy: {iv_rank:.0f}%")

    # Low IV rank = cheap vol = high score for buying strangles
    if iv_rank < 20:
        score += 5
        details.append("Extremely cheap vol — ideal strangle entry")
    elif iv_rank < 35:
        score += 4
        details.append("Cheap vol — attractive for long strangles")
    elif iv_rank < 50:
        score += 3
        details.append("Below-average vol — reasonable entry")
    elif iv_rank < 70:
        score += 1
        details.append("Above-average vol — strangles getting expensive")
    else:
        score += 0
        details.append("Expensive vol — avoid buying strangles, premiums inflated")

    return {
        "score": score,
        "max_score": max_score,
        "details": "; ".join(details),
        "iv_rank": round(iv_rank, 2),
    }


###############################################################################
# 2. Tail Thickness (Kurtosis) — Are Fat Tails Present?
#
#    Excess kurtosis > 0 means fatter tails than a normal distribution.
#    Higher kurtosis = more tail events = strangles pay off more often than
#    Black-Scholes predicts. This is the core of Taleb's edge.
###############################################################################

def _tail_thickness_analysis(prices):
    max_score = 5
    score = 0
    details: list[str] = []

    if not prices or len(prices) < 60:
        details.append("Insufficient data for kurtosis analysis")
        return {"score": score, "max_score": max_score, "details": "; ".join(details),
                "kurtosis": 0.0, "skewness": 0.0}

    df = prices_to_df(prices)
    returns = df["close"].pct_change().dropna().values

    excess_kurtosis = float(sp_stats.kurtosis(returns, fisher=True))
    skewness = float(sp_stats.skew(returns))

    details.append(f"Excess kurtosis: {excess_kurtosis:.2f}")
    details.append(f"Skewness: {skewness:.2f}")

    # Count actual tail events (|return| > 2 sigma)
    sigma = np.std(returns)
    tail_events = np.sum(np.abs(returns) > 2 * sigma)
    expected_tail_events = len(returns) * 0.0456  # ~4.56% under normal
    tail_ratio = tail_events / max(expected_tail_events, 1)

    details.append(f"Tail events (>2σ): {tail_events} vs {expected_tail_events:.1f} expected")
    details.append(f"Tail ratio: {tail_ratio:.2f}x normal")

    # Score: higher kurtosis and more tail events = better for strangles
    if excess_kurtosis > 5:
        score += 3
        details.append("Extremely fat tails — strangles massively underpriced by Black-Scholes")
    elif excess_kurtosis > 2:
        score += 2
        details.append("Fat tails — strangles likely underpriced")
    elif excess_kurtosis > 0.5:
        score += 1
        details.append("Mild fat tails")
    else:
        details.append("Thin tails — normal distribution adequate, no kurtosis edge")

    if tail_ratio > 2.0:
        score += 2
        details.append("Observed tail events far exceed normal expectation")
    elif tail_ratio > 1.3:
        score += 1
        details.append("Observed tails moderately exceed expectation")

    return {
        "score": score,
        "max_score": max_score,
        "details": "; ".join(details),
        "kurtosis": round(excess_kurtosis, 4),
        "skewness": round(skewness, 4),
        "tail_ratio": round(tail_ratio, 4),
    }


###############################################################################
# 3. Vega Efficiency — How Much Vega Does $1 of Premium Buy?
#
#    We estimate ATM strangle cost from realised vol and current price,
#    then compute how much vega exposure (sensitivity to a 1-point vol
#    increase) you get per dollar. Higher = better.
#
#    Uses simplified Black-Scholes vega approximation:
#      vega ≈ S * sqrt(T) * N'(d1) ≈ S * sqrt(T) * 0.3989 (for ATM)
#      strangle_cost ≈ 2 * S * σ * sqrt(T / 2π)
###############################################################################

def _vega_efficiency_analysis(prices):
    max_score = 4
    score = 0
    details: list[str] = []

    if not prices or len(prices) < 30:
        details.append("Insufficient data for vega analysis")
        return {"score": score, "max_score": max_score, "details": "; ".join(details),
                "vega_per_dollar": 0.0}

    df = prices_to_df(prices)
    returns = df["close"].pct_change().dropna()

    S = df["close"].iloc[-1]
    sigma = returns.std() * math.sqrt(252)  # annualised vol
    T = 7 / 365  # 1-week expiry (matching the strangle strategy)

    # ATM strangle cost approximation
    strangle_cost = 2 * S * sigma * math.sqrt(T / (2 * math.pi))

    # Vega of ATM strangle (call vega + put vega ≈ 2 * S * sqrt(T) * N'(0))
    vega = 2 * S * math.sqrt(T) * 0.3989  # N'(0) = 1/sqrt(2π) ≈ 0.3989

    vega_per_dollar = vega / strangle_cost if strangle_cost > 0 else 0

    details.append(f"Spot: ${S:.2f}, σ_annual: {sigma:.1%}")
    details.append(f"Est. 1-week ATM strangle cost: ${strangle_cost:.2f}")
    details.append(f"Est. strangle vega: ${vega:.4f}")
    details.append(f"Vega per $1 premium: {vega_per_dollar:.2f}")

    # High vega-per-dollar = you get a lot of vol exposure cheaply
    if vega_per_dollar > 8:
        score += 4
        details.append("Exceptional vega efficiency — maximum vol exposure per dollar")
    elif vega_per_dollar > 5:
        score += 3
        details.append("Strong vega efficiency")
    elif vega_per_dollar > 3:
        score += 2
        details.append("Adequate vega efficiency")
    elif vega_per_dollar > 1.5:
        score += 1
        details.append("Mediocre vega efficiency")
    else:
        details.append("Poor vega efficiency — premium too expensive relative to vega")

    return {
        "score": score,
        "max_score": max_score,
        "details": "; ".join(details),
        "vega_per_dollar": round(vega_per_dollar, 4),
        "strangle_cost": round(strangle_cost, 4),
        "spot": round(S, 2),
        "annual_vol": round(sigma, 4),
    }


###############################################################################
# 4. Convexity Score — Asymmetric Payoff Potential
#
#    Measures how much the asset's return distribution favours large moves
#    (which benefit strangles) over small ones (which decay premium).
#    Combines:
#      - Ratio of max absolute move to average move (convexity ratio)
#      - Frequency of "gap" days (|return| > 3%)
#      - News catalyst density (potential for future gaps)
###############################################################################

def _convexity_analysis(prices, news, insider_trades):
    max_score = 3
    score = 0
    details: list[str] = []

    if not prices or len(prices) < 60:
        details.append("Insufficient data for convexity analysis")
        return {"score": score, "max_score": max_score, "details": "; ".join(details),
                "convexity_ratio": 0.0}

    df = prices_to_df(prices)
    returns = df["close"].pct_change().dropna().values

    abs_returns = np.abs(returns)
    avg_move = abs_returns.mean()
    max_move = abs_returns.max()
    convexity_ratio = max_move / avg_move if avg_move > 0 else 0

    # Gap days: |return| > 3%
    gap_days = np.sum(abs_returns > 0.03)
    gap_frequency = gap_days / len(returns)

    details.append(f"Avg daily |move|: {avg_move:.2%}")
    details.append(f"Max daily |move|: {max_move:.2%}")
    details.append(f"Convexity ratio (max/avg): {convexity_ratio:.1f}x")
    details.append(f"Gap days (>3%): {gap_days} ({gap_frequency:.1%} of days)")

    # News catalyst density
    catalyst_density = 0
    if news:
        catalyst_density = len(news) / 12  # normalise to per-month
        details.append(f"News catalysts: {len(news)} items ({catalyst_density:.1f}/month)")

    # Score
    if convexity_ratio > 8:
        score += 2
        details.append("High convexity — large moves vastly exceed average")
    elif convexity_ratio > 5:
        score += 1
        details.append("Moderate convexity")

    if gap_frequency > 0.05:
        score += 1
        details.append("Frequent gap days — strangles hit payoff zone regularly")
    elif gap_frequency > 0.02:
        pass  # no bonus, no penalty

    return {
        "score": score,
        "max_score": max_score,
        "details": "; ".join(details),
        "convexity_ratio": round(convexity_ratio, 4),
        "gap_frequency": round(gap_frequency, 4),
        "catalyst_density": round(catalyst_density, 2),
    }


###############################################################################
# 5. Antifragility Score — Does the Asset Benefit from Disorder?
#
#    Taleb's key insight: some assets gain from volatility itself.
#    We measure:
#      - Vol-of-vol: does volatility cluster and spike? (benefits strangles)
#      - Vol autocorrelation: do vol spikes persist? (more time in payoff zone)
#      - Recent vol trend: is vol expanding? (vega gains on entry)
###############################################################################

def _antifragility_analysis(prices):
    max_score = 3
    score = 0
    details: list[str] = []

    if not prices or len(prices) < 90:
        details.append("Insufficient data for antifragility analysis")
        return {"score": score, "max_score": max_score, "details": "; ".join(details),
                "vol_of_vol": 0.0, "vol_autocorr": 0.0}

    df = prices_to_df(prices)
    returns = df["close"].pct_change().dropna()

    # Rolling 20-day vol
    rolling_vol = returns.rolling(20).std() * math.sqrt(252)
    rolling_vol = rolling_vol.dropna()

    if len(rolling_vol) < 40:
        details.append("Not enough rolling vol data for antifragility")
        return {"score": score, "max_score": max_score, "details": "; ".join(details),
                "vol_of_vol": 0.0, "vol_autocorr": 0.0}

    # Vol-of-vol: standard deviation of rolling vol
    vol_of_vol = rolling_vol.std() / rolling_vol.mean() if rolling_vol.mean() > 0 else 0
    details.append(f"Vol-of-vol (CV): {vol_of_vol:.2f}")

    # Vol autocorrelation: does vol cluster?
    vol_autocorr = float(rolling_vol.autocorr(lag=5))
    details.append(f"Vol autocorrelation (5-day lag): {vol_autocorr:.2f}")

    # Recent vol trend: compare last 20 days vs prior 60 days
    recent_vol = rolling_vol.iloc[-20:].mean()
    prior_vol = rolling_vol.iloc[-80:-20].mean() if len(rolling_vol) >= 80 else rolling_vol.iloc[:-20].mean()
    vol_trend = (recent_vol - prior_vol) / prior_vol if prior_vol > 0 else 0
    details.append(f"Recent vol: {recent_vol:.1%} vs prior: {prior_vol:.1%} (trend: {vol_trend:+.0%})")

    # Score: high vol-of-vol + clustering + expanding vol = antifragile setup
    if vol_of_vol > 0.5:
        score += 1
        details.append("High vol-of-vol — volatility is volatile (strangles thrive)")

    if vol_autocorr > 0.7:
        score += 1
        details.append("Strong vol clustering — spikes persist, strangles stay in-the-money longer")
    elif vol_autocorr > 0.4:
        pass  # neutral

    if vol_trend < -0.15:
        score += 1
        details.append("Vol contracting — cheap entry point, mean-reversion likely to expand vol")
    elif vol_trend > 0.30:
        details.append("Vol already expanding — may be late entry, premiums elevated")

    return {
        "score": score,
        "max_score": max_score,
        "details": "; ".join(details),
        "vol_of_vol": round(vol_of_vol, 4),
        "vol_autocorr": round(vol_autocorr, 4),
        "vol_trend": round(vol_trend, 4),
        "recent_vol": round(recent_vol, 4),
    }


###############################################################################
# LLM Generation
###############################################################################

def _generate_taleb_output(
    ticker: str,
    analysis_data: dict,
    state: AgentState,
    agent_id: str,
) -> TalebStrangleSignal:
    """Call the LLM to synthesise the five analyses into a strangle recommendation."""

    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an AI agent channelling Nassim Nicholas Taleb — author of
The Black Swan, Antifragile, and Fooled by Randomness. You are a practitioner
of long-volatility strategies, not a directional equity trader.

Your ONLY mandate is to evaluate **long strangles** (simultaneous OTM put + OTM call).
You NEVER recommend buying or shorting the underlying stock. Your output is always
about whether to BUY VOLATILITY (long strangles) or AVOID (vol too expensive).

Core principles:
- You LOVE cheap vol. Low IV rank is the #1 criterion.
- You LOVE fat tails. Excess kurtosis means Black-Scholes underprices options.
- You LOVE convexity. You want payoff functions that are concave-down in losses
  and convex-up in gains — strangles give you this.
- You LOVE disorder. If an asset's vol is itself volatile and clusters, strangles
  become asymmetric bets.
- You DESPISE expensive vol. If IV rank is above 70, the market has already priced
  in the tail risk. You are NOT paying for someone else's fear.
- You think in terms of vega-per-dollar: how much volatility exposure does each
  dollar of premium buy?

Communication style:
- Erudite, philosophical, slightly combative — like Taleb's writing
- Lead with the vol regime: "Vol is cheap/expensive, IV rank X%"
- Quote kurtosis and tail ratio as evidence of fat tails
- Express the strangle opportunity in terms of convexity and vega efficiency
- Mock anyone who uses Black-Scholes without adjusting for fat tails
- Reference the barbell strategy: small defined-risk bets with asymmetric payoff
- Use phrases like "antifragile positioning", "convexity harvest", "the market is
  Gaussian-blind", "optionality is free here"

Output signals:
- strong_buy_vol: IV rank <25%, fat tails confirmed, high vega efficiency
- buy_vol: Reasonably cheap vol with tail/convexity support
- neutral: Mixed signals or fair-value vol
- sell_vol: Vol too expensive, tails already priced in, avoid strangles

When providing reasoning, follow this structure:
1. IV rank proxy and what it means for strangle pricing
2. Kurtosis and tail ratio — evidence of fat tails
3. Vega efficiency — bang for your premium buck
4. Convexity ratio and gap frequency
5. Antifragility: vol-of-vol, clustering, trend
6. One-line Talebian conclusion
""",
            ),
            (
                "human",
                """Evaluate the long strangle opportunity for {ticker}:

Analysis Data:
{analysis_data}

Return your assessment in the following JSON format exactly:
{{
  "signal": "strong_buy_vol" | "buy_vol" | "neutral" | "sell_vol",
  "confidence": float between 0 and 100,
  "reasoning": "string",
  "iv_rank_proxy": float (0-100),
  "kurtosis": float,
  "skewness": float,
  "vega_efficiency": float,
  "convexity_score": float (0-10),
  "antifragility_score": float (0-10)
}}
""",
            ),
        ]
    )

    prompt = template.invoke({
        "analysis_data": json.dumps(analysis_data, indent=2),
        "ticker": ticker,
    })

    def create_default_taleb_signal():
        return TalebStrangleSignal(
            signal="neutral",
            confidence=0.0,
            reasoning="Insufficient data — cannot evaluate strangle opportunity",
            iv_rank_proxy=50.0,
            kurtosis=0.0,
            skewness=0.0,
            vega_efficiency=0.0,
            convexity_score=0.0,
            antifragility_score=0.0,
        )

    return call_llm(
        prompt=prompt,
        pydantic_model=TalebStrangleSignal,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_taleb_signal,
    )
