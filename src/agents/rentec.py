"""
Renaissance Technologies (RenTec) Quant Agent

Applies five quantitative formulas used by hedge funds in prediction markets
(as outlined in the Polymarket quant playbook) to equity analysis:

1. Kelly Criterion         – Optimal position sizing based on edge & win probability
2. Expected Value Gap      – Scanning for mispriced securities vs model-implied fair value
3. KL-Divergence           – Flagging statistical inconsistencies across related signals
4. Bayesian Updating       – Continuously recalibrating probability estimates from new data
5. LMSR Market Impact      – Estimating how a position will move the market before others react
"""

from __future__ import annotations

import math
import json
from datetime import datetime, timedelta
from typing_extensions import Literal

import numpy as np

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import (
    get_financial_metrics,
    get_prices,
    get_company_news,
    get_insider_trades,
    get_market_cap,
    prices_to_df,
    search_line_items,
)
from src.utils.llm import call_llm
from src.utils.progress import progress
from src.utils.api_key import get_api_key_from_state


# ---------------------------------------------------------------------------
# Pydantic output schema
# ---------------------------------------------------------------------------

class RenTecSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float  # 0–100
    reasoning: str


# ---------------------------------------------------------------------------
# Main agent entry-point
# ---------------------------------------------------------------------------

def rentec_agent(state: AgentState, agent_id: str = "rentec_agent"):
    """Analyse stocks using Renaissance Technologies-style quantitative methods."""

    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    data = state["data"]
    end_date: str = data["end_date"]
    tickers: list[str] = data["tickers"]

    start_date = (datetime.fromisoformat(end_date) - timedelta(days=365)).date().isoformat()

    analysis_data: dict[str, dict] = {}
    rentec_analysis: dict[str, dict] = {}

    for ticker in tickers:
        # ==================================================================
        # Fetch raw data
        # ==================================================================
        progress.update_status(agent_id, ticker, "Fetching prices")
        prices = get_prices(ticker, start_date, end_date, api_key=api_key)

        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=5, api_key=api_key)

        progress.update_status(agent_id, ticker, "Fetching line items")
        line_items = search_line_items(
            ticker,
            [
                "free_cash_flow",
                "net_income",
                "total_debt",
                "cash_and_equivalents",
                "total_assets",
                "total_liabilities",
                "outstanding_shares",
                "revenue",
                "earnings_per_share_basic",
            ],
            end_date,
            api_key=api_key,
        )

        progress.update_status(agent_id, ticker, "Fetching market cap")
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)

        progress.update_status(agent_id, ticker, "Fetching company news")
        news = get_company_news(ticker, end_date=end_date, start_date=start_date, limit=100)

        progress.update_status(agent_id, ticker, "Fetching insider trades")
        insider_trades = get_insider_trades(ticker, end_date=end_date, start_date=start_date)

        # ==================================================================
        # Run the five quant sub-analyses
        # ==================================================================
        progress.update_status(agent_id, ticker, "Running Kelly Criterion analysis")
        kelly_analysis = _kelly_criterion_analysis(prices, metrics, line_items, market_cap)

        progress.update_status(agent_id, ticker, "Running Expected Value Gap scan")
        ev_gap_analysis = _expected_value_gap_analysis(metrics, line_items, market_cap)

        progress.update_status(agent_id, ticker, "Running KL-Divergence analysis")
        kl_analysis = _kl_divergence_analysis(prices, news, insider_trades)

        progress.update_status(agent_id, ticker, "Running Bayesian Updating")
        bayesian_analysis = _bayesian_update_analysis(
            kelly_analysis, ev_gap_analysis, kl_analysis, news, insider_trades
        )

        progress.update_status(agent_id, ticker, "Running LMSR Market Impact estimate")
        lmsr_analysis = _lmsr_market_impact_analysis(prices, market_cap)

        # ==================================================================
        # Aggregate scores
        # ==================================================================
        total_score = (
            kelly_analysis["score"]
            + ev_gap_analysis["score"]
            + kl_analysis["score"]
            + bayesian_analysis["score"]
            + lmsr_analysis["score"]
        )
        max_score = (
            kelly_analysis["max_score"]
            + ev_gap_analysis["max_score"]
            + kl_analysis["max_score"]
            + bayesian_analysis["max_score"]
            + lmsr_analysis["max_score"]
        )

        if max_score == 0:
            signal = "neutral"
        elif total_score >= 0.7 * max_score:
            signal = "bullish"
        elif total_score <= 0.3 * max_score:
            signal = "bearish"
        else:
            signal = "neutral"

        analysis_data[ticker] = {
            "signal": signal,
            "score": total_score,
            "max_score": max_score,
            "kelly_criterion": kelly_analysis,
            "expected_value_gap": ev_gap_analysis,
            "kl_divergence": kl_analysis,
            "bayesian_update": bayesian_analysis,
            "lmsr_market_impact": lmsr_analysis,
            "market_cap": market_cap,
        }

        progress.update_status(agent_id, ticker, "Generating LLM output")
        rentec_output = _generate_rentec_output(
            ticker=ticker,
            analysis_data=analysis_data,
            state=state,
            agent_id=agent_id,
        )

        rentec_analysis[ticker] = {
            "signal": rentec_output.signal,
            "confidence": rentec_output.confidence,
            "reasoning": rentec_output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=rentec_output.reasoning)

    # ------------------------------------------------------------------
    # Return to the graph
    # ------------------------------------------------------------------
    message = HumanMessage(content=json.dumps(rentec_analysis), name=agent_id)

    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(rentec_analysis, "RenTec Quant Agent")

    state["data"]["analyst_signals"][agent_id] = rentec_analysis

    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}


