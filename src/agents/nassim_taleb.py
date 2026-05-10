from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
import json
import math
from datetime import datetime, timedelta
from typing_extensions import Literal
import numpy as np
import pandas as pd

from src.tools.api import (
    get_company_news,
    get_financial_metrics,
    get_insider_trades,
    get_market_cap,
    get_prices,
    prices_to_df,
    search_line_items,
)
from src.utils.llm import call_llm
from src.utils.progress import progress
from src.utils.api_key import get_api_key_from_state


class NassimTalebSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")


def nassim_taleb_agent(state: AgentState, agent_id: str = "nassim_taleb_agent"):
    """Analyzes stocks using Taleb's antifragility, tail risk, and convexity principles."""
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")

    # Look one year back for insider trades and news
    start_date = (datetime.fromisoformat(end_date) - timedelta(days=365)).date().isoformat()

    analysis_data = {}
    taleb_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching price data")
        prices = get_prices(ticker, start_date, end_date, api_key=api_key)
        prices_df = prices_to_df(prices) if prices else pd.DataFrame()

        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=10, api_key=api_key)

        progress.update_status(agent_id, ticker, "Gathering financial line items")
        line_items = search_line_items(
            ticker,
            [
                "free_cash_flow",
                "net_income",
                "total_debt",
                "cash_and_equivalents",
                "total_assets",
                "total_liabilities",
                "revenue",
                "operating_income",
                "research_and_development",
                "capital_expenditure",
                "outstanding_shares",
            ],
            end_date,
            period="ttm",
            limit=5,
            api_key=api_key,
        )

        progress.update_status(agent_id, ticker, "Fetching insider trades")
        insider_trades = get_insider_trades(ticker, end_date=end_date, start_date=start_date)

        progress.update_status(agent_id, ticker, "Fetching company news")
        news = get_company_news(ticker, end_date=end_date, start_date=start_date, limit=100)

        progress.update_status(agent_id, ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)

        # Run sub-analyses
        progress.update_status(agent_id, ticker, "Analyzing tail risk")
        tail_risk_analysis = analyze_tail_risk(prices_df)

        progress.update_status(agent_id, ticker, "Analyzing antifragility")
        antifragility_analysis = analyze_antifragility(metrics, line_items, market_cap)

        progress.update_status(agent_id, ticker, "Analyzing convexity")
        convexity_analysis = analyze_convexity(metrics, line_items, prices_df, market_cap)

        progress.update_status(agent_id, ticker, "Analyzing fragility")
        fragility_analysis = analyze_fragility(metrics, line_items)

        progress.update_status(agent_id, ticker, "Analyzing skin in the game")
        skin_in_game_analysis = analyze_skin_in_game(insider_trades)

        progress.update_status(agent_id, ticker, "Analyzing volatility regime")
        volatility_regime_analysis = analyze_volatility_regime(prices_df)

        progress.update_status(agent_id, ticker, "Scanning for black swan signals")
        black_swan_analysis = analyze_black_swan_sentinel(news, prices_df)

        # Aggregate scores (raw addition — max_scores create implicit weighting)
        total_score = (
            tail_risk_analysis["score"]
            + antifragility_analysis["score"]
            + convexity_analysis["score"]
            + fragility_analysis["score"]
            + skin_in_game_analysis["score"]
            + volatility_regime_analysis["score"]
            + black_swan_analysis["score"]
        )
        max_possible_score = (
            tail_risk_analysis["max_score"]
            + antifragility_analysis["max_score"]
            + convexity_analysis["max_score"]
            + fragility_analysis["max_score"]
            + skin_in_game_analysis["max_score"]
            + volatility_regime_analysis["max_score"]
            + black_swan_analysis["max_score"]
        )

        analysis_data[ticker] = {
            "ticker": ticker,
            "score": total_score,
            "max_score": max_possible_score,
            "tail_risk_analysis": tail_risk_analysis,
            "antifragility_analysis": antifragility_analysis,
            "convexity_analysis": convexity_analysis,
            "fragility_analysis": fragility_analysis,
            "skin_in_game_analysis": skin_in_game_analysis,
            "volatility_regime_analysis": volatility_regime_analysis,
            "black_swan_analysis": black_swan_analysis,
            "market_cap": market_cap,
        }

        progress.update_status(agent_id, ticker, "Generating Nassim Taleb analysis")
        taleb_output = generate_taleb_output(
            ticker=ticker,
            analysis_data=analysis_data[ticker],
            state=state,
            agent_id=agent_id,
        )

        taleb_analysis[ticker] = {
            "signal": taleb_output.signal,
            "confidence": taleb_output.confidence,
            "reasoning": taleb_output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=taleb_output.reasoning)

    # Create the message
    message = HumanMessage(content=json.dumps(taleb_analysis), name=agent_id)

    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(taleb_analysis, agent_id)

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"][agent_id] = taleb_analysis

    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}


