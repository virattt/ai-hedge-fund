from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import get_financial_metrics, get_market_cap, search_line_items
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import json
from typing_extensions import Literal
from src.utils.progress import progress
from src.utils.llm import call_llm
from src.utils.api_key import get_api_key_from_state


class MohnishPabraiSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def mohnish_pabrai_agent(state: AgentState, agent_id: str = "mohnish_pabrai_agent"):
    """
    Analyzes stocks using Mohnish Pabrai's principles:
    - Focus on undervalued, high-quality businesses.
    - Evaluate downside protection and cash yield.
    - Use growth, valuation, fundamentals, and insider activity signals.
    """
    data = state["data"]
    tickers = data["tickers"]
    end_date = data["end_date"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")

    analysis_data = {}
    pabrai_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="annual", limit=8, api_key=api_key)

        progress.update_status(agent_id, ticker, "Gathering financial line items")
        # Safe line items extraction
        keywords = [
            "revenue", "gross_profit", "gross_margin", "operating_income", "operating_margin",
            "net_income", "free_cash_flow", "total_debt", "cash_and_equivalents",
            "current_assets", "current_liabilities", "shareholders_equity",
            "capital_expenditure", "depreciation_and_amortization", "outstanding_shares",
        ]
        financial_line_items = {}
        for kw in keywords:
            items = search_line_items(metrics, kw)
            if isinstance(items, dict):
                financial_line_items.update(items)
        
        # Analyze valuation safely
        pabrai_analysis[ticker] = analyze_pabrai_valuation(financial_line_items, metrics)

        # Analyze downside protection safely
        downside = analyze_downside_protection(financial_line_items)

        # Example growth analysis (stub, replace with your growth logic)
        growth_analysis = {"score": 5.0}  # placeholder for real growth scoring

        # Example insider activity (stub)
        insider_activity = {"score": 5.0}  # placeholder for real insider scoring

        # Combine partial scores with Pabrai-style weights
        total_score = (
            pabrai_analysis[ticker].get("score", 0) * 0.40
            + growth_analysis.get("score", 0) * 0.30
            + downside.get("score", 0) * 0.20
            + insider_activity.get("score", 0) * 0.10
        )
        max_possible_score = 10.0

        # Map total_score to signal
        if total_score >= 7.5:
            signal = "bullish"
        elif total_score <= 4.5:
            signal = "bearish"
        else:
            signal = "neutral"

        analysis_data[ticker] = {
            "signal": signal,
            "score": total_score,
            "max_score": max_possible_score,
            "valuation_analysis": pabrai_analysis[ticker],
            "downside_analysis": downside,
            "growth_analysis": growth_analysis,
            "insider_activity": insider_activity,
        }

    return {
    "data": analysis_data
}



def analyze_downside_protection(financial_line_items: list) -> dict[str, any]:
    """Assess balance-sheet strength and downside resiliency (capital preservation first)."""
    if not financial_line_items:
        return {"score": 0, "details": "Insufficient data"}

    latest = financial_line_items[0]
    details: list[str] = []
    score = 0

    cash = getattr(latest, "cash_and_equivalents", None)
    debt = getattr(latest, "total_debt", None)
    current_assets = getattr(latest, "current_assets", None)
    current_liabilities = getattr(latest, "current_liabilities", None)
    equity = getattr(latest, "shareholders_equity", None)

    # Net cash position is a strong downside protector
    net_cash = None
    if cash is not None and debt is not None:
        net_cash = cash - debt
        if net_cash > 0:
            score += 3
            details.append(f"Net cash position: ${net_cash:,.0f}")
        else:
            details.append(f"Net debt position: ${net_cash:,.0f}")

    # Current ratio
    if current_assets is not None and current_liabilities is not None and current_liabilities > 0:
        current_ratio = current_assets / current_liabilities
        if current_ratio >= 2.0:
            score += 2
            details.append(f"Strong liquidity (current ratio {current_ratio:.2f})")
        elif current_ratio >= 1.2:
            score += 1
            details.append(f"Adequate liquidity (current ratio {current_ratio:.2f})")
        else:
            details.append(f"Weak liquidity (current ratio {current_ratio:.2f})")

    # Low leverage
    if equity is not None and equity > 0 and debt is not None:
        de_ratio = debt / equity
        if de_ratio < 0.3:
            score += 2
            details.append(f"Very low leverage (D/E {de_ratio:.2f})")
        elif de_ratio < 0.7:
            score += 1
            details.append(f"Moderate leverage (D/E {de_ratio:.2f})")
        else:
            details.append(f"High leverage (D/E {de_ratio:.2f})")

    # Free cash flow positive and stable
    fcf_values = [getattr(li, "free_cash_flow", None) for li in financial_line_items if getattr(li, "free_cash_flow", None) is not None]
    if fcf_values and len(fcf_values) >= 3:
        recent_avg = sum(fcf_values[:3]) / 3
        older = sum(fcf_values[-3:]) / 3 if len(fcf_values) >= 6 else fcf_values[-1]
        if recent_avg > 0 and recent_avg >= older:
            score += 2
            details.append("Positive and improving/stable FCF")
        elif recent_avg > 0:
            score += 1
            details.append("Positive but declining FCF")
        else:
            details.append("Negative FCF")

    return {"score": min(10, score), "details": "; ".join(details)}


