from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import json
from typing_extensions import Literal
from src.tools.api import get_financial_metrics, get_market_cap, search_line_items
from src.utils.llm import call_llm
from src.utils.progress import progress

class RakeshJhunjhunwalaSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str

def rakesh_jhunjhunwala_agent(state: AgentState):
    """Analyzes stocks using Rakesh Jhunjhunwala's principles and LLM reasoning."""
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]

    # Collect all analysis for LLM reasoning
    analysis_data = {}
    jhunjhunwala_analysis = {}

    for ticker in tickers:

        # Core Data
        progress.update_status("rakesh_jhunjhunwala_agent", ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=5)

        progress.update_status("rakesh_jhunjhunwala_agent", ticker, "Fetching financial line items")
        financial_line_items = search_line_items(
            ticker,
            [
                "net_income",
                "earnings_per_share",
                "ebit",
                "operating_income",
                "revenue",
                "operating_margin",
                "total_assets",
                "total_liabilities",
                "current_assets",
                "current_liabilities",
                "free_cash_flow",
                "dividends_and_other_cash_distributions",
                "issuance_or_purchase_of_equity_shares"
            ],
            end_date,
        )

        progress.update_status("rakesh_jhunjhunwala_agent", ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date)

        # ─── Analyses ───────────────────────────────────────────────────────────
        progress.update_status("rakesh_jhunjhunwala_agent", ticker, "Analyzing growth")
        growth_analysis = analyze_growth(financial_line_items)

        progress.update_status("rakesh_jhunjhunwala_agent", ticker, "Analyzing profitability")
        profitability_analysis = analyze_profitability(financial_line_items)
        
        progress.update_status("rakesh_jhunjhunwala_agent", ticker, "Analyzing balance sheet")
        balancesheet_analysis = analyze_balance_sheet(financial_line_items)
        
        progress.update_status("rakesh_jhunjhunwala_agent", ticker, "Analyzing cash flow")
        cashflow_analysis = analyze_cash_flow(financial_line_items)
        
        progress.update_status("rakesh_jhunjhunwala_agent", ticker, "Analyzing management actions")
        management_analysis = analyze_management_actions(financial_line_items)
        
        progress.update_status("rakesh_jhunjhunwala_agent", ticker, "Calculating intrinsic value")
        # Calculate intrinsic value once
        intrinsic_value = calculate_intrinsic_value(financial_line_items, market_cap)

        # ─── Score & margin of safety ──────────────────────────────────────────
        total_score = (
            growth_analysis["score"]
            + profitability_analysis["score"]
            + balancesheet_analysis["score"]
            + cashflow_analysis["score"]
            + management_analysis["score"]
        )
        # Fixed: Correct max_score calculation based on actual scoring breakdown
        max_score = 24  # 8(prof) + 7(growth) + 4(bs) + 3(cf) + 2(mgmt) = 24

        # Calculate margin of safety
        margin_of_safety = (
            (intrinsic_value - market_cap) / market_cap if intrinsic_value and market_cap else None
        )

        # Jhunjhunwala's decision rules (30% minimum margin of safety for conviction)
        if margin_of_safety is not None and margin_of_safety >= 0.30:
            signal = "bullish"
        elif margin_of_safety is not None and margin_of_safety <= -0.30:
            signal = "bearish"
        else:
            # Use quality score as tie-breaker for neutral cases
            quality_score = assess_quality_metrics(financial_line_items)
            if quality_score >= 0.7 and total_score >= max_score * 0.6:
                signal = "bullish"  # High quality company at fair price
            elif quality_score <= 0.4 or total_score <= max_score * 0.3:
                signal = "bearish"  # Poor quality or fundamentals
            else:
                signal = "neutral"

        # Confidence based on margin of safety and quality
        if margin_of_safety is not None:
            confidence = min(max(abs(margin_of_safety) * 150, 20), 95)  # 20-95% range
        else:
            confidence = min(max((total_score / max_score) * 100, 10), 80)  # Based on score

        # Create comprehensive analysis summary
        intrinsic_value_analysis = analyze_rakesh_jhunjhunwala_style(
            financial_line_items, 
            intrinsic_value=intrinsic_value,
            current_price=market_cap
        )

        analysis_data[ticker] = {
            "signal": signal,
            "score": total_score,
            "max_score": max_score,
            "margin_of_safety": margin_of_safety,
            "growth_analysis": growth_analysis,
            "profitability_analysis": profitability_analysis,
            "balancesheet_analysis": balancesheet_analysis,
            "cashflow_analysis": cashflow_analysis,
            "management_analysis": management_analysis,
            "intrinsic_value_analysis": intrinsic_value_analysis,
            "intrinsic_value": intrinsic_value,
            "market_cap": market_cap,
        }

        # ─── LLM: craft Jhunjhunwala‑style narrative ──────────────────────────────
        progress.update_status("rakesh_jhunjhunwala_agent", ticker, "Generating Jhunjhunwala analysis")
        jhunjhunwala_output = generate_jhunjhunwala_output(
            ticker=ticker,
            analysis_data=analysis_data[ticker],
            model_name=state["metadata"]["model_name"],
            model_provider=state["metadata"]["model_provider"],
        )

        jhunjhunwala_analysis[ticker] = jhunjhunwala_output.model_dump()

        progress.update_status("rakesh_jhunjhunwala_agent", ticker, "Done", analysis=jhunjhunwala_output.reasoning)

    # ─── Push message back to graph state ──────────────────────────────────────
    message = HumanMessage(content=json.dumps(jhunjhunwala_analysis), name="rakesh_jhunjhunwala_agent")

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(jhunjhunwala_analysis, "Rakesh Jhunjhunwala Agent")

    state["data"]["analyst_signals"]["rakesh_jhunjhunwala_agent"] = jhunjhunwala_analysis
    progress.update_status("rakesh_jhunjhunwala_agent", None, "Done")

    return {"messages": [message], "data": state["data"]}


