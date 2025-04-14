from graph.state import AgentState, show_agent_reasoning
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import json
from typing_extensions import Literal
from tools.api import get_financial_metrics, get_market_cap, search_line_items
from utils.llm import call_llm
from utils.progress import progress


class RalphWangerSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def ralph_wanger_agent(state: AgentState):
    """Analyzes stocks using Ralph Wanger's small-cap growth approach and LLM reasoning."""
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]

    # Collect all analysis for LLM reasoning
    analysis_data = {}
    wanger_analysis = {}

    for ticker in tickers:
        progress.update_status("ralph_wanger_agent", ticker, "Fetching financial metrics")
        # Fetch required data
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=5)

        progress.update_status("ralph_wanger_agent", ticker, "Gathering financial line items")
        financial_line_items = search_line_items(
            ticker,
            [
                "net_income",
                "total_assets",
                "total_liabilities",
                "cash_and_cash_equivalents",
                "revenue",
                "research_and_development_expenses",
                "capital_expenditure",
            ],
            end_date,
        )

        progress.update_status("ralph_wanger_agent", ticker, "Getting market cap")
        # Get current market cap
        market_cap = get_market_cap(ticker, end_date)

        progress.update_status("ralph_wanger_agent", ticker, "Analyzing small-cap growth criteria")
        # Analyze if it meets small-cap growth criteria
        small_cap_growth_analysis = analyze_small_cap_growth_criteria(market_cap, metrics)

        progress.update_status("ralph_wanger_agent", ticker, "Analyzing secular trends")
        # Analyze secular trends
        secular_trends_analysis = analyze_secular_trends(metrics, financial_line_items)

        progress.update_status("ralph_wanger_agent", ticker, "Analyzing growth metrics")
        # Analyze growth metrics
        growth_metrics_analysis = analyze_growth_metrics(financial_line_items, metrics)

        progress.update_status("ralph_wanger_agent", ticker, "Analyzing competitive advantage")
        # Analyze competitive advantage
        competitive_advantage_analysis = analyze_competitive_advantage(financial_line_items, metrics)

        # Calculate total score
        total_score = (
            small_cap_growth_analysis["score"] + 
            secular_trends_analysis["score"] + 
            growth_metrics_analysis["score"] + 
            competitive_advantage_analysis["score"]
        )
        
        max_possible_score = (
            small_cap_growth_analysis["max_score"] + 
            secular_trends_analysis["max_score"] + 
            growth_metrics_analysis["max_score"] + 
            competitive_advantage_analysis["max_score"]
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
            "small_cap_growth_analysis": small_cap_growth_analysis,
            "secular_trends_analysis": secular_trends_analysis,
            "growth_metrics_analysis": growth_metrics_analysis,
            "competitive_advantage_analysis": competitive_advantage_analysis,
            "market_cap": market_cap,
        }

        progress.update_status("ralph_wanger_agent", ticker, "Generating Ralph Wanger analysis")
        wanger_output = generate_wanger_output(
            ticker=ticker,
            analysis_data=analysis_data,
            model_name=state["metadata"]["model_name"],
            model_provider=state["metadata"]["model_provider"],
        )

        # Store analysis in consistent format with other agents
        wanger_analysis[ticker] = {
            "signal": wanger_output.signal,
            "confidence": wanger_output.confidence,
            "reasoning": wanger_output.reasoning,
        }

        progress.update_status("ralph_wanger_agent", ticker, "Done")

    # Create the message
    message = HumanMessage(content=json.dumps(wanger_analysis), name="ralph_wanger_agent")

    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(wanger_analysis, "Ralph Wanger Agent")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"]["ralph_wanger_agent"] = wanger_analysis

    return {"messages": [message], "data": state["data"]}


