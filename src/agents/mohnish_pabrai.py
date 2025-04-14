from graph.state import AgentState, show_agent_reasoning
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import json
from typing_extensions import Literal
from tools.api import get_financial_metrics, get_market_cap, search_line_items
from utils.llm import call_llm
from utils.progress import progress


class MohnishPabraiSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def mohnish_pabrai_agent(state: AgentState):
    """Analyzes stocks using Mohnish Pabrai's focused value approach and LLM reasoning."""
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]

    # Collect all analysis for LLM reasoning
    analysis_data = {}
    pabrai_analysis = {}

    for ticker in tickers:
        progress.update_status("mohnish_pabrai_agent", ticker, "Fetching financial metrics")
        # Fetch required data
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=5)

        progress.update_status("mohnish_pabrai_agent", ticker, "Gathering financial line items")
        financial_line_items = search_line_items(
            ticker,
            [
                "net_income",
                "total_assets",
                "total_liabilities",
                "total_debt",
                "cash_and_cash_equivalents",
                "revenue",
                "operating_income",
                "free_cash_flow",
            ],
            end_date,
        )

        progress.update_status("mohnish_pabrai_agent", ticker, "Getting market cap")
        # Get current market cap
        market_cap = get_market_cap(ticker, end_date)

        progress.update_status("mohnish_pabrai_agent", ticker, "Analyzing margin of safety")
        # Analyze margin of safety
        margin_of_safety_analysis = analyze_margin_of_safety(market_cap, financial_line_items, metrics)

        progress.update_status("mohnish_pabrai_agent", ticker, "Analyzing business simplicity")
        # Analyze business simplicity
        business_simplicity_analysis = analyze_business_simplicity(financial_line_items)

        progress.update_status("mohnish_pabrai_agent", ticker, "Analyzing moat and durability")
        # Analyze moat and durability
        moat_analysis = analyze_moat_and_durability(financial_line_items, metrics)

        progress.update_status("mohnish_pabrai_agent", ticker, "Analyzing distress potential")
        # Analyze distress potential
        distress_analysis = analyze_distress_potential(financial_line_items, metrics)

        # Calculate total score
        total_score = (
            margin_of_safety_analysis["score"] + 
            business_simplicity_analysis["score"] + 
            moat_analysis["score"] + 
            distress_analysis["score"]
        )
        
        max_possible_score = (
            margin_of_safety_analysis["max_score"] + 
            business_simplicity_analysis["max_score"] + 
            moat_analysis["max_score"] + 
            distress_analysis["max_score"]
        )

        # Generate trading signal based on total score
        if total_score >= 0.7 * max_possible_score:
            signal = "bullish"
        elif total_score <= 0.3 * max_possible_score:
            signal = "bearish"
        else:
            signal = "neutral"

        # Combine all analysis results
        analysis_data[ticker] = {
            "signal": signal,
            "score": total_score,
            "max_score": max_possible_score,
            "margin_of_safety_analysis": margin_of_safety_analysis,
            "business_simplicity_analysis": business_simplicity_analysis,
            "moat_analysis": moat_analysis,
            "distress_analysis": distress_analysis,
            "market_cap": market_cap,
        }

        progress.update_status("mohnish_pabrai_agent", ticker, "Generating Mohnish Pabrai analysis")
        pabrai_output = generate_pabrai_output(
            ticker=ticker,
            analysis_data=analysis_data,
            model_name=state["metadata"]["model_name"],
            model_provider=state["metadata"]["model_provider"],
        )

        # Store analysis in consistent format with other agents
        pabrai_analysis[ticker] = {
            "signal": pabrai_output.signal,
            "confidence": pabrai_output.confidence,
            "reasoning": pabrai_output.reasoning,
        }

        progress.update_status("mohnish_pabrai_agent", ticker, "Done")

    # Create the message
    message = HumanMessage(content=json.dumps(pabrai_analysis), name="mohnish_pabrai_agent")

    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(pabrai_analysis, "Mohnish Pabrai Agent")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"]["mohnish_pabrai_agent"] = pabrai_analysis

    return {"messages": [message], "data": state["data"]}