def analyze_profitability(financial_line_items: list) -> dict[str, any]:
    """
    Analyze profitability metrics like net income, EBIT, EPS, operating income.
    Focus on strong, consistent earnings growth and operating efficiency.
    """
    if not financial_line_items:
        return {"score": 0, "details": "No profitability data available"}

    latest = financial_line_items[0]
    score = 0
    reasoning = []

    # Calculate ROE (Return on Equity) - Jhunjhunwala's key metric
    if (getattr(latest, 'net_income', None) and latest.net_income > 0 and
        getattr(latest, 'total_assets', None) and getattr(latest, 'total_liabilities', None) and 
        latest.total_assets and latest.total_liabilities):
        
        shareholders_equity = latest.total_assets - latest.total_liabilities
        if shareholders_equity > 0:
            roe = (latest.net_income / shareholders_equity) * 100
            if roe > 20:  # Excellent ROE
                score += 3
                reasoning.append(f"Excellent ROE: {roe:.1f}%")
            elif roe > 15:  # Good ROE
                score += 2
                reasoning.append(f"Good ROE: {roe:.1f}%")
            elif roe > 10:  # Decent ROE
                score += 1
                reasoning.append(f"Decent ROE: {roe:.1f}%")
            else:
                reasoning.append(f"Low ROE: {roe:.1f}%")
        else:
            reasoning.append("Negative shareholders equity")
    else:
        reasoning.append("Unable to calculate ROE - missing data")

    # Operating Margin Analysis
    if (getattr(latest, "operating_income", None) and latest.operating_income and 
        getattr(latest, "revenue", None) and latest.revenue and latest.revenue > 0):
        operating_margin = (latest.operating_income / latest.revenue) * 100
        if operating_margin > 20:  # Excellent margin
            score += 2
            reasoning.append(f"Excellent operating margin: {operating_margin:.1f}%")
        elif operating_margin > 15:  # Good margin
            score += 1
            reasoning.append(f"Good operating margin: {operating_margin:.1f}%")
        elif operating_margin > 0:
            reasoning.append(f"Positive operating margin: {operating_margin:.1f}%")
        else:
            reasoning.append(f"Negative operating margin: {operating_margin:.1f}%")
    else:
        reasoning.append("Unable to calculate operating margin")

    # EPS Growth Consistency (3-year trend)
    eps_values = [getattr(item, "earnings_per_share", None) for item in financial_line_items 
                  if getattr(item, "earnings_per_share", None) is not None and getattr(item, "earnings_per_share", None) > 0]
    
    if len(eps_values) >= 3:
        # Calculate CAGR for EPS
        initial_eps = eps_values[-1]  # Oldest value
        final_eps = eps_values[0]     # Latest value
        years = len(eps_values) - 1
        
        if initial_eps > 0:
            eps_cagr = ((final_eps / initial_eps) ** (1/years) - 1) * 100
            if eps_cagr > 20:  # High growth
                score += 3
                reasoning.append(f"High EPS CAGR: {eps_cagr:.1f}%")
            elif eps_cagr > 15:  # Good growth
                score += 2
                reasoning.append(f"Good EPS CAGR: {eps_cagr:.1f}%")
            elif eps_cagr > 10:  # Moderate growth
                score += 1
                reasoning.append(f"Moderate EPS CAGR: {eps_cagr:.1f}%")
            else:
                reasoning.append(f"Low EPS CAGR: {eps_cagr:.1f}%")
        else:
            reasoning.append("Cannot calculate EPS growth from negative base")
    else:
        reasoning.append("Insufficient EPS data for growth analysis")

    return {"score": score, "details": "; ".join(reasoning)}