###############################################################################
# Helper
###############################################################################


def safe_float(value, default=0.0):
    """Safely convert a value to float, handling NaN cases."""
    try:
        if pd.isna(value) or np.isnan(value):
            return default
        return float(value)
    except (ValueError, TypeError, OverflowError):
        return default


###############################################################################
# Sub-analysis functions
###############################################################################


def analyze_tail_risk(prices_df: pd.DataFrame) -> dict[str, any]:
    """Assess fat tails, skewness, tail ratio, and max drawdown."""
    if prices_df.empty or len(prices_df) < 20:
        return {"score": 0, "max_score": 8, "details": "Insufficient price data for tail risk analysis"}

    score = 0
    reasoning = []

    returns = prices_df["close"].pct_change().dropna()

    # Excess kurtosis (use rolling 63-day if enough data, else full series)
    if len(returns) >= 63:
        kurt = safe_float(returns.rolling(63).kurt().iloc[-1])
    else:
        kurt = safe_float(returns.kurt())

    if kurt > 5:
        score += 2
        reasoning.append(f"Extremely fat tails (kurtosis {kurt:.1f})")
    elif kurt > 2:
        score += 1
        reasoning.append(f"Moderate fat tails (kurtosis {kurt:.1f})")
    else:
        reasoning.append(f"Near-Gaussian tails (kurtosis {kurt:.1f}) — suspiciously thin")

    # Skewness
    if len(returns) >= 63:
        skew = safe_float(returns.rolling(63).skew().iloc[-1])
    else:
        skew = safe_float(returns.skew())

    if skew > 0.5:
        score += 2
        reasoning.append(f"Positive skew ({skew:.2f}) favors long convexity")
    elif skew > -0.5:
        score += 1
        reasoning.append(f"Symmetric distribution (skew {skew:.2f})")
    else:
        reasoning.append(f"Negative skew ({skew:.2f}) — crash-prone")

    # Tail ratio (95th percentile gains / abs(5th percentile losses))
    positive_returns = returns[returns > 0]
    negative_returns = returns[returns < 0]

    if len(positive_returns) > 20 and len(negative_returns) > 20:
        right_tail = np.percentile(positive_returns, 95)
        left_tail = abs(np.percentile(negative_returns, 5))
        tail_ratio = right_tail / left_tail if left_tail > 0 else 1.0

        if tail_ratio > 1.2:
            score += 2
            reasoning.append(f"Asymmetric upside (tail ratio {tail_ratio:.2f})")
        elif tail_ratio > 0.8:
            score += 1
            reasoning.append(f"Balanced tails (tail ratio {tail_ratio:.2f})")
        else:
            reasoning.append(f"Asymmetric downside (tail ratio {tail_ratio:.2f})")
    else:
        reasoning.append("Insufficient data for tail ratio")

    # Max drawdown
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    max_dd = safe_float(drawdown.min())

    if max_dd > -0.15:
        score += 2
        reasoning.append(f"Resilient (max drawdown {max_dd:.1%})")
    elif max_dd > -0.30:
        score += 1
        reasoning.append(f"Moderate drawdown ({max_dd:.1%})")
    else:
        reasoning.append(f"Severe drawdown ({max_dd:.1%}) — fragile")

    return {"score": score, "max_score": 8, "details": "; ".join(reasoning)}