def analyze_margin_of_safety(market_cap: float, financial_line_items: list, metrics: list) -> dict:
    """Analyze margin of safety based on Pabrai's focus on low-risk, high-uncertainty situations."""
    if not market_cap or not financial_line_items:
        return {"score": 0, "max_score": 4, "details": "Insufficient data for margin of safety analysis"}
    
    score = 0
    reasoning = []
    
    latest = financial_line_items[0]
    
    # Check P/E ratio for value
    if metrics and len(metrics) > 0:
        latest_metrics = metrics[0]
        
        if hasattr(latest_metrics, "pe_ratio") and latest_metrics.pe_ratio is not None:
            if latest_metrics.pe_ratio < 10:
                score += 1
                reasoning.append(f"Very low P/E ratio of {latest_metrics.pe_ratio:.1f} provides significant margin of safety")
            elif latest_metrics.pe_ratio < 15:
                score += 0.5
                reasoning.append(f"Reasonable P/E ratio of {latest_metrics.pe_ratio:.1f}")
            else:
                reasoning.append(f"Elevated P/E ratio of {latest_metrics.pe_ratio:.1f} offers limited margin of safety")
        else:
            reasoning.append("P/E ratio data not available")
    else:
        reasoning.append("Metrics data not available for P/E analysis")
    
    # Check price to book value
    if metrics and len(metrics) > 0:
        latest_metrics = metrics[0]
        
        if hasattr(latest_metrics, "price_to_book") and latest_metrics.price_to_book is not None:
            if latest_metrics.price_to_book < 1:
                score += 1
                reasoning.append(f"Trading below book value (P/B: {latest_metrics.price_to_book:.1f}) - classic Pabrai territory")
            elif latest_metrics.price_to_book < 2:
                score += 0.5
                reasoning.append(f"Reasonable price to book ratio of {latest_metrics.price_to_book:.1f}")
            else:
                reasoning.append(f"Elevated price to book ratio of {latest_metrics.price_to_book:.1f}")
        else:
            reasoning.append("Price to book ratio data not available")
    else:
        reasoning.append("Metrics data not available for price to book analysis")
    
    # Check EV/EBITDA
    if metrics and len(metrics) > 0:
        latest_metrics = metrics[0]
        
        if hasattr(latest_metrics, "ev_to_ebitda") and latest_metrics.ev_to_ebitda is not None:
            if latest_metrics.ev_to_ebitda < 6:
                score += 1
                reasoning.append(f"Very low EV/EBITDA of {latest_metrics.ev_to_ebitda:.1f} suggests significant undervaluation")
            elif latest_metrics.ev_to_ebitda < 10:
                score += 0.5
                reasoning.append(f"Reasonable EV/EBITDA of {latest_metrics.ev_to_ebitda:.1f}")
            else:
                reasoning.append(f"Elevated EV/EBITDA of {latest_metrics.ev_to_ebitda:.1f}")
        else:
            reasoning.append("EV/EBITDA data not available")
    else:
        reasoning.append("Metrics data not available for EV/EBITDA analysis")
    
    # Check price to free cash flow
    if hasattr(latest, "free_cash_flow") and latest.free_cash_flow and latest.free_cash_flow > 0:
        price_to_fcf = market_cap / latest.free_cash_flow
        
        if price_to_fcf < 8:
            score += 1
            reasoning.append(f"Very low price to free cash flow ratio of {price_to_fcf:.1f}")
        elif price_to_fcf < 15:
            score += 0.5
            reasoning.append(f"Reasonable price to free cash flow ratio of {price_to_fcf:.1f}")
        else:
            reasoning.append(f"Elevated price to free cash flow ratio of {price_to_fcf:.1f}")
    else:
        reasoning.append("Free cash flow data not available or negative")
    
    return {
        "score": score,
        "max_score": 4,
        "details": "; ".join(reasoning),
    }


