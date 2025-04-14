from graph.state import AgentState, show_agent_reasoning
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import json
from typing_extensions import Literal
from tools.api import get_financial_metrics, get_market_cap, search_line_items
from utils.llm import call_llm
from utils.progress import progress


class WhitneyGeorgeSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def whitney_george_agent(state: AgentState):
    """Analyzes stocks using Whitney George's small-cap value approach and LLM reasoning."""
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]

    # Collect all analysis for LLM reasoning
    analysis_data = {}
    george_analysis = {}

    for ticker in tickers:
        progress.update_status("whitney_george_agent", ticker, "Fetching financial metrics")
        # Fetch required data
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=5)

        progress.update_status("whitney_george_agent", ticker, "Gathering financial line items")
        financial_line_items = search_line_items(
            ticker,
            [
                "net_income",
                "total_assets",
                "total_liabilities",
                "cash_and_cash_equivalents",
                "inventory",
                "property_plant_and_equipment_net",
                "revenue",
                "cost_of_goods_sold",
                "research_and_development_expenses",
            ],
            end_date,
        )

        progress.update_status("whitney_george_agent", ticker, "Getting market cap")
        # Get current market cap
        market_cap = get_market_cap(ticker, end_date)

        progress.update_status("whitney_george_agent", ticker, "Analyzing small-cap criteria")
        # Analyze if it meets small-cap criteria
        small_cap_analysis = analyze_small_cap_criteria(market_cap)

        progress.update_status("whitney_george_agent", ticker, "Analyzing tangible assets")
        # Analyze tangible assets
        tangible_assets_analysis = analyze_tangible_assets(financial_line_items)

        progress.update_status("whitney_george_agent", ticker, "Analyzing profitability")
        # Analyze profitability
        profitability_analysis = analyze_profitability(financial_line_items, metrics)

        progress.update_status("whitney_george_agent", ticker, "Analyzing valuation")
        # Analyze valuation
        valuation_analysis = analyze_valuation(metrics, market_cap)

        # Calculate total score
        total_score = (
            small_cap_analysis["score"] + 
            tangible_assets_analysis["score"] + 
            profitability_analysis["score"] + 
            valuation_analysis["score"]
        )
        
        max_possible_score = (
            small_cap_analysis["max_score"] + 
            tangible_assets_analysis["max_score"] + 
            profitability_analysis["max_score"] + 
            valuation_analysis["max_score"]
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
            "small_cap_analysis": small_cap_analysis,
            "tangible_assets_analysis": tangible_assets_analysis,
            "profitability_analysis": profitability_analysis,
            "valuation_analysis": valuation_analysis,
            "market_cap": market_cap,
        }

        progress.update_status("whitney_george_agent", ticker, "Generating Whitney George analysis")
        george_output = generate_george_output(
            ticker=ticker,
            analysis_data=analysis_data,
            model_name=state["metadata"]["model_name"],
            model_provider=state["metadata"]["model_provider"],
        )

        # Store analysis in consistent format with other agents
        george_analysis[ticker] = {
            "signal": george_output.signal,
            "confidence": george_output.confidence,
            "reasoning": george_output.reasoning,
        }

        progress.update_status("whitney_george_agent", ticker, "Done")

    # Create the message
    message = HumanMessage(content=json.dumps(george_analysis), name="whitney_george_agent")

    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(george_analysis, "Whitney George Agent")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"]["whitney_george_agent"] = george_analysis

    return {"messages": [message], "data": state["data"]}