def analyze_growth(financial_line_items: list) -> dict[str, any]:
    """
    Analyze revenue and net income growth trends using CAGR.
    Jhunjhunwala favored companies with strong, consistent compound growth.
    """
    if len(financial_line_items) < 3:
        return {"score": 0, "details": "Insufficient data for growth analysis"}

    score = 0
    reasoning = []

    # Revenue CAGR Analysis
    revenues = [getattr(item, "revenue", None) for item in financial_line_items 
                if getattr(item, "revenue", None) is not None and getattr(item, "revenue", None) > 0]
    
    if len(revenues) >= 3:
        initial_revenue = revenues[-1]  # Oldest
        final_revenue = revenues[0]     # Latest
        years = len(revenues) - 1
        
        if initial_revenue > 0:  # Fixed: Add zero check
            revenue_cagr = ((final_revenue / initial_revenue) ** (1/years) - 1) * 100
            
            if revenue_cagr > 20:  # High growth
                score += 3
                reasoning.append(f"Excellent revenue CAGR: {revenue_cagr:.1f}%")
            elif revenue_cagr > 15:  # Good growth
                score += 2
                reasoning.append(f"Good revenue CAGR: {revenue_cagr:.1f}%")
            elif revenue_cagr > 10:  # Moderate growth
                score += 1
                reasoning.append(f"Moderate revenue CAGR: {revenue_cagr:.1f}%")
            else:
                reasoning.append(f"Low revenue CAGR: {revenue_cagr:.1f}%")
        else:
            reasoning.append("Cannot calculate revenue CAGR from zero base")
    else:
        reasoning.append("Insufficient revenue data for CAGR calculation")

    # Net Income CAGR Analysis
    net_incomes = [getattr(item, "net_income", None) for item in financial_line_items 
                   if getattr(item, "net_income", None) is not None and getattr(item, "net_income", None) > 0]
    
    if len(net_incomes) >= 3:
        initial_income = net_incomes[-1]  # Oldest
        final_income = net_incomes[0]     # Latest
        years = len(net_incomes) - 1
        
        if initial_income > 0:  # Fixed: Add zero check
            income_cagr = ((final_income / initial_income) ** (1/years) - 1) * 100
            
            if income_cagr > 25:  # Very high growth
                score += 3
                reasoning.append(f"Excellent income CAGR: {income_cagr:.1f}%")
            elif income_cagr > 20:  # High growth
                score += 2
                reasoning.append(f"High income CAGR: {income_cagr:.1f}%")
            elif income_cagr > 15:  # Good growth
                score += 1
                reasoning.append(f"Good income CAGR: {income_cagr:.1f}%")
            else:
                reasoning.append(f"Moderate income CAGR: {income_cagr:.1f}%")
        else:
            reasoning.append("Cannot calculate income CAGR from zero base")
    else:
        reasoning.append("Insufficient net income data for CAGR calculation")

    # Revenue Consistency Check (year-over-year)
    if len(revenues) >= 3:
        declining_years = sum(1 for i in range(1, len(revenues)) if revenues[i-1] > revenues[i])
        consistency_ratio = 1 - (declining_years / (len(revenues) - 1))
        
        if consistency_ratio >= 0.8:  # 80% or more years with growth
            score += 1
            reasoning.append(f"Consistent growth pattern ({consistency_ratio*100:.0f}% of years)")
        else:
            reasoning.append(f"Inconsistent growth pattern ({consistency_ratio*100:.0f}% of years)")

    return {"score": score, "details": "; ".join(reasoning)}


