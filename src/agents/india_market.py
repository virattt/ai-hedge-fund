"""
India Market Agent - Provides India-specific market intelligence

Analyzes FII/DII flows, promoter activity, and SEBI-style risk filters
to provide market bias signals (risk-on / risk-off / domestic support)
"""

from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import json
from typing_extensions import Literal
from src.utils.llm import call_llm
from src.utils.progress import progress


class IndiaMarketSignal(BaseModel):
    market_bias: Literal["risk_on", "risk_off", "domestic_support", "neutral"]
    confidence: float
    reasoning: str
    key_factors: list[str]


def india_market_agent(state: AgentState, agent_id: str = "india_market_agent"):
    """Analyzes Indian market conditions and provides market bias signals."""
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]

    analysis_data = {}
    market_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Analyzing India market context")

        # Analyze India-specific factors
        fii_dii_analysis = analyze_fii_dii_flows(ticker, end_date)
        promoter_analysis = analyze_promoter_holding(ticker, end_date)
        sebi_risk_analysis = analyze_sebi_risk_filters(ticker, end_date)
        
        # Generate overall market bias
        market_bias = generate_market_bias(
            fii_dii_analysis, 
            promoter_analysis, 
            sebi_risk_analysis
        )

        analysis_data[ticker] = {
            "fii_dii_flows": fii_dii_analysis,
            "promoter_holding": promoter_analysis,
            "sebi_risk": sebi_risk_analysis,
            "market_bias": market_bias
        }

        progress.update_status(agent_id, ticker, "Generating India market signal")

    # Create message for LLM reasoning
    template = ChatPromptTemplate.from_messages([
        ("system", """You are an Indian market analyst. Analyze the provided data and give a market bias signal.

Consider:
- FII/DII flow trends (Foreign vs Domestic Institutional Investors)
- Promoter holding changes and pledges
- SEBI-style risk filters (concentration, liquidity, governance)

Return JSON with:
- market_bias: "risk_on" / "risk_off" / "domestic_support" / "neutral"
- confidence: 0-100
- reasoning: brief explanation
- key_factors: list of 2-4 main factors"""),
        ("human", "Based on the India market data: {data}")
    ])

    prompt = template.invoke({
        "data": json.dumps(analysis_data, indent=2)
    })

    result = call_llm(
        state=state,
        prompt=prompt,
        agent_id=agent_id,
        pydantic_model=IndiaMarketSignal
    )

    india_market_signal = result if isinstance(result, IndiaMarketSignal) else IndiaMarketSignal(
        market_bias="neutral",
        confidence=50,
        reasoning="Unable to analyze India market conditions",
        key_factors=["Insufficient data"]
    )

    # Create response
    message = HumanMessage(
        content=json.dumps({
            "market_bias": india_market_signal.market_bias,
            "confidence": india_market_signal.confidence,
            "reasoning": india_market_signal.reasoning,
            "key_factors": india_market_signal.key_factors,
            "analysis_data": analysis_data
        }),
        name=agent_id
    )

    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(message.content, agent_id)

    state["data"]["analyst_signals"][agent_id] = india_market_signal.model_dump()

    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}


def analyze_fii_dii_flows(ticker: str, end_date: str) -> dict:
    """Analyze FII/DII flow patterns for Indian stocks."""
    # Placeholder - in production would fetch from NSE/BSE APIs
    return {
        "fii_trend": "net_buying",  # or "net_selling", "neutral"
        "dii_trend": "net_buying",
        "recent_flow_strength": "moderate",
        "notes": "DII support visible, FII stance improving"
    }


def analyze_promoter_holding(ticker: str, end_date: str) -> dict:
    """Check promoter holding changes and pledge status."""
    # Placeholder - in production would fetch from company filings
    return {
        "promoter_holding_pct": 65.0,  # Example
        "holding_change": "stable",
        "pledge_status": "low",  # or "moderate", "high", "concerning"
        "notes": "Promoter holding stable with minimal pledges"
    }


def analyze_sebi_risk_filters(ticker: str, end_date: str) -> dict:
    """Apply SEBI-style risk filters."""
    # Placeholder - in production would apply actual SEBI filters
    return {
        "concentration_risk": "low",
        "liquidity_risk": "moderate",
        "governance_risk": "low",
        "overall_risk_level": "acceptable",
        "notes": "Passes basic SEBI risk filters"
    }


def generate_market_bias(
    fii_dii: dict, 
    promoter: dict, 
    sebi_risk: dict
) -> str:
    """Generate overall market bias signal."""
    # Simple heuristic for market bias
    score = 0
    
    if fii_dii["fii_trend"] == "net_buying":
        score += 2
    elif fii_dii["fii_trend"] == "net_selling":
        score -= 2
        
    if fii_dii["dii_trend"] == "net_buying":
        score += 1
        
    if promoter["pledge_status"] in ["low", "moderate"]:
        score += 1
    elif promoter["pledge_status"] == "concerning":
        score -= 2
        
    if sebi_risk["overall_risk_level"] == "acceptable":
        score += 1
        
    if score >= 3:
        return "risk_on"
    elif score <= -2:
        return "risk_off"
    elif fii_dii["dii_trend"] == "net_buying" and fii_dii["fii_trend"] == "net_selling":
        return "domestic_support"
    else:
        return "neutral"