def analyze_business_simplicity(financial_line_items: list) -> dict:
    """Analyze business simplicity based on Pabrai's preference for simple, understandable businesses."""
    if not financial_line_items or len(financial_line_items) < 3:
        return {"score": 0, "max_score": 2, "details": "Insufficient financial data for business simplicity analysis"}
    
    score = 0
    reasoning = []
    
    # Check revenue consistency (proxy for business simplicity)
    if all(hasattr(item, "revenue") for item in financial_line_items[:3]):
        revenues = [item.revenue for item in financial_line_items[:3] if item.revenue]
        
        if len(revenues) >= 3:
            # Calculate coefficient of variation (standard deviation / mean)
            mean_revenue = sum(revenues) / len(revenues)
            variance = sum((r - mean_revenue) ** 2 for r in revenues) / len(revenues)
            std_dev = variance ** 0.5
            cv = std_dev / mean_revenue if mean_revenue else float('inf')
            
            if cv < 0.15:
                score += 1
                reasoning.append(f"Highly consistent revenue pattern (CV: {cv:.2f}) suggests simple, predictable business")
            elif cv < 0.3:
                score += 0.5
                reasoning.append(f"Moderately consistent revenue pattern (CV: {cv:.2f})")
            else:
                reasoning.append(f"Volatile revenue pattern (CV: {cv:.2f}) suggests complex or unpredictable business")
        else:
            reasoning.append("Insufficient revenue data points")
    else:
        reasoning.append("Revenue consistency data not available")
    
    # Check operating margin consistency (another proxy for business simplicity)
    if all(hasattr(item, "operating_income") and hasattr(item, "revenue") for item in financial_line_items[:3]):
        operating_margins = []
        for item in financial_line_items[:3]:
            if item.revenue and item.revenue > 0 and item.operating_income is not None:
                operating_margins.append(item.operating_income / item.revenue)
        
        if len(operating_margins) >= 3:
            # Calculate coefficient of variation
            mean_margin = sum(operating_margins) / len(operating_margins)
            if mean_margin > 0:
                variance = sum((m - mean_margin) ** 2 for m in operating_margins) / len(operating_margins)
                std_dev = variance ** 0.5
                cv = std_dev / mean_margin
                
                if cv < 0.2:
                    score += 1
                    reasoning.append(f"Highly consistent operating margins (CV: {cv:.2f}) suggest simple business model")
                elif cv < 0.4:
                    score += 0.5
                    reasoning.append(f"Moderately consistent operating margins (CV: {cv:.2f})")
                else:
                    reasoning.append(f"Volatile operating margins (CV: {cv:.2f}) suggest complex business dynamics")
            else:
                reasoning.append("Negative or zero mean operating margin")
        else:
            reasoning.append("Insufficient operating margin data points")
    else:
        reasoning.append("Operating margin consistency data not available")
    
    return {
        "score": score,
        "max_score": 2,
        "details": "; ".join(reasoning),
    }


