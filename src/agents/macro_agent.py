import json
import statistics
from datetime import datetime

from dateutil.relativedelta import relativedelta
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel
from typing_extensions import Literal

from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import (
    get_company_news,
    get_financial_metrics,
    get_prices,
)
from src.tools.macro_api import get_macro_snapshot
from src.utils.api_key import get_api_key_from_state
from src.utils.llm import call_llm
from src.utils.progress import progress


class MacroSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def macro_agent(state: AgentState, agent_id: str = "macro_agent"):
    """Top-down macro agent: reads the regime (trend, volatility, rate sensitivity,
    macro news flow) for each ticker and emits a risk-on / risk-off style signal."""
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    fred_api_key = get_api_key_from_state(state, "FRED_API_KEY")

    analysis_data = {}
    macro_analysis = {}

    # Trend (50-day SMA) and volatility (40-day) need a longer window than the
    # run's start_date provides during backtests (1-month lookback). Fetch ~8 months
    # of prices independent of the run window, mirroring the Taleb agent's approach.
    price_start_date = (datetime.fromisoformat(end_date) - relativedelta(months=8)).date().isoformat()

    # Macro environment is market-wide, so fetch it once for the whole run.
    progress.update_status(agent_id, None, "Fetching macro environment (FRED)")
    macro_snapshot = get_macro_snapshot(end_date, api_key=fred_api_key)
    macro_environment_analysis = analyze_macro_environment(macro_snapshot)

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching price history")
        prices = get_prices(ticker, start_date=price_start_date, end_date=end_date, api_key=api_key)

        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=4, api_key=api_key)

        progress.update_status(agent_id, ticker, "Fetching company news")
        news = get_company_news(ticker, end_date, start_date=start_date, limit=50, api_key=api_key)

        progress.update_status(agent_id, ticker, "Analyzing trend regime")
        trend_analysis = analyze_trend_regime(prices)

        progress.update_status(agent_id, ticker, "Analyzing volatility regime")
        volatility_analysis = analyze_volatility_regime(prices)

        progress.update_status(agent_id, ticker, "Analyzing rate sensitivity")
        rate_analysis = analyze_rate_sensitivity(metrics)

        progress.update_status(agent_id, ticker, "Analyzing macro news flow")
        sentiment_analysis = analyze_macro_sentiment(news)

        # Weighted blend. Real top-down macro (FRED) is the largest single input:
        #   macro environment 30%, trend 25%, volatility 20%, rate sensitivity 15%, news 10%
        total_score = (
            macro_environment_analysis["score"] * 0.30
            + trend_analysis["score"] * 0.25
            + volatility_analysis["score"] * 0.20
            + rate_analysis["score"] * 0.15
            + sentiment_analysis["score"] * 0.10
        )
        max_possible_score = 10

        if total_score >= 6.5:
            signal = "bullish"
        elif total_score <= 4.0:
            signal = "bearish"
        else:
            signal = "neutral"

        analysis_data[ticker] = {
            "signal": signal,
            "score": total_score,
            "max_score": max_possible_score,
            "macro_environment_analysis": macro_environment_analysis,
            "macro_snapshot": macro_snapshot,
            "trend_analysis": trend_analysis,
            "volatility_analysis": volatility_analysis,
            "rate_analysis": rate_analysis,
            "sentiment_analysis": sentiment_analysis,
        }

        progress.update_status(agent_id, ticker, "Generating macro analysis")
        macro_output = generate_macro_output(
            ticker=ticker,
            analysis_data=analysis_data,
            state=state,
            agent_id=agent_id,
        )

        macro_analysis[ticker] = {
            "signal": macro_output.signal,
            "confidence": macro_output.confidence,
            "reasoning": macro_output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=macro_output.reasoning)

    message = HumanMessage(content=json.dumps(macro_analysis), name=agent_id)

    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(macro_analysis, "Macro Agent")

    state["data"]["analyst_signals"][agent_id] = macro_analysis

    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}