def analyze_antifragility(metrics: list, line_items: list, market_cap: float | None) -> dict[str, any]:
    """Evaluate whether the company benefits from disorder: low debt, high cash, stable margins."""
    if not metrics and not line_items:
        return {"score": 0, "max_score": 10, "details": "Insufficient data for antifragility analysis"}

    score = 0
    reasoning = []
    latest_metrics = metrics[0] if metrics else None
    latest_item = line_items[0] if line_items else None

    # Net cash position
    cash = getattr(latest_item, "cash_and_equivalents", None) if latest_item else None
    total_debt = getattr(latest_item, "total_debt", None) if latest_item else None
    total_assets = getattr(latest_item, "total_assets", None) if latest_item else None

    if cash is not None and total_debt is not None:
        net_cash = cash - total_debt
        if net_cash > 0 and market_cap and cash > 0.20 * market_cap:
            score += 3
            reasoning.append(f"War chest: net cash ${net_cash:,.0f}, cash is {cash / market_cap:.0%} of market cap")
        elif net_cash > 0:
            score += 2
            reasoning.append(f"Net cash positive (${net_cash:,.0f})")
        elif total_assets and total_debt < 0.30 * total_assets:
            score += 1
            reasoning.append("Net debt but manageable relative to assets")
        else:
            reasoning.append("Leveraged position — not antifragile")
    else:
        reasoning.append("Cash/debt data not available")

    # Debt-to-equity
    debt_to_equity = getattr(latest_metrics, "debt_to_equity", None) if latest_metrics else None
    if debt_to_equity is not None:
        if debt_to_equity < 0.3:
            score += 2
            reasoning.append(f"Taleb-approved low leverage (D/E {debt_to_equity:.2f})")
        elif debt_to_equity < 0.7:
            score += 1
            reasoning.append(f"Moderate leverage (D/E {debt_to_equity:.2f})")
        else:
            reasoning.append(f"High leverage (D/E {debt_to_equity:.2f}) — fragile")
    else:
        reasoning.append("Debt-to-equity data not available")

    # Operating margin stability (CV across periods)
    op_margins = [m.operating_margin for m in metrics if m.operating_margin is not None]
    if len(op_margins) >= 3:
        mean_margin = sum(op_margins) / len(op_margins)
        variance = sum((m - mean_margin) ** 2 for m in op_margins) / len(op_margins)
        std_margin = variance ** 0.5
        cv = std_margin / abs(mean_margin) if mean_margin != 0 else float("inf")

        if cv < 0.15 and mean_margin > 0.15:
            score += 3
            reasoning.append(f"Stable high margins (avg {mean_margin:.1%}, CV {cv:.2f}) — antifragile pricing power")
        elif cv < 0.30 and mean_margin > 0.10:
            score += 2
            reasoning.append(f"Reasonable margin stability (avg {mean_margin:.1%}, CV {cv:.2f})")
        elif cv < 0.30:
            score += 1
            reasoning.append(f"Margins somewhat stable (CV {cv:.2f}) but low (avg {mean_margin:.1%})")
        else:
            reasoning.append(f"Volatile margins (CV {cv:.2f}) — fragile pricing power")
    else:
        reasoning.append("Insufficient margin history for stability analysis")

    # FCF consistency
    fcf_values = [getattr(item, "free_cash_flow", None) for item in line_items] if line_items else []
    fcf_values = [v for v in fcf_values if v is not None]
    if fcf_values:
        positive_count = sum(1 for v in fcf_values if v > 0)
        if positive_count == len(fcf_values):
            score += 2
            reasoning.append(f"Consistent FCF generation ({positive_count}/{len(fcf_values)} periods positive)")
        elif positive_count > len(fcf_values) / 2:
            score += 1
            reasoning.append(f"Majority positive FCF ({positive_count}/{len(fcf_values)} periods)")
        else:
            reasoning.append(f"Inconsistent FCF ({positive_count}/{len(fcf_values)} periods positive)")
    else:
        reasoning.append("FCF data not available")

    return {"score": score, "max_score": 10, "details": "; ".join(reasoning)}