def analyze_balance_sheet(financial_line_items: list) -> dict[str, any]:
    """
    Check financial strength - healthy asset/liability structure, liquidity.
    Jhunjhunwala favored companies with clean balance sheets and manageable debt.
    """
    if not financial_line_items:
        return {"score": 0, "details": "No balance sheet data"}

    latest = financial_line_items[0]
    score = 0
    reasoning = []

    # Debt to asset ratio
    if (getattr(latest, "total_assets", None) and getattr(latest, "total_liabilities", None) 
        and latest.total_assets and latest.total_liabilities 
        and latest.total_assets > 0):
        debt_ratio = latest.total_liabilities / latest.total_assets
        if debt_ratio < 0.5:
            score += 2
            reasoning.append(f"Low debt ratio: {debt_ratio:.2f}")
        elif debt_ratio < 0.7:
            score += 1
            reasoning.append(f"Moderate debt ratio: {debt_ratio:.2f}")
        else:
            reasoning.append(f"High debt ratio: {debt_ratio:.2f}")
    else:
        reasoning.append("Insufficient data to calculate debt ratio")

    # Current ratio (liquidity)
    if (getattr(latest, "current_assets", None) and getattr(latest, "current_liabilities", None) 
        and latest.current_assets and latest.current_liabilities 
        and latest.current_liabilities > 0):
        current_ratio = latest.current_assets / latest.current_liabilities
        if current_ratio > 2.0:
            score += 2
            reasoning.append(f"Excellent liquidity with current ratio: {current_ratio:.2f}")
        elif current_ratio > 1.5:
            score += 1
            reasoning.append(f"Good liquidity with current ratio: {current_ratio:.2f}")
        else:
            reasoning.append(f"Weak liquidity with current ratio: {current_ratio:.2f}")
    else:
        reasoning.append("Insufficient data to calculate current ratio")

    return {"score": score, "details": "; ".join(reasoning)}