###############################################################################
# 1. Kelly Criterion – Optimal Position Sizing
#
#   f* = (p * b  -  q) / b
#   where  p = estimated win probability,  q = 1 - p,  b = odds (reward/risk)
#
#   We derive p from historical win-rate of positive return days and
#   b from average-gain / average-loss ratio.
###############################################################################

def _kelly_criterion_analysis(prices, metrics, line_items, market_cap):
    max_score = 5
    score = 0
    details: list[str] = []

    if not prices or len(prices) < 30:
        details.append("Insufficient price data for Kelly analysis")
        return {"score": score, "max_score": max_score, "details": "; ".join(details)}

    df = prices_to_df(prices)
    returns = df["close"].pct_change().dropna()

    wins = returns[returns > 0]
    losses = returns[returns < 0]

    if len(wins) == 0 or len(losses) == 0:
        details.append("Cannot compute Kelly – no wins or no losses in period")
        return {"score": score, "max_score": max_score, "details": "; ".join(details)}

    p = len(wins) / len(returns)       # win probability
    q = 1 - p
    avg_win = wins.mean()
    avg_loss = abs(losses.mean())
    b = avg_win / avg_loss if avg_loss > 0 else 0  # reward-to-risk ratio

    kelly_fraction = (p * b - q) / b if b > 0 else 0

    details.append(f"Win rate {p:.1%}, avg gain/loss ratio {b:.2f}")
    details.append(f"Kelly fraction f* = {kelly_fraction:.3f}")

    # Score based on Kelly fraction
    if kelly_fraction > 0.25:
        score += 5
        details.append("Strong positive edge — large optimal allocation")
    elif kelly_fraction > 0.15:
        score += 4
        details.append("Solid positive edge")
    elif kelly_fraction > 0.05:
        score += 3
        details.append("Moderate edge detected")
    elif kelly_fraction > 0:
        score += 1
        details.append("Marginal edge — small allocation warranted")
    else:
        details.append("Negative Kelly — no statistical edge detected")

    return {
        "score": score,
        "max_score": max_score,
        "details": "; ".join(details),
        "kelly_fraction": round(kelly_fraction, 4),
        "win_rate": round(p, 4),
        "reward_risk_ratio": round(b, 4),
    }


