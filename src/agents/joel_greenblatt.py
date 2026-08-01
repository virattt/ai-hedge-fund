from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import get_financial_metrics, get_market_cap, search_line_items
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
import json
from typing_extensions import Literal
from src.utils.progress import progress
from src.utils.llm import call_llm
from src.utils.api_key import get_api_key_from_state


class JoelGreenblattSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def joel_greenblatt_agent(state: AgentState, agent_id: str = "joel_greenblatt_agent"):
    """
    Analyzes stocks using Joel Greenblatt's Magic Formula:
    1. High Earnings Yield (EBIT / Enterprise Value)
    2. High Return on Capital (EBIT / (Net Working Capital + Net Fixed Assets))
    """
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")

    analysis_data = {}
    greenblatt_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=1, api_key=api_key)

        progress.update_status(agent_id, ticker, "Gathering financial line items")
        financial_line_items = search_line_items(
            ticker,
            [
                "operating_income",
                "total_assets",
                "total_current_assets",
                "total_current_liabilities",
                "property_plant_equipment_net",  # Proxy for Net Fixed Assets
                "enterprise_value",
            ],
            end_date,
            period="ttm",
            limit=1,
            api_key=api_key,
        )

        progress.update_status(agent_id, ticker, "Analyzing Magic Formula metrics")
        
        # Default values
        earnings_yield = 0.0
        return_on_capital = 0.0
        ey_score = 0
        roc_score = 0
        details = []

        if metrics and financial_line_items:
            latest_metrics = metrics[0]
            latest_items = financial_line_items[0]

            # 1. Earnings Yield = EBIT / Enterprise Value
            # We try to get EV from metrics first, then line items
            enterprise_value = latest_metrics.enterprise_value
            operating_income = getattr(latest_items, "operating_income", 0)

            if enterprise_value and enterprise_value > 0 and operating_income:
                earnings_yield = operating_income / enterprise_value
                details.append(f"Earnings Yield: {earnings_yield:.1%}")
                
                if earnings_yield > 0.10: # > 10% is generally good
                    ey_score = 2
                    details.append("Excellent Earnings Yield (>10%)")
                elif earnings_yield > 0.05:
                    ey_score = 1
                    details.append("Moderate Earnings Yield (>5%)")
                else:
                    details.append("Low Earnings Yield")
            else:
                details.append("Insufficient data for Earnings Yield")

            # 2. Return on Capital = EBIT / (Net Working Capital + Net Fixed Assets)
            # Net Working Capital = Current Assets - Current Liabilities
            current_assets = getattr(latest_items, "total_current_assets", 0)
            current_liabilities = getattr(latest_items, "total_current_liabilities", 0)
            net_fixed_assets = getattr(latest_items, "property_plant_equipment_net", 0)

            invested_capital = (current_assets - current_liabilities) + net_fixed_assets

            if invested_capital > 0 and operating_income:
                return_on_capital = operating_income / invested_capital
                details.append(f"Return on Capital: {return_on_capital:.1%}")

                if return_on_capital > 0.50:
                    roc_score = 3
                    details.append("Exceptional Return on Capital (>50%)")
                elif return_on_capital > 0.25:
                    roc_score = 2
                    details.append("Strong Return on Capital (>25%)")
                elif return_on_capital > 0.15:
                    roc_score = 1
                    details.append("Decent Return on Capital (>15%)")
                else:
                    details.append("Low Return on Capital")
            else:
                # Fallback to ROIC from metrics if available
                if latest_metrics.return_on_invested_capital:
                    return_on_capital = latest_metrics.return_on_invested_capital
                    details.append(f"Using reported ROIC: {return_on_capital:.1%}")
                    if return_on_capital > 0.15:
                        roc_score = 1
                else:
                    details.append("Insufficient data for Return on Capital")
        
        total_score = ey_score + roc_score
        max_score = 5 # 2 for python EY, 3 for ROC

        analysis_data[ticker] = {
            "earnings_yield": earnings_yield,
            "return_on_capital": return_on_capital,
            "score": total_score,
            "max_score": max_score,
            "details": "; ".join(details)
        }

        progress.update_status(agent_id, ticker, "Generating Greenblatt analysis")
        greenblatt_output = generate_greenblatt_output(
            ticker=ticker,
            analysis_data=analysis_data[ticker],
            state=state,
            agent_id=agent_id,
        )

        greenblatt_analysis[ticker] = {
            "signal": greenblatt_output.signal,
            "confidence": greenblatt_output.confidence,
            "reasoning": greenblatt_output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=greenblatt_output.reasoning)

    message = HumanMessage(content=json.dumps(greenblatt_analysis), name=agent_id)

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(greenblatt_analysis, "Joel Greenblatt Agent")

    state["data"]["analyst_signals"][agent_id] = greenblatt_analysis
    
    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}


def generate_greenblatt_output(
    ticker: str,
    analysis_data: dict[str, any],
    state: AgentState,
    agent_id: str,
) -> JoelGreenblattSignal:
    """Generates decision based on Magic Formula principles."""
    
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a Joel Greenblatt AI agent, using the "Magic Formula" investing strategy.
                
                Your core principles:
                1. Buy good businesses (High Return on Capital).
                2. Buy them at bargain prices (High Earnings Yield).
                
                Scoring Guide:
                - Return on Capital (ROC) > 25% is excellent. > 50% is phenomenal.
                - Earnings Yield (EY) > 10% is very attractive.
                
                Decision Rules:
                - BULLISH: High ROC (>25%) AND High EY (>8%).
                - BEARISH: Low ROC (<10%) OR Negative EY.
                - NEUTRAL: Mixed or average metrics.
                
                Provide a concise reasoning emphasizing these two numbers.
                """
            ),
            (
                "human",
                """Ticker: {ticker}
                
                Analysis Data:
                {analysis_data}
                
                Return JSON:
                {{
                    "signal": "bullish" | "bearish" | "neutral",
                    "confidence": float,
                    "reasoning": "string"
                }}
                """
            ),
        ]
    )

    prompt = template.invoke({"analysis_data": json.dumps(analysis_data, indent=2), "ticker": ticker})

    def create_default_greenblatt_signal():
        return JoelGreenblattSignal(signal="neutral", confidence=0.0, reasoning="Error in analysis")

    return call_llm(
        prompt=prompt,
        pydantic_model=JoelGreenblattSignal,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_greenblatt_signal,
    )