def analyze_small_cap_growth_criteria(market_cap: float, metrics: list) -> dict:
    """Analyze if the stock meets Ralph Wanger's small-cap growth criteria."""
    if not market_cap:
        return {"score": 0, "max_score": 3, "details": "Market cap data not available"}
    
    score = 0
    reasoning = []
    
    # Define small-cap thresholds (in USD)
    small_cap_threshold = 2_000_000_000  # $2 billion
    mid_cap_threshold = 10_000_000_000  # $10 billion
    
    # Check market cap size
    if market_cap < small_cap_threshold:
        score += 2
        reasoning.append(f"Small-cap stock (${market_cap/1_000_000:.1f}M) - prime Ralph Wanger territory")
    elif market_cap < mid_cap_threshold:
        score += 1
        reasoning.append(f"Mid-cap stock (${market_cap/1_000_000:.1f}M) - larger than Wanger's typical focus")
    else:
        reasoning.append(f"Large-cap stock (${market_cap/1_000_000:.1f}M) - outside Wanger's typical focus")
    
    # Check growth characteristics
    if metrics and len(metrics) > 0:
        latest_metrics = metrics[0]
        
        # Check P/E ratio for growth expectations
        if hasattr(latest_metrics, "pe_ratio") and latest_metrics.pe_ratio is not None:
            if latest_metrics.pe_ratio > 20 and latest_metrics.pe_ratio < 50:
                score += 1
                reasoning.append(f"Growth-oriented P/E ratio of {latest_metrics.pe_ratio:.1f}")
            elif latest_metrics.pe_ratio >= 50:
                reasoning.append(f"Extremely high P/E ratio of {latest_metrics.pe_ratio:.1f} - potentially overvalued")
            else:
                reasoning.append(f"Value-oriented P/E ratio of {latest_metrics.pe_ratio:.1f} - less growth expectation")
        else:
            reasoning.append("P/E ratio data not available")
    else:
        reasoning.append("Growth metrics data not available")
    
    return {
        "score": score,
        "max_score": 3,
        "details": "; ".join(reasoning),
        "market_cap_millions": market_cap / 1_000_000,
    }


def analyze_secular_trends(metrics: list, financial_line_items: list) -> dict:
    """Analyze if the company is positioned to benefit from secular trends (Wanger's 'cats and dogs' approach)."""
    if not metrics or not financial_line_items:
        return {"score": 0, "max_score": 3, "details": "Insufficient data for secular trends analysis"}
    
    score = 0
    reasoning = []
    
    # Check R&D investment as proxy for innovation and future trends
    latest = financial_line_items[0]
    if hasattr(latest, "research_and_development_expenses") and hasattr(latest, "revenue") and latest.research_and_development_expenses and latest.revenue:
        rd_to_revenue = latest.research_and_development_expenses / latest.revenue
        
        if rd_to_revenue > 0.15:
            score += 1
            reasoning.append(f"High R&D investment ({rd_to_revenue:.1%} of revenue) suggests innovation focus")
        elif rd_to_revenue > 0.08:
            score += 0.5
            reasoning.append(f"Moderate R&D investment ({rd_to_revenue:.1%} of revenue)")
        else:
            reasoning.append(f"Limited R&D investment ({rd_to_revenue:.1%} of revenue)")
    else:
        reasoning.append("R&D investment data not available")
    
    # Check capital expenditure as proxy for growth investment
    if hasattr(latest, "capital_expenditure") and hasattr(latest, "revenue") and latest.capital_expenditure and latest.revenue:
        capex_to_revenue = abs(latest.capital_expenditure) / latest.revenue  # capex is often negative in financial statements
        
        if capex_to_revenue > 0.12:
            score += 1
            reasoning.append(f"Significant capital investment ({capex_to_revenue:.1%} of revenue) for future growth")
        elif capex_to_revenue > 0.06:
            score += 0.5
            reasoning.append(f"Moderate capital investment ({capex_to_revenue:.1%} of revenue)")
        else:
            reasoning.append(f"Limited capital investment ({capex_to_revenue:.1%} of revenue)")
    else:
        reasoning.append("Capital expenditure data not available")
    
    # Check revenue growth acceleration as proxy for secular trend benefit
    if len(financial_line_items) >= 3 and all(hasattr(item, "revenue") for item in financial_line_items[:3]):
        if financial_line_items[1].revenue and financial_line_items[2].revenue:
            growth_previous = (financial_line_items[1].revenue - financial_line_items[2].revenue) / financial_line_items[2].revenue
            growth_current = (financial_line_items[0].revenue - financial_line_items[1].revenue) / financial_line_items[1].revenue
            
            growth_acceleration = growth_current - growth_previous
            
            if growth_acceleration > 0.05:
                score += 1
                reasoning.append(f"Accelerating revenue growth ({growth_acceleration:.1%} increase) suggests secular trend benefit")
            elif growth_acceleration > 0:
                score += 0.5
                reasoning.append(f"Modest revenue growth acceleration ({growth_acceleration:.1%})")
            else:
                reasoning.append(f"Decelerating revenue growth ({growth_acceleration:.1%})")
        else:
            reasoning.append("Historical revenue data incomplete")
    else:
        reasoning.append("Insufficient historical data for revenue growth acceleration analysis")
    
    return {
        "score": score,
        "max_score": 3,
        "details": "; ".join(reasoning),
    }