###############################################################################
# 2. Expected Value Gap Scanning
#
#   EV_gap = model_fair_value  -  market_price
#
#   We build an independent probability-weighted fair value from FCF yield,
#   earnings yield, and revenue multiples, then compare to market price.
###############################################################################

def _expected_value_gap_analysis(metrics, line_items, market_cap):
    max_score = 5
    score = 0
    details: list[str] = []

    if not metrics or not market_cap or not line_items:
        details.append("Insufficient data for EV gap analysis")
        return {"score": score, "max_score": max_score, "details": "; ".join(details)}

    latest = line_items[0] if line_items else None
    m = metrics[0]

    # Collect valuation signals
    fair_values: list[float] = []

    # FCF-based fair value (FCF * 15 multiple as baseline)
    fcf = getattr(latest, "free_cash_flow", None) if latest else None
    if fcf and fcf > 0:
        fcf_fv = fcf * 15
        fair_values.append(fcf_fv)
        details.append(f"FCF-implied value: ${fcf_fv / 1e9:.1f}B")

    # Earnings-based fair value (PE of 15)
    net_income = getattr(latest, "net_income", None) if latest else None
    if net_income and net_income > 0:
        earnings_fv = net_income * 15
        fair_values.append(earnings_fv)
        details.append(f"Earnings-implied value: ${earnings_fv / 1e9:.1f}B")

    # Revenue-based fair value (using sector-average PS ratio ~3)
    revenue = getattr(latest, "revenue", None) if latest else None
    if revenue and revenue > 0:
        rev_fv = revenue * 3
        fair_values.append(rev_fv)
        details.append(f"Revenue-implied value: ${rev_fv / 1e9:.1f}B")

    if not fair_values:
        details.append("No fair value estimates available")
        return {"score": score, "max_score": max_score, "details": "; ".join(details)}

    # Probability-weighted composite fair value
    model_fair_value = sum(fair_values) / len(fair_values)
    ev_gap_pct = (model_fair_value - market_cap) / market_cap

    details.append(f"Market cap: ${market_cap / 1e9:.1f}B")
    details.append(f"Model fair value: ${model_fair_value / 1e9:.1f}B")
    details.append(f"EV gap: {ev_gap_pct:+.1%}")

    # Score based on gap magnitude and direction
    if ev_gap_pct > 0.40:
        score += 5
        details.append("Deeply undervalued — large positive EV gap")
    elif ev_gap_pct > 0.20:
        score += 4
        details.append("Significantly undervalued")
    elif ev_gap_pct > 0.10:
        score += 3
        details.append("Moderately undervalued")
    elif ev_gap_pct > 0:
        score += 1
        details.append("Slightly undervalued")
    elif ev_gap_pct > -0.10:
        score += 0
        details.append("Fairly valued")
    else:
        details.append("Overvalued — negative EV gap")

    return {
        "score": score,
        "max_score": max_score,
        "details": "; ".join(details),
        "ev_gap_pct": round(ev_gap_pct, 4),
        "model_fair_value": model_fair_value,
    }


###############################################################################
# 3. KL-Divergence – Signal Consistency Check
#
#   D_KL(P || Q) = Σ P(x) * log(P(x) / Q(x))
#
#   We compare the distribution of returns implied by fundamentals (P)
#   versus the distribution observed in market prices (Q).
#   Large divergence → market is mispricing the stock relative to fundamentals.
###############################################################################