def analyze_cash_flow(financial_line_items: list) -> dict[str, any]:
    """
    Evaluate free cash flow and dividend behavior.
    Jhunjhunwala appreciated companies generating strong free cash flow and rewarding shareholders.
    """
    if not financial_line_items:
        return {"score": 0, "details": "No cash flow data"}

    latest = financial_line_items[0]
    score = 0
    reasoning = []

    # Free cash flow analysis
    if getattr(latest, "free_cash_flow", None) and latest.free_cash_flow:
        if latest.free_cash_flow > 0:
            score += 2
            reasoning.append(f"Positive free cash flow: {latest.free_cash_flow}")
        else:
            reasoning.append(f"Negative free cash flow: {latest.free_cash_flow}")
    else:
        reasoning.append("Free cash flow data not available")

    # Dividend analysis
    if getattr(latest, "dividends_and_other_cash_distributions", None) and latest.dividends_and_other_cash_distributions:
        if latest.dividends_and_other_cash_distributions < 0:  # Negative indicates cash outflow for dividends
            score += 1
            reasoning.append("Company pays dividends to shareholders")
        else:
            reasoning.append("No significant dividend payments")
    else:
        reasoning.append("No dividend payment data available")

    return {"score": score, "details": "; ".join(reasoning)}


def analyze_management_actions(financial_line_items: list) -> dict[str, any]:
    """
    Look at share issuance or buybacks to assess shareholder friendliness.
    Jhunjhunwala liked managements who buy back shares or avoid dilution.
    """
    if not financial_line_items:
        return {"score": 0, "details": "No management action data"}

    latest = financial_line_items[0]
    score = 0
    reasoning = []

    issuance = getattr(latest, "issuance_or_purchase_of_equity_shares", None)
    if issuance is not None:
        if issuance < 0:  # Negative indicates share buybacks
            score += 2
            reasoning.append(f"Company buying back shares: {abs(issuance)}")
        elif issuance > 0:
            reasoning.append(f"Share issuance detected (potential dilution): {issuance}")
        else:
            score += 1
            reasoning.append("No recent share issuance or buyback")
    else:
        reasoning.append("No data on share issuance or buybacks")

    return {"score": score, "details": "; ".join(reasoning)}


def assess_quality_metrics(financial_line_items: list) -> float:
    """
    Assess company quality based on Jhunjhunwala's criteria.
    Returns a score between 0 and 1.
    """
    if not financial_line_items:
        return 0.5  # Neutral score
    
    latest = financial_line_items[0]
    quality_factors = []
    
    # ROE consistency and level
    if (getattr(latest, 'net_income', None) and getattr(latest, 'total_assets', None) and 
        getattr(latest, 'total_liabilities', None) and latest.total_assets and latest.total_liabilities):
        
        shareholders_equity = latest.total_assets - latest.total_liabilities
        if shareholders_equity > 0 and latest.net_income:
            roe = latest.net_income / shareholders_equity
            if roe > 0.20:  # ROE > 20%
                quality_factors.append(1.0)
            elif roe > 0.15:  # ROE > 15%
                quality_factors.append(0.8)
            elif roe > 0.10:  # ROE > 10%
                quality_factors.append(0.6)
            else:
                quality_factors.append(0.3)
        else:
            quality_factors.append(0.0)
    else:
        quality_factors.append(0.5)
    
    # Debt levels (lower is better)
    if (getattr(latest, 'total_assets', None) and getattr(latest, 'total_liabilities', None) and 
        latest.total_assets and latest.total_liabilities):
        debt_ratio = latest.total_liabilities / latest.total_assets
        if debt_ratio < 0.3:  # Low debt
            quality_factors.append(1.0)
        elif debt_ratio < 0.5:  # Moderate debt
            quality_factors.append(0.7)
        elif debt_ratio < 0.7:  # High debt
            quality_factors.append(0.4)
        else:  # Very high debt
            quality_factors.append(0.1)
    else:
        quality_factors.append(0.5)
    
    # Growth consistency
    net_incomes = [getattr(item, "net_income", None) for item in financial_line_items[:4] 
                   if getattr(item, "net_income", None) is not None and getattr(item, "net_income", None) > 0]
    
    if len(net_incomes) >= 3:
        declining_years = sum(1 for i in range(1, len(net_incomes)) if net_incomes[i-1] > net_incomes[i])
        consistency = 1 - (declining_years / (len(net_incomes) - 1))
        quality_factors.append(consistency)
    else:
        quality_factors.append(0.5)
    
    # Return average quality score
    return sum(quality_factors) / len(quality_factors) if quality_factors else 0.5