def analyze_growth_metrics(financial_line_items: list, metrics: list) -> dict:
    """Analyze growth metrics based on Ralph Wanger's focus on sustainable growth."""
    if not financial_line_items or len(financial_line_items) < 3:
        return {"score": 0, "max_score": 3, "details": "Insufficient financial data for growth analysis"}
    
    score = 0
    reasoning = []
    
    # Check revenue growth
    if all(hasattr(item, "revenue") for item in financial_line_items[:3]):
        if financial_line_items[2].revenue and financial_line_items[2].revenue > 0:
            revenue_growth = (financial_line_items[0].revenue - financial_line_items[2].revenue) / financial_line_items[2].revenue
            
            if revenue_growth > 0.3:  # 30% growth over the period
                score += 1
                reasoning.append(f"Strong revenue growth of {revenue_growth:.1%} over recent periods")
            elif revenue_growth > 0.15:  # 15% growth over the period
                score += 0.5
                reasoning.append(f"Moderate revenue growth of {revenue_growth:.1%}")
            elif revenue_growth <= 0:
                reasoning.append(f"Declining revenue ({revenue_growth:.1%})")
            else:
                reasoning.append(f"Minimal revenue growth of {revenue_growth:.1%}")
        else:
            reasoning.append("Historical revenue data incomplete")
    else:
        reasoning.append("Revenue growth data not available")
    
    # Check earnings growth
    if all(hasattr(item, "net_income") for item in financial_line_items[:3]):
        # Filter out negative earnings periods for growth calculation
        earnings = [item.net_income for item in financial_line_items[:3] if item.net_income and item.net_income > 0]
        
        if len(earnings) >= 2:
            earnings_growth = (earnings[0] - earnings[-1]) / earnings[-1]
            
            if earnings_growth > 0.35:  # 35% growth
                score += 1
                reasoning.append(f"Strong earnings growth of {earnings_growth:.1%}")
            elif earnings_growth > 0.2:  # 20% growth
                score += 0.5
                reasoning.append(f"Moderate earnings growth of {earnings_growth:.1%}")
            elif earnings_growth <= 0:
                reasoning.append(f"Declining earnings ({earnings_growth:.1%})")
            else:
                reasoning.append(f"Minimal earnings growth of {earnings_growth:.1%}")
        else:
            reasoning.append("Insufficient positive earnings periods for growth calculation")
    else:
        reasoning.append("Earnings growth data not available")
    
    # Check return on invested capital (ROIC) - Wanger focused on efficient growth
    if metrics and len(metrics) > 0:
        latest_metrics = metrics[0]
        
        if hasattr(latest_metrics, "return_on_invested_capital") and latest_metrics.return_on_invested_capital is not None:
            if latest_metrics.return_on_invested_capital > 0.15:
                score += 1
                reasoning.append(f"Strong ROIC of {latest_metrics.return_on_invested_capital:.1%} indicates efficient growth")
            elif latest_metrics.return_on_invested_capital > 0.1:
                score += 0.5
                reasoning.append(f"Adequate ROIC of {latest_metrics.return_on_invested_capital:.1%}")
            else:
                reasoning.append(f"Low ROIC of {latest_metrics.return_on_invested_capital:.1%}")
        else:
            reasoning.append("ROIC data not available")
    else:
        reasoning.append("Metrics data not available for ROIC analysis")
    
    return {
        "score": score,
        "max_score": 3,
        "details": "; ".join(reasoning),
    }