def _kl_divergence_analysis(prices, news, insider_trades):
    max_score = 4
    score = 0
    details: list[str] = []

    if not prices or len(prices) < 60:
        details.append("Insufficient data for KL-divergence analysis")
        return {"score": score, "max_score": max_score, "details": "; ".join(details)}

    df = prices_to_df(prices)
    returns = df["close"].pct_change().dropna().values

    # Split into two halves to detect regime change / inconsistency
    mid = len(returns) // 2
    recent_returns = returns[mid:]
    older_returns = returns[:mid]

    # Build empirical distributions using histogram bins
    bins = np.linspace(-0.10, 0.10, 21)  # 20 bins from -10% to +10%

    hist_recent, _ = np.histogram(recent_returns, bins=bins, density=True)
    hist_older, _ = np.histogram(older_returns, bins=bins, density=True)

    # Add small epsilon to avoid log(0)
    eps = 1e-10
    p = hist_recent + eps
    q = hist_older + eps

    # Normalise to proper distributions
    p = p / p.sum()
    q = q / q.sum()

    kl_div = float(np.sum(p * np.log(p / q)))

    details.append(f"KL-divergence (recent vs older returns): {kl_div:.4f}")

    # Also check news sentiment vs price direction divergence
    if news:
        neg_count = sum(1 for n in news if n.sentiment and n.sentiment.lower() in ["negative", "bearish"])
        pos_count = sum(1 for n in news if n.sentiment and n.sentiment.lower() in ["positive", "bullish"])
        total_news = len(news)
        news_sentiment_ratio = (pos_count - neg_count) / max(total_news, 1)

        recent_return = float(np.mean(recent_returns)) if len(recent_returns) > 0 else 0

        # Divergence: positive news but negative returns or vice versa
        sentiment_price_divergence = abs(news_sentiment_ratio - np.sign(recent_return))
        details.append(f"Sentiment ratio: {news_sentiment_ratio:+.2f}, recent avg return: {recent_return:+.4f}")

        if sentiment_price_divergence > 1.0:
            details.append("Strong sentiment-price divergence detected")
    else:
        sentiment_price_divergence = 0

    # Also factor in insider trade signals
    insider_signal = 0
    if insider_trades:
        bought = sum(t.transaction_shares or 0 for t in insider_trades if (t.transaction_shares or 0) > 0)
        sold = abs(sum(t.transaction_shares or 0 for t in insider_trades if (t.transaction_shares or 0) < 0))
        insider_signal = 1 if bought > sold else -1
        details.append(f"Insider net: {'buying' if insider_signal > 0 else 'selling'}")

    # Score: high KL-divergence + insider/sentiment divergence → opportunity
    if kl_div > 0.5:
        score += 2
        details.append("High regime change detected — distribution shift")
    elif kl_div > 0.2:
        score += 1
        details.append("Moderate distribution shift")

    if sentiment_price_divergence > 1.0:
        score += 1

    if insider_signal > 0:
        score += 1
        details.append("Insider buying confirms contrarian signal")

    return {
        "score": score,
        "max_score": max_score,
        "details": "; ".join(details),
        "kl_divergence": round(kl_div, 4),
    }


###############################################################################
# 4. Bayesian Updating – Recalibrate probability from multiple signals
#
#   P(bullish | data) ∝ P(data | bullish) * P(bullish)
#
#   Start with a prior from the Kelly edge, then update with evidence from
#   EV gap, KL-divergence, news sentiment, and insider activity.
###############################################################################