def calculate_intrinsic_value(financial_line_items: list, market_cap: float) -> float:
    """
    Calculate intrinsic value using Rakesh Jhunjhunwala's approach:
    - Focus on earnings power and growth
    - Conservative discount rates
    - Quality premium for consistent performers
    """
    if not financial_line_items or not market_cap:
        return None
    
    try:
        latest = financial_line_items[0]
        
        # Need positive earnings as base
        if not getattr(latest, 'net_income', None) or latest.net_income <= 0:
            return None
        
        # Get historical earnings for growth calculation
        net_incomes = [getattr(item, "net_income", None) for item in financial_line_items[:5] 
                       if getattr(item, "net_income", None) is not None and getattr(item, "net_income", None) > 0]
        
        if len(net_incomes) < 2:
            # Use current earnings with conservative multiple for stable companies
            return latest.net_income * 12  # Conservative P/E of 12
        
        # Calculate sustainable growth rate using historical data
        initial_income = net_incomes[-1]  # Oldest
        final_income = net_incomes[0]     # Latest
        years = len(net_incomes) - 1
        
        # Calculate historical CAGR
        if initial_income > 0:  # Fixed: Add zero check
            historical_growth = ((final_income / initial_income) ** (1/years) - 1)
        else:
            historical_growth = 0.05  # Default to 5%
        
        # Conservative growth assumptions (Jhunjhunwala style)
        if historical_growth > 0.25:  # Cap at 25% for sustainability
            sustainable_growth = 0.20  # Conservative 20%
        elif historical_growth > 0.15:
            sustainable_growth = historical_growth * 0.8  # 80% of historical
        elif historical_growth > 0.05:
            sustainable_growth = historical_growth * 0.9  # 90% of historical
        else:
            sustainable_growth = 0.05  # Minimum 5% for inflation
        
        # Quality assessment affects discount rate
        quality_score = assess_quality_metrics(financial_line_items)
        
        # Discount rate based on quality (Jhunjhunwala preferred quality)
        if quality_score >= 0.8:  # High quality
            discount_rate = 0.12  # 12% for high quality companies
            terminal_multiple = 18
        elif quality_score >= 0.6:  # Medium quality
            discount_rate = 0.15  # 15% for medium quality
            terminal_multiple = 15
        else:  # Lower quality
            discount_rate = 0.18  # 18% for riskier companies
            terminal_multiple = 12
        
        # Simple DCF with terminal value
        current_earnings = latest.net_income
        terminal_value = 0
        dcf_value = 0
        
        # Project 5 years of earnings
        for year in range(1, 6):
            projected_earnings = current_earnings * ((1 + sustainable_growth) ** year)
            present_value = projected_earnings / ((1 + discount_rate) ** year)
            dcf_value += present_value
        
        # Terminal value (year 5 earnings * terminal multiple)
        year_5_earnings = current_earnings * ((1 + sustainable_growth) ** 5)
        terminal_value = (year_5_earnings * terminal_multiple) / ((1 + discount_rate) ** 5)
        
        total_intrinsic_value = dcf_value + terminal_value
        
        return total_intrinsic_value
        
    except Exception:
        # Fallback to simple earnings multiple
        if getattr(latest, 'net_income', None) and latest.net_income > 0:
            return latest.net_income * 15
        return None