def analyze_pabrai_valuation(financials: dict, financial_line_items: dict) -> dict:
    """
    Analyze a company's valuation and fundamentals for Mohnish Pabrai's investing style.
    
    Args:
        financials (dict): Raw financial metrics data.
        financial_line_items (dict): Extracted line items relevant to valuation.
        
    Returns:
        dict: Contains a 'score' (0–10) and textual 'reasoning'.
    """
    def get_numeric(value):
        """Safely extract a numeric value from raw input or nested dict."""
        if isinstance(value, dict):
            # Try common numeric keys
            for k in ("value", "amount", "numeric"):
                if k in value and isinstance(value[k], (int, float)):
                    return value[k]
            return None
        elif isinstance(value, (int, float)):
            return value
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    # Extract key metrics safely
    market_cap = get_numeric(financial_line_items.get("market_cap"))
    pe_ratio = get_numeric(financial_line_items.get("pe_ratio"))
    debt = get_numeric(financial_line_items.get("total_debt"))
    cash = get_numeric(financial_line_items.get("cash_and_equivalents"))
    free_cash_flow = get_numeric(financial_line_items.get("free_cash_flow"))

    if not financial_line_items or market_cap is None or market_cap <= 0:
        return {"score": 0, "reasoning": "Insufficient financial data for valuation."}

    score = 0
    reasoning_parts = []

    # Simple scoring examples
    if pe_ratio is not None and pe_ratio < 15:
        score += 3
        reasoning_parts.append(f"Reasonable P/E ratio ({pe_ratio})")
    elif pe_ratio is not None:
        score += 1
        reasoning_parts.append(f"High P/E ratio ({pe_ratio})")

    if debt is not None and debt / market_cap < 0.5:
        score += 3
        reasoning_parts.append(f"Low debt relative to market cap ({debt}/{market_cap})")
    elif debt is not None:
        score += 1
        reasoning_parts.append(f"High debt relative to market cap ({debt}/{market_cap})")

    if free_cash_flow is not None and free_cash_flow > 0:
        score += 2
        reasoning_parts.append(f"Positive free cash flow ({free_cash_flow})")
    else:
        reasoning_parts.append("No positive free cash flow data")

    if cash is not None and cash / market_cap > 0.1:
        score += 2
        reasoning_parts.append(f"Healthy cash reserves relative to market cap ({cash}/{market_cap})")

    # Normalize score to 10
    if score > 10:
        score = 10

    return {
        "score": score,
        "reasoning": "; ".join(reasoning_parts),
        "market_cap": market_cap,
        "pe_ratio": pe_ratio,
        "debt": debt,
        "cash": cash,
        "free_cash_flow": free_cash_flow,
    }