def _bayesian_update_analysis(kelly_result, ev_gap_result, kl_result, news, insider_trades):
    max_score = 4
    score = 0
    details: list[str] = []

    # Prior: start with Kelly win rate or 0.5 if unavailable
    prior = kelly_result.get("win_rate", 0.5)

    # Evidence likelihoods (how likely each signal under bullish hypothesis)
    likelihoods: list[tuple[str, float]] = []

    # EV gap evidence
    ev_gap = ev_gap_result.get("ev_gap_pct", 0)
    if ev_gap > 0.10:
        likelihoods.append(("EV gap undervalued", 0.75))
    elif ev_gap > 0:
        likelihoods.append(("EV gap slightly positive", 0.60))
    elif ev_gap > -0.10:
        likelihoods.append(("EV gap fair", 0.50))
    else:
        likelihoods.append(("EV gap overvalued", 0.30))

    # KL-divergence evidence (high divergence = potential opportunity)
    kl_div = kl_result.get("kl_divergence", 0)
    if kl_div > 0.5:
        likelihoods.append(("High KL-divergence (regime shift)", 0.65))
    elif kl_div > 0.2:
        likelihoods.append(("Moderate KL-divergence", 0.55))
    else:
        likelihoods.append(("Low KL-divergence (stable)", 0.50))

    # News sentiment evidence
    if news:
        pos = sum(1 for n in news if n.sentiment and n.sentiment.lower() in ["positive", "bullish"])
        neg = sum(1 for n in news if n.sentiment and n.sentiment.lower() in ["negative", "bearish"])
        if pos > neg * 1.5:
            likelihoods.append(("Strong positive sentiment", 0.70))
        elif pos > neg:
            likelihoods.append(("Moderately positive sentiment", 0.58))
        elif neg > pos * 1.5:
            likelihoods.append(("Strong negative sentiment", 0.35))
        else:
            likelihoods.append(("Mixed sentiment", 0.50))

    # Insider evidence
    if insider_trades:
        bought = sum(t.transaction_shares or 0 for t in insider_trades if (t.transaction_shares or 0) > 0)
        sold = abs(sum(t.transaction_shares or 0 for t in insider_trades if (t.transaction_shares or 0) < 0))
        if bought > sold:
            likelihoods.append(("Net insider buying", 0.70))
        else:
            likelihoods.append(("Net insider selling", 0.40))

    # Bayesian update: P(bull | evidence) ∝ prior * Π likelihood_i
    # We also compute the bearish complement for normalisation
    posterior_bull = prior
    posterior_bear = 1 - prior

    for label, lk in likelihoods:
        posterior_bull *= lk
        posterior_bear *= (1 - lk)
        details.append(f"{label} → P(bull|e)={lk:.2f}")

    # Normalise
    total = posterior_bull + posterior_bear
    if total > 0:
        posterior_bull /= total
    else:
        posterior_bull = 0.5

    details.insert(0, f"Prior P(bull): {prior:.3f}")
    details.append(f"Posterior P(bull): {posterior_bull:.3f}")

    # Score based on posterior
    if posterior_bull > 0.75:
        score += 4
        details.append("Very high posterior probability — strong bullish conviction")
    elif posterior_bull > 0.60:
        score += 3
        details.append("Elevated bullish probability")
    elif posterior_bull > 0.50:
        score += 2
        details.append("Slightly bullish posterior")
    elif posterior_bull > 0.40:
        score += 1
        details.append("Near-neutral posterior")
    else:
        details.append("Bearish posterior")

    return {
        "score": score,
        "max_score": max_score,
        "details": "; ".join(details),
        "posterior_bullish": round(posterior_bull, 4),
    }


###############################################################################
# 5. LMSR Market Impact – Liquidity & Impact Estimation
#
#   LMSR cost function:  C(q) = b * ln(Σ exp(q_i / b))
#   Price function:       p_i  = exp(q_i / b) / Σ exp(q_j / b)
#
#   We adapt this to equity markets by estimating how much a position would
#   move the market given volume and volatility — measuring liquidity risk.
###############################################################################

