from langchain_openai import ChatOpenAI
from graph.state import AgentState, show_agent_reasoning
from tools.api import get_financial_metrics, get_market_cap, search_line_items
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import json
from typing_extensions import Literal
from utils.progress import progress
from utils.llm import call_llm

class CathieWoodSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def cathie_wood_agent(state: AgentState):
    """
    Analyzes stocks using Cathie Wood's investing principles and LLM reasoning.
    1. Prioritizes companies with breakthrough technologies or business models
    2. Focuses on industries with rapid adoption curves and massive TAM (Total Addressable Market).
    3. Invests mostly in AI, robotics, genomic sequencing, fintech, and blockchain.
    4. Willing to endure short-term volatility for long-term gains.
    """
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]

    analysis_data = {}
    cw_analysis = {}

    for ticker in tickers:
        progress.update_status("cathie_wood_agent", ticker, "Fetching financial metrics")
        # You can adjust these parameters (period="annual"/"ttm", limit=5/10, etc.)
        metrics = get_financial_metrics(ticker, end_date, period="annual", limit=5)

        progress.update_status("cathie_wood_agent", ticker, "Gathering financial line items")
        # Request multiple periods of data (annual or TTM) for a more robust view.
        financial_line_items = search_line_items(
            ticker,
            [
                "revenue",
                "operating_margin",
                "debt_to_equity",
                "free_cash_flow",
                "total_assets",
                "total_liabilities",
                "dividends_and_other_cash_distributions",
                "outstanding_shares"
            ],
            end_date,
            period="annual",
            limit=5
        )

        progress.update_status("cathie_wood_agent", ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date)

        progress.update_status("cathie_wood_agent", ticker, "Analyzing disruptive potential")
        disruptive_analysis = analyze_disruptive_potential(metrics, financial_line_items)

        progress.update_status("cathie_wood_agent", ticker, "Analyzing innovation-driven growth")
        innovation_analysis = analyze_innovation_growth(metrics, financial_line_items)

        progress.update_status("cathie_wood_agent", ticker, "Calculating valuation & high-growth scenario")
        valuation_analysis = analyze_cathie_wood_valuation(financial_line_items, market_cap)

        # Combine partial scores or signals
        total_score = disruptive_analysis["score"] + innovation_analysis["score"] + valuation_analysis["score"]
        max_possible_score = 15  # Adjust weighting as desired

        if total_score >= 0.7 * max_possible_score:
            signal = "bullish"
        elif total_score <= 0.3 * max_possible_score:
            signal = "bearish"
        else:
            signal = "neutral"

        analysis_data[ticker] = {
            "signal": signal,
            "score": total_score,
            "max_score": max_possible_score,
            "disruptive_analysis": disruptive_analysis,
            "innovation_analysis": innovation_analysis,
            "valuation_analysis": valuation_analysis
        }

        progress.update_status("cathie_wood_agent", ticker, "Generating Cathie Wood style analysis")
        cw_output = generate_cathie_wood_output(
            ticker=ticker,
            analysis_data=analysis_data,
            model_name=state["metadata"]["model_name"],
            model_provider=state["metadata"]["model_provider"],
        )

        cw_analysis[ticker] = {
            "signal": cw_output.signal,
            "confidence": cw_output.confidence,
            "reasoning": cw_output.reasoning
        }

        progress.update_status("cathie_wood_agent", ticker, "Done")

    message = HumanMessage(
        content=json.dumps(cw_analysis),
        name="cathie_wood_agent"
    )

    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(cw_analysis, "Cathie Wood Agent")

    state["data"]["analyst_signals"]["cathie_wood_agent"] = cw_analysis

    return {
        "messages": [message],
        "data": state["data"]
    }


def analyze_disruptive_potential(metrics: list, financial_line_items: list) -> dict:
    """
    Analyze whether the company has disruptive products, technology, or business model.
    This can involve revenue growth acceleration, R&D intensity, and market share expansion.
    """
    score = 0
    details = []

    if not metrics or not financial_line_items:
        return {
            "score": 0,
            "details": "Insufficient data to analyze disruptive potential"
        }

    # Example: check multi-year revenue growth as a proxy for disruptive adoption
    revenues = [item.revenue for item in financial_line_items if item.revenue is not None]
    if len(revenues) >= 2:
        initial, final = revenues[0], revenues[-1]
        if initial and final and final > initial:
            growth_rate = (final - initial) / abs(initial)
            if growth_rate > 1.0:
                score += 3
                details.append(f"Revenue more than doubled over the period (growth: {(growth_rate*100):.1f}%).")
            elif growth_rate > 0.5:
                score += 2
                details.append(f"Revenue grew significantly over the period (growth: {(growth_rate*100):.1f}%).")
            else:
                score += 1
                details.append(f"Revenue growth is positive (growth: {(growth_rate*100):.1f}%).")
        else:
            details.append("Revenue did not grow significantly or data insufficient.")
    else:
        details.append("Not enough revenue data for multi-period trend.")

    return {
        "score": score,
        "details": "; ".join(details)
    }