def analyze_double_potential(financial_line_items: list, market_cap: float | None) -> dict[str, any]:
    """Estimate low-risk path to double capital in ~2-3 years: runway from FCF growth + rerating."""
    if not financial_line_items or market_cap is None or market_cap <= 0:
        return {"score": 0, "details": "Insufficient data"}

    details: list[str] = []

    # Use revenue and FCF trends as rough growth proxy (keep it simple)
    revenues = [getattr(li, "revenue", None) for li in financial_line_items if getattr(li, "revenue", None) is not None]
    fcfs = [getattr(li, "free_cash_flow", None) for li in financial_line_items if getattr(li, "free_cash_flow", None) is not None]

    score = 0
    if revenues and len(revenues) >= 3:
        recent_rev = sum(revenues[:3]) / 3
        older_rev = sum(revenues[-3:]) / 3 if len(revenues) >= 6 else revenues[-1]
        if older_rev > 0:
            rev_growth = (recent_rev / older_rev) - 1
            if rev_growth > 0.15:
                score += 2
                details.append(f"Strong revenue trajectory ({rev_growth:.1%})")
            elif rev_growth > 0.05:
                score += 1
                details.append(f"Modest revenue growth ({rev_growth:.1%})")

    if fcfs and len(fcfs) >= 3:
        recent_fcf = sum(fcfs[:3]) / 3
        older_fcf = sum(fcfs[-3:]) / 3 if len(fcfs) >= 6 else fcfs[-1]
        if older_fcf != 0:
            fcf_growth = (recent_fcf / older_fcf) - 1
            if fcf_growth > 0.20:
                score += 3
                details.append(f"Strong FCF growth ({fcf_growth:.1%})")
            elif fcf_growth > 0.08:
                score += 2
                details.append(f"Healthy FCF growth ({fcf_growth:.1%})")
            elif fcf_growth > 0:
                score += 1
                details.append(f"Positive FCF growth ({fcf_growth:.1%})")

    # If FCF yield is already high (>8%), doubling can come from cash generation alone in few years
    tmp_val = analyze_pabrai_valuation(financial_line_items, market_cap)
    fcf_yield = tmp_val.get("fcf_yield")
    if fcf_yield is not None:
        if fcf_yield > 0.08:
            score += 3
            details.append("High FCF yield can drive doubling via retained cash/Buybacks")
        elif fcf_yield > 0.05:
            score += 1
            details.append("Reasonable FCF yield supports moderate compounding")

    return {"score": min(10, score), "details": "; ".join(details)}


def generate_pabrai_output(
    ticker: str,
    analysis_data: dict[str, any],
    state: AgentState,
    agent_id: str,
) -> MohnishPabraiSignal:
    """Generate Pabrai-style decision focusing on low risk, high uncertainty bets and cloning."""
    template = ChatPromptTemplate.from_messages([
        (
          "system",
          """You are Mohnish Pabrai. Apply my value investing philosophy:

          - Heads I win; tails I don't lose much: prioritize downside protection first.
          - Buy businesses with simple, understandable models and durable moats.
          - Demand high free cash flow yields and low leverage; prefer asset-light models.
          - Look for situations where intrinsic value is rising and price is significantly lower.
          - Favor cloning great investors' ideas and checklists over novelty.
          - Seek potential to double capital in 2-3 years with low risk.
          - Avoid leverage, complexity, and fragile balance sheets.

            Provide candid, checklist-driven reasoning, with emphasis on capital preservation and expected mispricing.
            """,
        ),
        (
          "human",
          """Analyze {ticker} using the provided data.

          DATA:
          {analysis_data}

          Return EXACTLY this JSON:
          {{
            "signal": "bullish" | "bearish" | "neutral",
            "confidence": float (0-100),
            "reasoning": "string with Pabrai-style analysis focusing on downside protection, FCF yield, and doubling potential"
          }}
          """,
        ),
    ])

    prompt = template.invoke({
        "analysis_data": json.dumps(analysis_data, indent=2),
        "ticker": ticker,
    })

    def create_default_pabrai_signal():
        return MohnishPabraiSignal(signal="neutral", confidence=0.0, reasoning="Error in analysis, defaulting to neutral")

    return call_llm(
        prompt=prompt,
        state=state,
        pydantic_model=MohnishPabraiSignal,
        agent_name=agent_id,
        default_factory=create_default_pabrai_signal,
    ) 