def _lmsr_market_impact_analysis(prices, market_cap):
    max_score = 2
    score = 0
    details: list[str] = []

    if not prices or len(prices) < 30 or not market_cap:
        details.append("Insufficient data for LMSR market impact analysis")
        return {"score": score, "max_score": max_score, "details": "; ".join(details)}

    df = prices_to_df(prices)

    # Average daily volume and volatility
    avg_volume = df["volume"].mean()
    avg_price = df["close"].mean()
    avg_dollar_volume = avg_volume * avg_price
    daily_volatility = df["close"].pct_change().std()

    # LMSR-inspired liquidity parameter b ≈ daily dollar volume / volatility
    # Higher b → more liquid → less market impact per trade
    b_param = avg_dollar_volume / (daily_volatility + 1e-10) if daily_volatility > 0 else 0

    # Estimate impact of a $1M position
    position_size = 1_000_000
    if avg_dollar_volume > 0:
        market_impact_pct = (position_size / avg_dollar_volume) * daily_volatility * 100
    else:
        market_impact_pct = float("inf")

    details.append(f"Avg daily $ volume: ${avg_dollar_volume / 1e6:.1f}M")
    details.append(f"Daily volatility: {daily_volatility:.4f}")
    details.append(f"LMSR b-parameter: {b_param / 1e9:.2f}B")
    details.append(f"Est. impact of $1M position: {market_impact_pct:.3f}%")

    # Score: low impact = good liquidity = favorable for position entry
    if market_impact_pct < 0.01:
        score += 2
        details.append("Excellent liquidity — minimal market impact")
    elif market_impact_pct < 0.05:
        score += 1
        details.append("Adequate liquidity")
    else:
        details.append("Poor liquidity — high market impact risk")

    return {
        "score": score,
        "max_score": max_score,
        "details": "; ".join(details),
        "market_impact_pct": round(market_impact_pct, 6),
        "b_parameter": round(b_param, 2),
    }


###############################################################################
# LLM generation
###############################################################################

def _generate_rentec_output(
    ticker: str,
    analysis_data: dict,
    state: AgentState,
    agent_id: str,
) -> RenTecSignal:
    """Call the LLM to synthesise the five quant signals into a final trading decision."""

    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an AI agent emulating the quantitative trading approach of
Renaissance Technologies (RenTec), the most successful quant hedge fund in history.
Your mandate:

- Make decisions based purely on mathematical and statistical evidence
- Apply the Kelly Criterion to determine optimal position sizing and conviction
- Identify expected-value gaps where market price diverges from model fair value
- Use KL-Divergence to detect regime changes and signal inconsistencies
- Apply Bayesian reasoning to update beliefs as new evidence arrives
- Consider LMSR-derived market impact / liquidity before recommending a position

Communication style:
- Terse, quantitative, data-first — like a quant research memo
- Lead with the key statistical metrics (Kelly f*, EV gap %, posterior probability)
- Express confidence as a precise number tied to the Bayesian posterior
- Highlight any divergence between signals — that is where the edge lives
- Never use flowery language; stick to numbers and brief conclusions

When providing your reasoning, follow this structure:
1. State the Kelly fraction and what it implies about edge
2. Quote the EV gap percentage and fair value estimate
3. Note any KL-divergence or regime change
4. Give the Bayesian posterior probability
5. Comment on liquidity / market impact
6. One-line conclusion

Example bullish: "Kelly f*=0.18, win rate 56%, gain/loss 1.3x. EV gap +32% (model $42B vs mkt $32B). KL-div 0.41 — moderate regime shift, sentiment diverging from price. Bayesian posterior P(bull)=0.71. Liquidity adequate, $1M impact 0.02%. Allocate."
Example bearish: "Kelly f*=-0.03, negative edge. EV gap -15%. Posterior P(bull)=0.38. Pass."
""",
            ),
            (
                "human",
                """Based on the following quantitative analysis, create the investment signal:

Analysis Data for {ticker}:
{analysis_data}

Return the trading signal in the following JSON format exactly:
{{
  "signal": "bullish" | "bearish" | "neutral",
  "confidence": float between 0 and 100,
  "reasoning": "string"
}}
""",
            ),
        ]
    )

    prompt = template.invoke({
        "analysis_data": json.dumps(analysis_data, indent=2),
        "ticker": ticker,
    })

    def create_default_rentec_signal():
        return RenTecSignal(
            signal="neutral",
            confidence=0.0,
            reasoning="Insufficient data — defaulting to neutral",
        )

    return call_llm(
        prompt=prompt,
        pydantic_model=RenTecSignal,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_rentec_signal,
    )