def analyze_moat_and_durability(financial_line_items: list, metrics: list) -> dict:
    """Analyze business moat and durability based on Pabrai's focus on enduring businesses."""
    if not financial_line_items or not metrics:
        return {"score": 0, "max_score": 3, "details": "Insufficient data for moat analysis"}
    
    score = 0
    reasoning = []
    
    # Check return on equity (ROE)
    if metrics and len(metrics) >= 3:
        roes = [m.return_on_equity for m in metrics[:3] if hasattr(m, "return_on_equity") and m.return_on_equity is not None]
        
        if len(roes) >= 3:
            avg_roe = sum(roes) / len(roes)
            
            if avg_roe > 0.2:
                score += 1
                reasoning.append(f"Exceptional ROE ({avg_roe:.1%}) suggests strong competitive advantage")
            elif avg_roe > 0.15:
                score += 0.5
                reasoning.append(f"Good ROE ({avg_roe:.1%}) indicates solid business economics")
            else:
                reasoning.append(f"Modest ROE ({avg_roe:.1%})")
        else:
            reasoning.append("Insufficient ROE data points")
    else:
        reasoning.append("ROE data not available")
    
    # Check operating margin
    if metrics and len(metrics) > 0:
        latest_metrics = metrics[0]
        
        if hasattr(latest_metrics, "operating_margin") and latest_metrics.operating_margin is not None:
            if latest_metrics.operating_margin > 0.2:
                score += 1
                reasoning.append(f"High operating margin ({latest_metrics.operating_margin:.1%}) indicates pricing power")
            elif latest_metrics.operating_margin > 0.12:
                score += 0.5
                reasoning.append(f"Decent operating margin ({latest_metrics.operating_margin:.1%})")
            else:
                reasoning.append(f"Low operating margin ({latest_metrics.operating_margin:.1%})")
        else:
            reasoning.append("Operating margin data not available")
    else:
        reasoning.append("Metrics data not available for operating margin analysis")
    
    # Check revenue growth consistency
    if len(financial_line_items) >= 3 and all(hasattr(item, "revenue") for item in financial_line_items[:3]):
        if all(item.revenue and item.revenue > 0 for item in financial_line_items[:3]):
            growth_rates = [
                (financial_line_items[i].revenue - financial_line_items[i+1].revenue) / financial_line_items[i+1].revenue
                for i in range(len(financial_line_items[:3]) - 1)
            ]
            
            if len(growth_rates) >= 2:
                all_positive = all(rate > 0 for rate in growth_rates)
                
                if all_positive and min(growth_rates) > 0.05:
                    score += 1
                    reasoning.append(f"Consistent positive revenue growth (min: {min(growth_rates):.1%}) indicates durable business")
                elif all_positive:
                    score += 0.5
                    reasoning.append(f"Positive but modest revenue growth (min: {min(growth_rates):.1%})")
                else:
                    reasoning.append("Inconsistent revenue growth pattern")
            else:
                reasoning.append("Insufficient growth rate data points")
        else:
            reasoning.append("Revenue data contains zero or negative values")
    else:
        reasoning.append("Revenue growth consistency data not available")
    
    return {
        "score": score,
        "max_score": 3,
        "details": "; ".join(reasoning),
    }


def analyze_distress_potential(financial_line_items: list, metrics: list) -> dict:
    """Analyze potential for financial distress based on Pabrai's focus on avoiding permanent capital loss."""
    if not financial_line_items:
        return {"score": 0, "max_score": 3, "details": "Insufficient financial data for distress analysis"}
    
    score = 0
    reasoning = []
    
    latest = financial_line_items[0]
    
    # Check debt to equity ratio
    if metrics and len(metrics) > 0:
        latest_metrics = metrics[0]
        
        if hasattr(latest_metrics, "debt_to_equity") and latest_metrics.debt_to_equity is not None:
            if latest_metrics.debt_to_equity < 0.3:
                score += 1
                reasoning.append(f"Very low debt to equity ratio ({latest_metrics.debt_to_equity:.1f}) minimizes financial risk")
            elif latest_metrics.debt_to_equity < 0.7:
                score += 0.5
                reasoning.append(f"Moderate debt to equity ratio ({latest_metrics.debt_to_equity:.1f})")
            elif latest_metrics.debt_to_equity > 2:
                reasoning.append(f"High debt to equity ratio ({latest_metrics.debt_to_equity:.1f}) increases financial risk")
            else:
                reasoning.append(f"Elevated debt to equity ratio ({latest_metrics.debt_to_equity:.1f})")
        else:
            reasoning.append("Debt to equity ratio data not available")
    else:
        reasoning.append("Metrics data not available for debt to equity analysis")
    
    # Check interest coverage ratio
    if hasattr(latest, "operating_income") and hasattr(latest, "total_debt") and latest.operating_income and latest.total_debt:
        # Estimate interest expense as 5% of total debt
        estimated_interest = latest.total_debt * 0.05
        
        if estimated_interest > 0:
            interest_coverage = latest.operating_income / estimated_interest
            
            if interest_coverage > 10:
                score += 1
                reasoning.append(f"Excellent interest coverage ratio (est. {interest_coverage:.1f}x)")
            elif interest_coverage > 5:
                score += 0.5
                reasoning.append(f"Good interest coverage ratio (est. {interest_coverage:.1f}x)")
            elif interest_coverage < 2:
                reasoning.append(f"Poor interest coverage ratio (est. {interest_coverage:.1f}x) indicates potential distress")
            else:
                reasoning.append(f"Adequate interest coverage ratio (est. {interest_coverage:.1f}x)")
        else:
            reasoning.append("Zero estimated interest expense")
    else:
        reasoning.append("Interest coverage ratio data not available")
    
    # Check cash to debt ratio
    if hasattr(latest, "cash_and_cash_equivalents") and hasattr(latest, "total_debt"):
        if latest.total_debt and latest.total_debt > 0:
            cash_to_debt = latest.cash_and_cash_equivalents / latest.total_debt
            
            if cash_to_debt > 1:
                score += 1
                reasoning.append(f"Cash exceeds total debt (ratio: {cash_to_debt:.1f}x) - minimal financial risk")
            elif cash_to_debt > 0.5:
                score += 0.5
                reasoning.append(f"Substantial cash relative to debt (ratio: {cash_to_debt:.1f}x)")
            else:
                reasoning.append(f"Limited cash relative to debt (ratio: {cash_to_debt:.1f}x)")
        elif latest.cash_and_cash_equivalents > 0:
            score += 1
            reasoning.append("Cash positive with minimal or no debt - excellent financial position")
        else:
            reasoning.append("Cash and debt data incomplete")
    else:
        reasoning.append("Cash to debt ratio data not available")
    
    return {
        "score": score,
        "max_score": 3,
        "details": "; ".join(reasoning),
    }