def analyze_competitive_advantage(financial_line_items: list, metrics: list) -> dict:
    """Analyze competitive advantage based on Ralph Wanger's focus on companies with sustainable advantages."""
    if not financial_line_items or not metrics:
        return {"score": 0, "max_score": 3, "details": "Insufficient data for competitive advantage analysis"}
    
    score = 0
    reasoning = []
    
    latest = financial_line_items[0]
    latest_metrics = metrics[0] if metrics else None
    
    # Check operating margins as indicator of competitive advantage
    if latest_metrics and hasattr(latest_metrics, "operating_margin") and latest_metrics.operating_margin is not None:
        if latest_metrics.operating_margin > 0.2:
            score += 1
            reasoning.append(f"Strong operating margins ({latest_metrics.operating_margin:.1%}) suggest competitive advantage")
        elif latest_metrics.operating_margin > 0.12:
            score += 0.5
            reasoning.append(f"Adequate operating margins ({latest_metrics.operating_margin:.1%})")
        else:
            reasoning.append(f"Low operating margins ({latest_metrics.operating_margin:.1%})")
    else:
        reasoning.append("Operating margin data not available")
    
    # Check margin stability/improvement over time
    if len(metrics) >= 3:
        if all(hasattr(m, "operating_margin") and m.operating_margin is not None for m in metrics[:3]):
            margin_trend = metrics[0].operating_margin - metrics[2].operating_margin
            
            if margin_trend > 0.03:
                score += 1
                reasoning.append(f"Improving operating margins (+{margin_trend:.1%}) suggest strengthening competitive position")
            elif margin_trend > 0:
                score += 0.5
                reasoning.append(f"Slightly improving operating margins (+{margin_trend:.1%})")
            else:
                reasoning.append(f"Declining operating margins ({margin_trend:.1%})")
        else:
            reasoning.append("Historical operating margin data incomplete")
    else:
        reasoning.append("Insufficient historical data for margin trend analysis")
    
    # Check cash generation relative to assets (cash return on assets)
    if latest and hasattr(latest, "cash_and_cash_equivalents") and hasattr(latest, "total_assets") and latest.cash_and_cash_equivalents and latest.total_assets:
        cash_to_assets = latest.cash_and_cash_equivalents / latest.total_assets
        
        if cash_to_assets > 0.15:
            score += 1
            reasoning.append(f"Strong cash generation ({cash_to_assets:.1%} of assets) indicates business quality")
        elif cash_to_assets > 0.08:
            score += 0.5
            reasoning.append(f"Adequate cash generation ({cash_to_assets:.1%} of assets)")
        else:
            reasoning.append(f"Limited cash generation ({cash_to_assets:.1%} of assets)")
    else:
        reasoning.append("Cash generation data not available")
    
    return {
        "score": score,
        "max_score": 3,
        "details": "; ".join(reasoning),
    }


def generate_wanger_output(
    ticker: str,
    analysis_data: dict,
    model_name: str,
    model_provider: str,
) -> RalphWangerSignal:
    """Get investment decision from LLM with Ralph Wanger's principles"""
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a Ralph Wanger AI agent. Decide on investment signals based on Ralph Wanger's small-cap growth principles:
                - Small-Cap Focus: Concentrate on small companies with room to grow
                - Secular Trends: Identify companies benefiting from long-term trends (Wanger's "cats and dogs" approach)
                - Sustainable Growth: Look for companies with sustainable growth potential
                - Competitive Advantage: Seek businesses with durable competitive advantages
                - Long-term Perspective: Invest with a multi-year time horizon
                - Innovation Focus: Value companies investing in innovation and future growth
                - Reasonable Valuation: Pay attention to valuation, but prioritize growth potential
                - Management Quality: Prefer entrepreneurial management with vision

                When providing your reasoning, be thorough and specific by:
                1. Explaining how the company fits Ralph Wanger's small-cap growth criteria
                2. Highlighting the secular trends the company is positioned to benefit from
                3. Analyzing the growth metrics and their sustainability
                4. Discussing competitive advantages and business quality
                5. Providing quantitative evidence with specific numbers and percentages
                6. Concluding with a Wanger-style assessment of the investment opportunity
                7. Using Ralph Wanger's practical and sometimes witty voice in your explanation

                For example, if bullish: "This $[X]M market cap company is riding the secular trend of [specific trend], growing revenues at [X%] with improving margins..."
                For example, if bearish: "Despite being in the small-cap space, the combination of [specific issue] and [growth concern] doesn't provide the sustainable growth trajectory we seek..."

                Follow these guidelines strictly.
                """,
            ),
            (
                "human",
                """Based on the following data, create the investment signal as Ralph Wanger would:

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
    def create_default_ralph_wanger_signal():
        return RalphWangerSignal(signal="neutral", confidence=0.0, reasoning="Error in analysis, defaulting to neutral")

    return call_llm(
        prompt=prompt,
        model_name=model_name,
        model_provider=model_provider,
        pydantic_model=RalphWangerSignal,
        agent_name="ralph_wanger_agent",
        default_factory=create_default_ralph_wanger_signal,
    )