def analyze_small_cap_criteria(market_cap: float) -> dict:
    """Analyze if the stock meets small-cap criteria."""
    if not market_cap:
        return {"score": 0, "max_score": 3, "details": "Market cap data not available"}
    
    score = 0
    reasoning = []
    
    # Define small-cap thresholds (in USD)
    micro_cap_threshold = 300_000_000  # $300 million
    small_cap_threshold = 2_000_000_000  # $2 billion
    
    # Check market cap size
    if market_cap < micro_cap_threshold:
        score += 3
        reasoning.append(f"Micro-cap stock (${market_cap/1_000_000:.1f}M) - prime Whitney George territory")
    elif market_cap < small_cap_threshold:
        score += 2
        reasoning.append(f"Small-cap stock (${market_cap/1_000_000:.1f}M) - within Whitney George focus area")
    else:
        reasoning.append(f"Not a small-cap stock (${market_cap/1_000_000:.1f}M) - outside Whitney George's typical focus")
    
    return {
        "score": score,
        "max_score": 3,
        "details": "; ".join(reasoning),
        "market_cap_millions": market_cap / 1_000_000,
    }


def analyze_tangible_assets(financial_line_items: list) -> dict:
    """Analyze tangible assets based on Whitney George's focus on asset-rich businesses."""
    if not financial_line_items:
        return {"score": 0, "max_score": 3, "details": "Insufficient financial data"}
    
    score = 0
    reasoning = []
    
    latest = financial_line_items[0]
    
    # Check for tangible assets
    tangible_assets = 0
    if hasattr(latest, "property_plant_and_equipment_net") and latest.property_plant_and_equipment_net:
        tangible_assets += latest.property_plant_and_equipment_net
        reasoning.append(f"Property, plant & equipment: ${latest.property_plant_and_equipment_net/1_000_000:.1f}M")
    
    if hasattr(latest, "inventory") and latest.inventory:
        tangible_assets += latest.inventory
        reasoning.append(f"Inventory: ${latest.inventory/1_000_000:.1f}M")
    
    if hasattr(latest, "cash_and_cash_equivalents") and latest.cash_and_cash_equivalents:
        tangible_assets += latest.cash_and_cash_equivalents
        reasoning.append(f"Cash & equivalents: ${latest.cash_and_cash_equivalents/1_000_000:.1f}M")
    
    # Calculate tangible assets to total assets ratio
    if hasattr(latest, "total_assets") and latest.total_assets and latest.total_assets > 0:
        tangible_ratio = tangible_assets / latest.total_assets
        
        if tangible_ratio > 0.7:
            score += 2
            reasoning.append(f"High tangible asset ratio ({tangible_ratio:.1%}) - asset-rich business")
        elif tangible_ratio > 0.5:
            score += 1
            reasoning.append(f"Moderate tangible asset ratio ({tangible_ratio:.1%})")
        else:
            reasoning.append(f"Low tangible asset ratio ({tangible_ratio:.1%}) - less asset-intensive")
    else:
        reasoning.append("Total assets data not available for ratio calculation")
    
    # Check for asset growth
    if len(financial_line_items) >= 3 and all(hasattr(item, "total_assets") for item in financial_line_items[:3]):
        if financial_line_items[2].total_assets and financial_line_items[2].total_assets > 0:
            asset_growth = (financial_line_items[0].total_assets - financial_line_items[2].total_assets) / financial_line_items[2].total_assets
            
            if asset_growth > 0.15:
                score += 1
                reasoning.append(f"Strong asset growth ({asset_growth:.1%} over recent periods)")
            elif asset_growth > 0.05:
                score += 0.5
                reasoning.append(f"Moderate asset growth ({asset_growth:.1%})")
            elif asset_growth < 0:
                reasoning.append(f"Declining assets ({asset_growth:.1%})")
            else:
                reasoning.append(f"Minimal asset growth ({asset_growth:.1%})")
        else:
            reasoning.append("Historical asset data incomplete for growth calculation")
    else:
        reasoning.append("Insufficient historical data for asset growth analysis")
    
    return {
        "score": score,
        "max_score": 3,
        "details": "; ".join(reasoning),
    }