def generate_pabrai_output(
    ticker: str,
    analysis_data: dict,
    model_name: str,
    model_provider: str,
) -> MohnishPabraiSignal:
    """Get investment decision from LLM with Mohnish Pabrai's principles"""
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a Mohnish Pabrai AI agent. Decide on investment signals based on Pabrai's focused value principles:
                - Heads I Win, Tails I Don't Lose Much: Focus on asymmetric risk-reward opportunities
                - Margin of Safety: Require significant discount to intrinsic value
                - Few Bets, Big Bets: Make concentrated investments in high-conviction ideas
                - Simple Businesses: Prefer simple, understandable business models
                - Distress Avoidance: Avoid businesses with high financial or operational risk
                - Cloning: Adapt successful investment approaches from other great investors
                - Low-risk, High-uncertainty: Seek situations with low risk of permanent capital loss but high uncertainty
                - Patience: Wait for fat pitches and act decisively when they appear

                When providing your reasoning, be thorough and specific by:
                1. Explaining how the company fits Pabrai's focused value criteria
                2. Highlighting the margin of safety and asymmetric risk-reward profile
                3. Analyzing business simplicity and understandability
                4. Discussing moat characteristics and business durability
                5. Evaluating financial distress potential
                6. Providing quantitative evidence with specific numbers and percentages
                7. Concluding with a Pabrai-style assessment of the investment opportunity
                8. Using Mohnish Pabrai's straightforward and practical voice in your explanation

                For example, if bullish: "This presents a classic 'heads I win, tails I don't lose much' situation with [specific factors] providing downside protection while [specific factors] offer significant upside potential..."
                For example, if bearish: "The combination of [specific issue] and [valuation concern] creates too much risk of permanent capital loss without sufficient upside to justify investment..."

                Follow these guidelines strictly.
                """,
            ),
            (
                "human",
                """Based on the following data, create the investment signal as Mohnish Pabrai would:

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

    prompt = template.invoke({"analysis_data": json.dumps(analysis_data, indent=2), "ticker": ticker})

    # Default fallback signal in case parsing fails
    def create_default_mohnish_pabrai_signal():
        return MohnishPabraiSignal(signal="neutral", confidence=0.0, reasoning="Error in analysis, defaulting to neutral")

    return call_llm(
        prompt=prompt,
        model_name=model_name,
        model_provider=model_provider,
        pydantic_model=MohnishPabraiSignal,
        agent_name="mohnish_pabrai_agent",
        default_factory=create_default_mohnish_pabrai_signal,
    )