def analyze_rakesh_jhunjhunwala_style(
    financial_line_items: list,
    owner_earnings: float = None,
    intrinsic_value: float = None,
    current_price: float = None,
) -> dict[str, any]:
    """
    Comprehensive analysis in Rakesh Jhunjhunwala's investment style.
    """
    # Run sub-analyses
    profitability = analyze_profitability(financial_line_items)
    growth = analyze_growth(financial_line_items)
    balance_sheet = analyze_balance_sheet(financial_line_items)
    cash_flow = analyze_cash_flow(financial_line_items)
    management = analyze_management_actions(financial_line_items)

    total_score = (
        profitability["score"]
        + growth["score"]
        + balance_sheet["score"]
        + cash_flow["score"]
        + management["score"]
    )

    details = (
        f"Profitability: {profitability['details']}\n"
        f"Growth: {growth['details']}\n"
        f"Balance Sheet: {balance_sheet['details']}\n"
        f"Cash Flow: {cash_flow['details']}\n"
        f"Management Actions: {management['details']}"
    )

    # Use provided intrinsic value or calculate if not provided
    if not intrinsic_value:
        intrinsic_value = calculate_intrinsic_value(financial_line_items, current_price)

    valuation_gap = None
    if intrinsic_value and current_price:
        valuation_gap = intrinsic_value - current_price

    return {
        "total_score": total_score,
        "details": details,
        "owner_earnings": owner_earnings,
        "intrinsic_value": intrinsic_value,
        "current_price": current_price,
        "valuation_gap": valuation_gap,
        "breakdown": {
            "profitability": profitability,
            "growth": growth,
            "balance_sheet": balance_sheet,
            "cash_flow": cash_flow,
            "management": management,
        },
    }


# ────────────────────────────────────────────────────────────────────────────────
# LLM generation
# ────────────────────────────────────────────────────────────────────────────────
def generate_jhunjhunwala_output(
    ticker: str,
    analysis_data: dict[str, any],
    model_name: str,
    model_provider: str,
) -> RakeshJhunjhunwalaSignal:
    """Get investment decision from LLM with Jhunjhunwala's principles"""
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a Rakesh Jhunjhunwala AI agent. Decide on investment signals based on Rakesh Jhunjhunwala's principles:
                - Circle of Competence: Only invest in businesses you understand
                - Margin of Safety (> 30%): Buy at a significant discount to intrinsic value
                - Economic Moat: Look for durable competitive advantages
                - Quality Management: Seek conservative, shareholder-oriented teams
                - Financial Strength: Favor low debt, strong returns on equity
                - Long-term Horizon: Invest in businesses, not just stocks
                - Growth Focus: Look for companies with consistent earnings and revenue growth
                - Sell only if fundamentals deteriorate or valuation far exceeds intrinsic value

                When providing your reasoning, be thorough and specific by:
                1. Explaining the key factors that influenced your decision the most (both positive and negative)
                2. Highlighting how the company aligns with or violates specific Jhunjhunwala principles
                3. Providing quantitative evidence where relevant (e.g., specific margins, ROE values, debt levels)
                4. Concluding with a Jhunjhunwala-style assessment of the investment opportunity
                5. Using Rakesh Jhunjhunwala's voice and conversational style in your explanation

                For example, if bullish: "I'm particularly impressed with the consistent growth and strong balance sheet, reminiscent of quality companies that create long-term wealth..."
                For example, if bearish: "The deteriorating margins and high debt levels concern me - this doesn't fit the profile of companies that build lasting value..."

                Follow these guidelines strictly.
                """,
            ),
            (
                "human",
                """Based on the following data, create the investment signal as Rakesh Jhunjhunwala would:

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
    def create_default_rakesh_jhunjhunwala_signal():
        return RakeshJhunjhunwalaSignal(signal="neutral", confidence=0.0, reasoning="Error in analysis, defaulting to neutral")

    return call_llm(
        prompt=prompt,
        model_name=model_name,
        model_provider=model_provider,
        pydantic_model=RakeshJhunjhunwalaSignal,
        agent_name="rakesh_jhunjhunwala_agent",
        default_factory=create_default_rakesh_jhunjhunwala_signal,
    )