def analyze_profitability(financial_line_items: list, metrics: list) -> dict:
    """Analyze profitability based on Whitney George's focus on profitable businesses."""
    if not financial_line_items or not metrics:
        return {"score": 0, "max_score": 3, "details": "Insufficient financial data"}
    
    score = 0
    reasoning = []
    
    latest = financial_line_items[0]
    latest_metrics = metrics[0] if metrics else None
    
    # Check for consistent profitability
    if len(financial_line_items) >= 3 and all(hasattr(item, "net_income") for item in financial_line_items[:3]):
        profitable_periods = sum(1 for item in financial_line_items[:3] if item.net_income and item.net_income > 0)
        
        if profitable_periods == 3:
            score += 1
            reasoning.append("Consistently profitable across recent periods")
        elif profitable_periods == 2:
            score += 0.5
            reasoning.append("Profitable in 2 of 3 recent periods")
        elif profitable_periods == 1:
            reasoning.append("Profitable in only 1 of 3 recent periods")
        else:
            reasoning.append("Not profitable in recent periods")
    else:
        reasoning.append("Insufficient historical data for profitability analysis")
    
    # Check gross margins
    if latest_metrics and hasattr(latest_metrics, "gross_margin") and latest_metrics.gross_margin is not None:
        if latest_metrics.gross_margin > 0.4:
            score += 1
            reasoning.append(f"Strong gross margins ({latest_metrics.gross_margin:.1%})")
        elif latest_metrics.gross_margin > 0.25:
            score += 0.5
            reasoning.append(f"Adequate gross margins ({latest_metrics.gross_margin:.1%})")
        else:
            reasoning.append(f"Low gross margins ({latest_metrics.gross_margin:.1%})")
    elif latest and hasattr(latest, "revenue") and hasattr(latest, "cost_of_goods_sold") and latest.revenue and latest.cost_of_goods_sold:
        gross_margin = (latest.revenue - latest.cost_of_goods_sold) / latest.revenue
        
        if gross_margin > 0.4:
            score += 1
            reasoning.append(f"Strong gross margins ({gross_margin:.1%})")
        elif gross_margin > 0.25:
            score += 0.5
            reasoning.append(f"Adequate gross margins ({gross_margin:.1%})")
        else:
            reasoning.append(f"Low gross margins ({gross_margin:.1%})")
    else:
        reasoning.append("Gross margin data not available")
    
    # Check R&D investment (Whitney George often looks for companies investing in future growth)
    if latest and hasattr(latest, "research_and_development_expenses") and hasattr(latest, "revenue") and latest.research_and_development_expenses and latest.revenue:
        rd_to_revenue = latest.research_and_development_expenses / latest.revenue
        
        if rd_to_revenue > 0.1:
            score += 1
            reasoning.append(f"Significant R&D investment ({rd_to_revenue:.1%} of revenue)")
        elif rd_to_revenue > 0.05:
            score += 0.5
            reasoning.append(f"Moderate R&D investment ({rd_to_revenue:.1%} of revenue)")
        else:
            reasoning.append(f"Limited R&D investment ({rd_to_revenue:.1%} of revenue)")
    else:
        reasoning.append("R&D investment data not available")
    
    return {
        "score": score,
        "max_score": 3,
        "details": "; ".join(reasoning),
    }