def analyze_convexity(
    metrics: list, line_items: list, prices_df: pd.DataFrame, market_cap: float | None
) -> dict[str, any]:
    """Measure asymmetric payoff potential: R&D optionality, upside/downside ratio, cash optionality."""
    if not metrics and not line_items and prices_df.empty:
        return {"score": 0, "max_score": 10, "details": "Insufficient data for convexity analysis"}

    score = 0
    reasoning = []
    latest_item = line_items[0] if line_items else None

    # R&D as embedded optionality
    rd = getattr(latest_item, "research_and_development", None) if latest_item else None
    revenue = getattr(latest_item, "revenue", None) if latest_item else None

    if rd is not None and revenue and revenue > 0:
        rd_ratio = abs(rd) / revenue
        if rd_ratio > 0.15:
            score += 3
            reasoning.append(f"Significant embedded optionality via R&D ({rd_ratio:.1%} of revenue)")
        elif rd_ratio > 0.08:
            score += 2
            reasoning.append(f"Meaningful R&D investment ({rd_ratio:.1%} of revenue)")
        elif rd_ratio > 0.03:
            score += 1
            reasoning.append(f"Modest R&D ({rd_ratio:.1%} of revenue)")
        else:
            reasoning.append(f"Minimal R&D ({rd_ratio:.1%} of revenue)")
    else:
        reasoning.append("R&D data not available — no penalty for non-R&D sectors")

    # Upside/downside capture ratio
    if not prices_df.empty and len(prices_df) >= 20:
        returns = prices_df["close"].pct_change().dropna()
        upside = returns[returns > 0]
        downside = returns[returns < 0]

        if len(upside) > 10 and len(downside) > 10:
            avg_up = upside.mean()
            avg_down = abs(downside.mean())
            up_down_ratio = avg_up / avg_down if avg_down > 0 else 1.0

            if up_down_ratio > 1.3:
                score += 2
                reasoning.append(f"Convex return profile (up/down ratio {up_down_ratio:.2f})")
            elif up_down_ratio > 1.0:
                score += 1
                reasoning.append(f"Slight positive asymmetry (up/down ratio {up_down_ratio:.2f})")
            else:
                reasoning.append(f"Concave returns (up/down ratio {up_down_ratio:.2f}) — unfavorable")
        else:
            reasoning.append("Insufficient return data for asymmetry analysis")
    else:
        reasoning.append("Insufficient price data for return asymmetry analysis")

    # Cash optionality (cash / market_cap)
    cash = getattr(latest_item, "cash_and_equivalents", None) if latest_item else None
    if cash is not None and market_cap and market_cap > 0:
        cash_ratio = cash / market_cap
        if cash_ratio > 0.30:
            score += 3
            reasoning.append(f"Cash is a call option on future opportunities ({cash_ratio:.0%} of market cap)")
        elif cash_ratio > 0.15:
            score += 2
            reasoning.append(f"Strong cash position ({cash_ratio:.0%} of market cap)")
        elif cash_ratio > 0.05:
            score += 1
            reasoning.append(f"Moderate cash buffer ({cash_ratio:.0%} of market cap)")
        else:
            reasoning.append(f"Low cash relative to market cap ({cash_ratio:.0%})")
    else:
        reasoning.append("Cash/market cap data not available")

    # FCF yield
    latest_metrics = metrics[0] if metrics else None
    fcf_yield = None
    if latest_item and market_cap and market_cap > 0:
        fcf = getattr(latest_item, "free_cash_flow", None)
        if fcf is not None:
            fcf_yield = fcf / market_cap
    if fcf_yield is None and latest_metrics:
        fcf_yield = getattr(latest_metrics, "free_cash_flow_yield", None)

    if fcf_yield is not None:
        if fcf_yield > 0.10:
            score += 2
            reasoning.append(f"High FCF yield ({fcf_yield:.1%}) provides margin for convex bet")
        elif fcf_yield > 0.05:
            score += 1
            reasoning.append(f"Decent FCF yield ({fcf_yield:.1%})")
        else:
            reasoning.append(f"Low FCF yield ({fcf_yield:.1%})")
    else:
        reasoning.append("FCF yield data not available")

    return {"score": score, "max_score": 10, "details": "; ".join(reasoning)}