def analyze_macro_environment(snapshot: dict) -> dict:
    """Top-down regime from FRED: yield curve, Fed direction, inflation, labor trend.

    Degrades to a neutral 5/10 when FRED data is unavailable (no FRED_API_KEY)."""
    if not snapshot or not snapshot.get("available"):
        return {"score": 5, "details": "Macro data unavailable - set FRED_API_KEY for live top-down inputs"}

    score_pts = 0.0
    max_pts = 0.0
    details = []

    # Yield curve (10y-2y): inversion is the classic recession warning
    yc = snapshot.get("yield_curve_10y2y")
    if yc is not None:
        max_pts += 3
        if yc > 0.5:
            score_pts += 3
            details.append(f"Healthy yield curve (10y-2y {yc:+.2f})")
        elif yc > 0:
            score_pts += 2
            details.append(f"Flattening curve (10y-2y {yc:+.2f})")
        elif yc > -0.5:
            score_pts += 1
            details.append(f"Mildly inverted curve (10y-2y {yc:+.2f}) - caution")
        else:
            details.append(f"Deeply inverted curve (10y-2y {yc:+.2f}) - recession warning")

    # Fed funds direction over ~6 months: easing is a liquidity tailwind
    ff_chg = snapshot.get("fed_funds_6m_change")
    if ff_chg is not None:
        max_pts += 3
        if ff_chg < -0.25:
            score_pts += 3
            details.append(f"Fed easing ({ff_chg:+.2f}pp/6m) - liquidity tailwind")
        elif ff_chg <= 0.25:
            score_pts += 2
            details.append(f"Fed on hold ({ff_chg:+.2f}pp/6m)")
        elif ff_chg <= 0.75:
            score_pts += 1
            details.append(f"Fed tightening ({ff_chg:+.2f}pp/6m) - headwind")
        else:
            details.append(f"Aggressive tightening ({ff_chg:+.2f}pp/6m) - strong headwind")

    # Inflation (CPI YoY): contained inflation supports risk assets
    cpi = snapshot.get("cpi_yoy")
    if cpi is not None:
        max_pts += 2
        if cpi < 2.5:
            score_pts += 2
            details.append(f"Inflation contained ({cpi:.1f}% YoY)")
        elif cpi < 4.0:
            score_pts += 1
            details.append(f"Moderate inflation ({cpi:.1f}% YoY)")
        else:
            details.append(f"Elevated inflation ({cpi:.1f}% YoY) - policy risk")

    # Labor market trend: a sharp rise in unemployment flags recession
    u_chg = snapshot.get("unemployment_6m_change")
    if u_chg is not None:
        max_pts += 2
        if u_chg < 0.1:
            score_pts += 2
            details.append("Stable/improving labor market")
        elif u_chg < 0.5:
            score_pts += 1
            details.append(f"Labor market softening ({u_chg:+.1f}pp/6m)")
        else:
            details.append(f"Labor market deteriorating ({u_chg:+.1f}pp/6m) - recession signal")

    if max_pts == 0:
        return {"score": 5, "details": "Macro data unavailable"}

    final_score = min(10, (score_pts / max_pts) * 10)
    return {"score": final_score, "details": "; ".join(details)}


def analyze_trend_regime(prices: list) -> dict:
    """Risk-on vs risk-off tape via price relative to its 20- and 50-period moving averages."""
    if not prices or len(prices) < 50:
        return {"score": 5, "details": "Insufficient price history for trend regime"}

    sorted_prices = sorted(prices, key=lambda p: p.time)
    closes = [p.close for p in sorted_prices if p.close is not None]
    if len(closes) < 50:
        return {"score": 5, "details": "Insufficient close prices for trend regime"}

    sma20 = sum(closes[-20:]) / 20
    sma50 = sum(closes[-50:]) / 50
    last = closes[-1]

    if last > sma20 > sma50:
        return {"score": 9, "details": f"Risk-on uptrend: price {last:.2f} > SMA20 {sma20:.2f} > SMA50 {sma50:.2f}"}
    if last < sma20 < sma50:
        return {"score": 2, "details": f"Risk-off downtrend: price {last:.2f} < SMA20 {sma20:.2f} < SMA50 {sma50:.2f}"}
    return {"score": 5, "details": f"Transitional/choppy tape: price {last:.2f}, SMA20 {sma20:.2f}, SMA50 {sma50:.2f}"}


def analyze_volatility_regime(prices: list) -> dict:
    """Rising volatility = macro stress (risk-off); compressing volatility = stable risk appetite."""
    if not prices or len(prices) < 40:
        return {"score": 5, "details": "Insufficient price data for volatility regime"}

    sorted_prices = sorted(prices, key=lambda p: p.time)
    closes = [p.close for p in sorted_prices if p.close is not None]
    returns = [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes))
        if closes[i - 1] > 0
    ]
    if len(returns) < 40:
        return {"score": 5, "details": "Insufficient returns for volatility regime"}

    recent_vol = statistics.pstdev(returns[-20:])
    longer_vol = statistics.pstdev(returns[-60:] if len(returns) >= 60 else returns)
    ratio = recent_vol / longer_vol if longer_vol > 0 else 1.0

    if ratio < 0.8:
        return {"score": 8, "details": f"Volatility compressing (ratio {ratio:.2f}) - stable risk appetite"}
    if ratio <= 1.2:
        return {"score": 6, "details": f"Stable volatility regime (ratio {ratio:.2f})"}
    if ratio <= 1.6:
        return {"score": 3, "details": f"Volatility expanding (ratio {ratio:.2f}) - rising macro stress"}
    return {"score": 1, "details": f"Volatility spiking (ratio {ratio:.2f}) - risk-off shock"}