def analyze_valuation(metrics: list, market_cap: float) -> dict:
    """Analyze valuation based on Whitney George's value-oriented approach."""
    if not metrics or not market_cap:
        return {"score": 0, "max_score": 3, "details": "Insufficient valuation data"}
    
    score = 0
    reasoning = []
    
    latest_metrics = metrics[0]
    
    # Check P/E ratio
    if hasattr(latest_metrics, "pe_ratio") and latest_metrics.pe_ratio is not None:
        if latest_metrics.pe_ratio < 15:
            score += 1
            reasoning.append(f"Attractive P/E ratio of {latest_metrics.pe_ratio:.1f}")
        elif latest_metrics.pe_ratio < 25:
            score += 0.5
            reasoning.append(f"Reasonable P/E ratio of {latest_metrics.pe_ratio:.1f}")
        else:
            reasoning.append(f"Elevated P/E ratio of {latest_metrics.pe_ratio:.1f}")
    else:
        reasoning.append("P/E ratio data not available")
    
    # Check P/B ratio
    if hasattr(latest_metrics, "price_to_book") and latest_metrics.price_to_book is not None:
        if latest_metrics.price_to_book < 1.5:
            score += 1
            reasoning.append(f"Attractive P/B ratio of {latest_metrics.price_to_book:.1f}")
        elif latest_metrics.price_to_book < 3:
            score += 0.5
            reasoning.append(f"Reasonable P/B ratio of {latest_metrics.price_to_book:.1f}")
        else:
            reasoning.append(f"Elevated P/B ratio of {latest_metrics.price_to_book:.1f}")
    else:
        reasoning.append("P/B ratio data not available")
    
    # Check EV/EBITDA
    if hasattr(latest_metrics, "ev_to_ebitda") and latest_metrics.ev_to_ebitda is not None:
        if latest_metrics.ev_to_ebitda < 8:
            score += 1
            reasoning.append(f"Attractive EV/EBITDA of {latest_metrics.ev_to_ebitda:.1f}")
        elif latest_metrics.ev_to_ebitda < 12:
            score += 0.5
            reasoning.append(f"Reasonable EV/EBITDA of {latest_metrics.ev_to_ebitda:.1f}")
        else:
            reasoning.append(f"Elevated EV/EBITDA of {latest_metrics.ev_to_ebitda:.1f}")
    else:
        reasoning.append("EV/EBITDA data not available")
    
    return {
        "score": score,
        "max_score": 3,
        "details": "; ".join(reasoning),
    }


def generate_george_output(
    ticker: str,
    analysis_data: dict,
    model_name: str,
    model_provider: str,
) -> WhitneyGeorgeSignal:
    """Get investment decision from LLM with Whitney George's principles"""
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a Whitney George AI agent. Decide on investment signals based on Whitney George's small-cap value principles:
                - Small-Cap Focus: Concentrate on small and micro-cap companies
                - Tangible Assets: Prefer businesses with significant tangible assets
                - Value Orientation: Look for undervalued companies trading below intrinsic value
                - Quality Business: Focus on profitable companies with sustainable business models
                - Long-term Perspective: Invest with a multi-year time horizon
                - Contrarian Approach: Willing to invest in out-of-favor sectors or companies
                - Margin of Safety: Require a significant discount to estimated intrinsic value
                - Management Quality: Seek aligned management with skin in the game

                When providing your reasoning, be thorough and specific by:
                1. Explaining how the company fits Whitney George's small-cap value criteria
                2. Highlighting the tangible asset base and its importance to the business
                3. Analyzing the valuation metrics and margin of safety
                4. Discussing profitability and business quality
                5. Providing quantitative evidence with specific numbers and percentages
                6. Concluding with a George-style assessment of the investment opportunity
                7. Using Whitney George's practical and value-oriented voice in your explanation

                For example, if bullish: "This $[X]M market cap company has [specific tangible assets] trading at just [valuation metric], providing a significant margin of safety..."
                For example, if bearish: "Despite being in the small-cap space, the combination of [specific issue] and [valuation concern] doesn't provide the margin of safety we require..."

                Follow these guidelines strictly.
                """,
            ),
            (
                "human",
                """Based on the following data, create the investment signal as Whitney George would:

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
    def create_default_whitney_george_signal():
        return WhitneyGeorgeSignal(signal="neutral", confidence=0.0, reasoning="Error in analysis, defaulting to neutral")

    return call_llm(
        prompt=prompt,
        model_name=model_name,
        model_provider=model_provider,
        pydantic_model=WhitneyGeorgeSignal,
        agent_name="whitney_george_agent",
        default_factory=create_default_whitney_george_signal,
    )