def analyze_innovation_growth(metrics: list, financial_line_items: list) -> dict:
    """
    Evaluate the company's commitment to R&D, future-facing technologies, and
    potential for exponential growth.
    """
    score = 0
    details = []

    if not metrics or not financial_line_items:
        return {
            "score": 0,
            "details": "Insufficient data to analyze innovation-driven growth"
        }

    # We might check operating margin, free cash flow used for R&D, etc.
    # For demonstration, let's treat consistent positive FCF as an indicator of capacity to invest.

    fcf_vals = [item.free_cash_flow for item in financial_line_items if item.free_cash_flow is not None]
    if fcf_vals:
        positive_fcf_count = sum(1 for f in fcf_vals if f > 0)
        if positive_fcf_count >= (len(fcf_vals) // 2 + 1):
            score += 2
            details.append("Company has consistent free cash flow for reinvestment in innovation.")
        else:
            details.append("Free cash flow not consistently positive, limited reinvestment capacity.")
    else:
        details.append("No free cash flow data available.")

    # Potentially also look for a metric or ratio indicating R&D expenditure.
    # This is purely illustrative.
    # We'll just assume if there's an operating margin > 0, there's some buffer for R&D.

    op_margin_vals = [item.operating_margin for item in financial_line_items if item.operating_margin is not None]
    if op_margin_vals:
        above_10 = sum(1 for m in op_margin_vals if m > 0.10)
        if above_10 > 0:
            score += 1
            details.append("Operating margin above 10% in at least one period, indicating potential to fund R&D.")
        else:
            details.append("Operating margin not above 10%.")
    else:
        details.append("No operating margin data available.")

    return {
        "score": score,
        "details": "; ".join(details)
    }


def analyze_cathie_wood_valuation(financial_line_items: list, market_cap: float) -> dict:
    """
    Cathie Wood often focuses on long-term exponential growth potential. We can do
    a simplified approach looking for a large total addressable market (TAM) and the
    company's ability to capture a sizable portion.
    """
    if not financial_line_items or market_cap is None:
        return {
            "score": 0,
            "details": "Insufficient data for valuation"
        }

    latest = financial_line_items[-1]
    fcf = latest.free_cash_flow if latest.free_cash_flow else 0

    if fcf <= 0:
        return {
            "score": 0,
            "details": f"No positive FCF for valuation; FCF = {fcf}",
            "intrinsic_value": None
        }

    # Instead of a standard DCF, let's assume a higher growth rate for an innovative company.
    # Example values:
    growth_rate = 0.20  # 20% annual growth
    discount_rate = 0.15
    terminal_multiple = 25
    projection_years = 5

    present_value = 0
    for year in range(1, projection_years + 1):
        future_fcf = fcf * (1 + growth_rate) ** year
        pv = future_fcf / ((1 + discount_rate) ** year)
        present_value += pv

    # Terminal Value
    terminal_value = (fcf * (1 + growth_rate) ** projection_years * terminal_multiple) \
                     / ((1 + discount_rate) ** projection_years)
    intrinsic_value = present_value + terminal_value

    margin_of_safety = (intrinsic_value - market_cap) / market_cap

    score = 0
    if margin_of_safety > 0.5:
        score += 3
    elif margin_of_safety > 0.2:
        score += 1

    details = [
        f"Calculated intrinsic value: ~{intrinsic_value:,.2f}",
        f"Market cap: ~{market_cap:,.2f}",
        f"Margin of safety: {margin_of_safety:.2%}"
    ]

    return {
        "score": score,
        "details": "; ".join(details),
        "intrinsic_value": intrinsic_value,
        "margin_of_safety": margin_of_safety
    }


def generate_cathie_wood_output(
    ticker: str,
    analysis_data: dict[str, any],
    model_name: str,
    model_provider: str,
) -> CathieWoodSignal:
    """
    Generates investment decisions in the style of Cathie Wood.
    """
    template = ChatPromptTemplate.from_messages([
        (
            "system",
            """You are a Cathie Wood AI agent, making investment decisions using her principles:\n\n"
            "1. Seek companies leveraging disruptive innovation.\n"
            "2. Emphasize exponential growth potential, large TAM.\n"
            "3. Focus on technology, healthcare, or other future-facing sectors.\n"
            "4. Consider multi-year time horizons for potential breakthroughs.\n"
            "5. Accept higher volatility in pursuit of high returns.\n"
            "6. Evaluate management's vision and ability to invest in R&D.\n\n"
            "Rules:\n"
            "- Identify disruptive or breakthrough technology.\n"
            "- Evaluate strong potential for multi-year revenue growth.\n"
            "- Check if the company can scale effectively in a large market.\n"
            "- Use a growth-biased valuation approach.\n"
            "- Provide a data-driven recommendation (bullish, bearish, or neutral)."""
        ),
        (
            "human",
            """Based on the following analysis, create a Cathie Wood-style investment signal.\n\n"
            "Analysis Data for {ticker}:\n"
            "{analysis_data}\n\n"
            "Return the trading signal in this JSON format:\n"
            "{{\n  \"signal\": \"bullish/bearish/neutral\",\n  \"confidence\": float (0-100),\n  \"reasoning\": \"string\"\n}}"""
        )
    ])

    prompt = template.invoke({
        "analysis_data": json.dumps(analysis_data, indent=2),
        "ticker": ticker
    })

    def create_default_cathie_wood_signal():
        return CathieWoodSignal(
            signal="neutral",
            confidence=0.0,
            reasoning="Error in analysis, defaulting to neutral"
        )

    return call_llm(
        prompt=prompt,
        model_name=model_name,
        model_provider=model_provider,
        pydantic_model=CathieWoodSignal,
        agent_name="cathie_wood_agent",
        default_factory=create_default_cathie_wood_signal,
    )

# source: https://ark-invest.com