def analyze_fragility(metrics: list, line_items: list) -> dict[str, any]:
    """Via Negativa: detect fragile companies. High score = NOT fragile."""
    if not metrics:
        return {"score": 0, "max_score": 8, "details": "Insufficient data for fragility analysis"}

    score = 0
    reasoning = []
    latest_metrics = metrics[0]

    # Leverage fragility
    debt_to_equity = getattr(latest_metrics, "debt_to_equity", None)
    if debt_to_equity is not None:
        if debt_to_equity > 2.0:
            reasoning.append(f"Extremely fragile balance sheet (D/E {debt_to_equity:.2f})")
        elif debt_to_equity > 1.0:
            score += 1
            reasoning.append(f"Elevated leverage (D/E {debt_to_equity:.2f})")
        elif debt_to_equity > 0.5:
            score += 2
            reasoning.append(f"Moderate leverage (D/E {debt_to_equity:.2f})")
        else:
            score += 3
            reasoning.append(f"Low leverage (D/E {debt_to_equity:.2f}) — not fragile")
    else:
        reasoning.append("Debt-to-equity data not available")

    # Interest coverage
    interest_coverage = getattr(latest_metrics, "interest_coverage", None)
    if interest_coverage is not None:
        if interest_coverage > 10:
            score += 2
            reasoning.append(f"Interest coverage {interest_coverage:.1f}x — debt is irrelevant")
        elif interest_coverage > 5:
            score += 1
            reasoning.append(f"Comfortable interest coverage ({interest_coverage:.1f}x)")
        else:
            reasoning.append(f"Low interest coverage ({interest_coverage:.1f}x) — fragile to rate changes")
    else:
        reasoning.append("Interest coverage data not available")

    # Earnings volatility
    earnings_growth_values = [m.earnings_growth for m in metrics if m.earnings_growth is not None]
    if len(earnings_growth_values) >= 3:
        mean_eg = sum(earnings_growth_values) / len(earnings_growth_values)
        variance = sum((e - mean_eg) ** 2 for e in earnings_growth_values) / len(earnings_growth_values)
        std_eg = variance ** 0.5

        if std_eg < 0.20:
            score += 2
            reasoning.append(f"Stable earnings (growth std {std_eg:.2f}) — robust")
        elif std_eg < 0.50:
            score += 1
            reasoning.append(f"Moderate earnings volatility (growth std {std_eg:.2f})")
        else:
            reasoning.append(f"Highly volatile earnings (growth std {std_eg:.2f}) — fragile")
    else:
        reasoning.append("Insufficient earnings history for volatility analysis")

    # Net margin buffer
    net_margin = getattr(latest_metrics, "net_margin", None)
    if net_margin is not None:
        if net_margin > 0.15:
            score += 1
            reasoning.append(f"Fat margins ({net_margin:.1%}) buffer shocks")
        elif net_margin >= 0.05:
            reasoning.append(f"Moderate margins ({net_margin:.1%})")
        else:
            reasoning.append(f"Paper-thin margins ({net_margin:.1%}) — one shock away from loss")
    else:
        reasoning.append("Net margin data not available")

    # Clamp score at minimum 0
    score = max(score, 0)

    return {"score": score, "max_score": 8, "details": "; ".join(reasoning)}


def analyze_skin_in_game(insider_trades: list) -> dict[str, any]:
    """Assess insider alignment: net insider buying signals trust."""
    if not insider_trades:
        return {"score": 1, "max_score": 4, "details": "No insider trade data — neutral assumption"}

    score = 0
    reasoning = []

    shares_bought = sum(t.transaction_shares or 0 for t in insider_trades if (t.transaction_shares or 0) > 0)
    shares_sold = abs(sum(t.transaction_shares or 0 for t in insider_trades if (t.transaction_shares or 0) < 0))
    net = shares_bought - shares_sold

    if net > 0:
        buy_sell_ratio = net / max(shares_sold, 1)
        if buy_sell_ratio > 2.0:
            score = 4
            reasoning.append(f"Strong skin in the game — net insider buying {net:,} shares (ratio {buy_sell_ratio:.1f}x)")
        elif buy_sell_ratio > 0.5:
            score = 3
            reasoning.append(f"Moderate insider conviction — net buying {net:,} shares")
        else:
            score = 2
            reasoning.append(f"Net insider buying of {net:,} shares")
    else:
        reasoning.append(f"Insiders selling — no skin in the game (net {net:,} shares)")

    return {"score": score, "max_score": 4, "details": "; ".join(reasoning)}