def analyze_rate_sensitivity(metrics: list) -> dict:
    """How exposed the name is to monetary tightening: leverage, interest coverage, liquidity."""
    if not metrics:
        return {"score": 5, "details": "No metrics for rate-sensitivity analysis"}

    m = metrics[0]
    details = []
    raw_score = 0

    de = m.debt_to_equity
    if de is not None:
        if de < 0.5:
            raw_score += 3
            details.append(f"Low leverage (D/E {de:.2f}) - resilient to tightening")
        elif de < 1.0:
            raw_score += 2
            details.append(f"Moderate leverage (D/E {de:.2f})")
        elif de < 2.0:
            raw_score += 1
            details.append(f"Elevated leverage (D/E {de:.2f}) - rate-sensitive")
        else:
            details.append(f"High leverage (D/E {de:.2f}) - very rate-sensitive")
    else:
        details.append("Debt-to-equity unavailable")

    ic = m.interest_coverage
    if ic is not None:
        if ic > 8:
            raw_score += 3
            details.append(f"Strong interest coverage ({ic:.1f}x)")
        elif ic > 3:
            raw_score += 2
            details.append(f"Adequate interest coverage ({ic:.1f}x)")
        elif ic > 1:
            raw_score += 1
            details.append(f"Thin interest coverage ({ic:.1f}x)")
        else:
            details.append(f"Weak interest coverage ({ic:.1f}x) - fragile to rate hikes")
    else:
        details.append("Interest coverage unavailable")

    cr = m.current_ratio
    if cr is not None:
        if cr > 1.5:
            raw_score += 2
            details.append(f"Healthy liquidity (current ratio {cr:.2f})")
        elif cr > 1.0:
            raw_score += 1
            details.append(f"Adequate liquidity (current ratio {cr:.2f})")
        else:
            details.append(f"Liquidity strain (current ratio {cr:.2f})")
    else:
        details.append("Current ratio unavailable")

    max_raw = 8  # 3 + 3 + 2
    final_score = min(10, (raw_score / max_raw) * 10)
    return {"score": final_score, "details": "; ".join(details)}


def analyze_macro_sentiment(news: list) -> dict:
    """Net news sentiment plus how heavily headlines reference macro themes."""
    if not news:
        return {"score": 5, "details": "No news for macro sentiment"}

    macro_keywords = [
        "fed", "federal reserve", "inflation", "interest rate", "rate hike", "rate cut",
        "recession", "gdp", "tariff", "stimulus", "unemployment", "yield", "cpi", "macro",
    ]

    total = len(news)
    macro_hits = 0
    pos = 0
    neg = 0
    for n in news:
        title = (n.title or "").lower()
        if any(k in title for k in macro_keywords):
            macro_hits += 1
        sentiment = (n.sentiment or "").lower()
        if sentiment in ("negative", "bearish"):
            neg += 1
        elif sentiment in ("positive", "bullish"):
            pos += 1

    net = pos - neg
    if net > total * 0.2:
        score = 8
        detail = f"Net-positive news flow ({pos} pos / {neg} neg)"
    elif net < -total * 0.2:
        score = 3
        detail = f"Net-negative news flow ({pos} pos / {neg} neg)"
    else:
        score = 5
        detail = f"Balanced news flow ({pos} pos / {neg} neg)"

    return {"score": score, "details": f"{detail}; {macro_hits}/{total} headlines reference macro themes"}


def generate_macro_output(
    ticker: str,
    analysis_data: dict,
    state: AgentState,
    agent_id: str,
) -> MacroSignal:
    """Turn the macro sub-scores into a top-down regime call via the LLM."""
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a top-down global macro portfolio manager making a regime call on a single stock.

                Your lens is macro, not bottom-up:
                1. Trend regime — is the tape risk-on (above rising moving averages) or risk-off?
                2. Volatility regime — expanding volatility signals macro stress; compression signals stability.
                3. Rate sensitivity — leveraged, thinly-covered balance sheets suffer when policy tightens.
                4. Macro news flow — net sentiment and how exposed headlines are to Fed / inflation / growth themes.

                Rules:
                - Be bullish only when the regime is supportive (risk-on trend, contained volatility, low rate sensitivity).
                - Be bearish when volatility is expanding, the trend has rolled over, or the balance sheet is rate-fragile.
                - Default to neutral when signals conflict or data is thin.
                - Output JSON with signal, confidence (0-100), and a concise reasoning string in a decisive macro voice.""",
            ),
            (
                "human",
                """Based on the following macro analysis, produce a regime signal.

                Analysis Data for {ticker}:
                {analysis_data}

                Return the trading signal in this JSON format:
                {{
                  "signal": "bullish/bearish/neutral",
                  "confidence": float (0-100),
                  "reasoning": "string"
                }}
                """,
            ),
        ]
    )

    prompt = template.invoke({"analysis_data": json.dumps(analysis_data, indent=2), "ticker": ticker})

    def create_default_signal():
        return MacroSignal(signal="neutral", confidence=0.0, reasoning="Error in analysis, defaulting to neutral")

    return call_llm(
        prompt=prompt,
        pydantic_model=MacroSignal,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_signal,
    )