def analyze_volatility_regime(prices_df: pd.DataFrame) -> dict[str, any]:
    """Volatility regime analysis. Key Taleb insight: low vol is dangerous (turkey problem)."""
    if prices_df.empty or len(prices_df) < 30:
        return {"score": 0, "max_score": 6, "details": "Insufficient price data for volatility analysis"}

    score = 0
    reasoning = []

    returns = prices_df["close"].pct_change().dropna()

    # Historical volatility (annualized, 21-day rolling)
    hist_vol = returns.rolling(21).std() * math.sqrt(252)

    # Vol regime ratio (current vol / 63-day avg vol)
    if len(hist_vol.dropna()) >= 63:
        vol_ma = hist_vol.rolling(63).mean()
        current_vol = safe_float(hist_vol.iloc[-1])
        avg_vol = safe_float(vol_ma.iloc[-1])
        vol_regime = current_vol / avg_vol if avg_vol > 0 else 1.0
    elif len(hist_vol.dropna()) >= 21:
        # Fallback: compare current to overall mean
        current_vol = safe_float(hist_vol.iloc[-1])
        avg_vol = safe_float(hist_vol.mean())
        vol_regime = current_vol / avg_vol if avg_vol > 0 else 1.0
    else:
        return {"score": 0, "max_score": 6, "details": "Insufficient data for volatility regime analysis"}

    # Vol regime scoring (max 4)
    if vol_regime < 0.7:
        reasoning.append(f"Dangerously low vol (regime {vol_regime:.2f}) — turkey problem")
    elif vol_regime < 0.9:
        score += 1
        reasoning.append(f"Below-average vol (regime {vol_regime:.2f}) — approaching complacency")
    elif vol_regime <= 1.3:
        score += 3
        reasoning.append(f"Normal vol regime ({vol_regime:.2f}) — fair pricing")
    elif vol_regime <= 2.0:
        score += 4
        reasoning.append(f"Elevated vol (regime {vol_regime:.2f}) — opportunity for the antifragile")
    else:
        score += 2
        reasoning.append(f"Extreme vol (regime {vol_regime:.2f}) — crisis mode")

    # Vol-of-vol scoring (max 2)
    if len(hist_vol.dropna()) >= 42:
        vol_of_vol = hist_vol.rolling(21).std()
        vol_of_vol_clean = vol_of_vol.dropna()
        if len(vol_of_vol_clean) > 0:
            current_vov = safe_float(vol_of_vol_clean.iloc[-1])
            median_vov = safe_float(vol_of_vol_clean.median())
            if median_vov > 0:
                if current_vov > 2 * median_vov:
                    score += 2
                    reasoning.append(f"Highly unstable vol (vol-of-vol {current_vov:.4f} vs median {median_vov:.4f}) — regime change likely")
                elif current_vov > median_vov:
                    score += 1
                    reasoning.append(f"Elevated vol-of-vol ({current_vov:.4f} vs median {median_vov:.4f})")
                else:
                    reasoning.append(f"Stable vol-of-vol ({current_vov:.4f})")
            else:
                reasoning.append("Vol-of-vol median is zero — unusual")
        else:
            reasoning.append("Insufficient vol-of-vol data")
    else:
        reasoning.append("Insufficient history for vol-of-vol analysis")

    return {"score": score, "max_score": 6, "details": "; ".join(reasoning)}


def analyze_black_swan_sentinel(news: list, prices_df: pd.DataFrame) -> dict[str, any]:
    """Monitor for crisis signals: abnormal news sentiment, volume spikes, price dislocations."""
    score = 2  # Default: normal conditions
    reasoning = []

    # News sentiment analysis
    neg_ratio = 0.0
    if news:
        total = len(news)
        neg_count = sum(1 for n in news if n.sentiment and n.sentiment.lower() in ["negative", "bearish"])
        neg_ratio = neg_count / total if total > 0 else 0
    else:
        reasoning.append("No recent news data")

    # Volume spike detection
    volume_spike = 1.0
    recent_return = 0.0
    if not prices_df.empty and len(prices_df) >= 10:
        if "volume" in prices_df.columns:
            recent_vol = prices_df["volume"].iloc[-5:].mean()
            avg_vol = prices_df["volume"].iloc[-63:].mean() if len(prices_df) >= 63 else prices_df["volume"].mean()
            volume_spike = recent_vol / avg_vol if avg_vol > 0 else 1.0

        if len(prices_df) >= 5:
            recent_return = safe_float(prices_df["close"].iloc[-1] / prices_df["close"].iloc[-5] - 1)

    # Scoring
    if neg_ratio > 0.7 and volume_spike > 2.0:
        score = 0
        reasoning.append(f"Black swan warning — {neg_ratio:.0%} negative news, {volume_spike:.1f}x volume spike")
    elif neg_ratio > 0.5 or volume_spike > 2.5:
        score = 1
        reasoning.append(f"Elevated stress signals (neg news {neg_ratio:.0%}, volume {volume_spike:.1f}x)")
    elif neg_ratio > 0.3 and abs(recent_return) > 0.10:
        score = 1
        reasoning.append(f"Moderate stress with price dislocation ({recent_return:.1%} move, {neg_ratio:.0%} negative news)")
    elif neg_ratio < 0.3 and volume_spike < 1.5:
        score = 3
        reasoning.append("No black swan signals detected")
    else:
        reasoning.append(f"Normal conditions (neg news {neg_ratio:.0%}, volume {volume_spike:.1f}x)")

    # Contrarian bonus: high negative news but no volume panic could be opportunity
    if neg_ratio > 0.4 and volume_spike < 1.5 and score < 4:
        score = min(score + 1, 4)
        reasoning.append("Contrarian opportunity — negative sentiment without panic selling")

    return {"score": score, "max_score": 4, "details": "; ".join(reasoning)}


###############################################################################
# LLM generation
###############################################################################


def generate_taleb_output(
    ticker: str,
    analysis_data: dict[str, any],
    state: AgentState,
    agent_id: str = "nassim_taleb_agent",
) -> NassimTalebSignal:
    """Get investment decision from LLM with a compact prompt."""

    facts = {
        "score": analysis_data.get("score"),
        "max_score": analysis_data.get("max_score"),
        "tail_risk": analysis_data.get("tail_risk_analysis", {}).get("details"),
        "antifragility": analysis_data.get("antifragility_analysis", {}).get("details"),
        "convexity": analysis_data.get("convexity_analysis", {}).get("details"),
        "fragility": analysis_data.get("fragility_analysis", {}).get("details"),
        "skin_in_game": analysis_data.get("skin_in_game_analysis", {}).get("details"),
        "volatility_regime": analysis_data.get("volatility_regime_analysis", {}).get("details"),
        "black_swan": analysis_data.get("black_swan_analysis", {}).get("details"),
        "market_cap": analysis_data.get("market_cap"),
    }

    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are Nassim Taleb. Decide bullish, bearish, or neutral using only the provided facts.\n"
                "\n"
                "Checklist for decision:\n"
                "- Antifragility (benefits from disorder)\n"
                "- Tail risk profile (fat tails, skewness)\n"
                "- Convexity (asymmetric payoff potential)\n"
                "- Fragility via negativa (avoid the fragile)\n"
                "- Skin in the game (insider alignment)\n"
                "- Volatility regime (low vol = danger)\n"
                "\n"
                "Signal rules:\n"
                "- Bullish: antifragile business with convex payoff AND not fragile.\n"
                "- Bearish: fragile business (high leverage, thin margins, volatile earnings) OR no skin in the game.\n"
                "- Neutral: mixed signals, or insufficient data to judge fragility.\n"
                "\n"
                "Confidence scale:\n"
                "- 90-100%: Truly antifragile with strong convexity and skin in the game\n"
                "- 70-89%: Low fragility with decent optionality\n"
                "- 50-69%: Mixed fragility signals, uncertain tail exposure\n"
                "- 30-49%: Some fragility detected, weak insider alignment\n"
                "- 10-29%: Clearly fragile or dangerous vol regime\n"
                "\n"
                "Use Taleb's vocabulary: antifragile, convexity, skin in the game, via negativa, barbell, turkey problem, Lindy effect.\n"
                "Keep reasoning under 150 characters. Do not invent data. Return JSON only.",
            ),
            (
                "human",
                "Ticker: {ticker}\n"
                "Facts:\n{facts}\n\n"
                "Return exactly:\n"
                "{{\n"
                '  "signal": "bullish" | "bearish" | "neutral",\n'
                '  "confidence": int,\n'
                '  "reasoning": "short justification"\n'
                "}}",
            ),
        ]
    )

    prompt = template.invoke({
        "facts": json.dumps(facts, separators=(",", ":"), ensure_ascii=False),
        "ticker": ticker,
    })

    def create_default_nassim_taleb_signal():
        return NassimTalebSignal(signal="neutral", confidence=50, reasoning="Insufficient data")

    return call_llm(
        prompt=prompt,
        pydantic_model=NassimTalebSignal,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_nassim_taleb_signal,
    )
