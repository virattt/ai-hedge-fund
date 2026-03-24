from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import get_financial_metrics, get_market_cap, search_line_items, get_insider_trades, get_company_news
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import json
from typing_extensions import Literal
from src.utils.progress import progress
from src.utils.llm import call_llm
from src.utils.api_key import get_api_key_from_state

class CharlieMungerSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int
    reasoning: str


def charlie_munger_agent(state: AgentState, agent_id: str = "charlie_munger_agent"):
    """
    Analyzes stocks using Charlie Munger's investing principles and mental models.
    Focuses on moat strength, management quality, predictability, and valuation.
    """
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    analysis_data = {}
    munger_analysis = {}
    
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="annual", limit=10, api_key=api_key)  # Munger looks at longer periods
        
        progress.update_status(agent_id, ticker, "Gathering financial line items")
        financial_line_items = search_line_items(
            ticker,
            [
                "revenue",
                "net_income",
                "operating_income",
                "return_on_invested_capital",
                "gross_margin",
                "operating_margin",
                "free_cash_flow",
                "capital_expenditure",
                "cash_and_equivalents",
                "total_debt",
                "shareholders_equity",
                "outstanding_shares",
                "research_and_development",
                "goodwill_and_intangible_assets",
            ],
            end_date,
            period="annual",
            limit=10,  # Munger examines long-term trends
            api_key=api_key,
        )
        
        progress.update_status(agent_id, ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)
        
        progress.update_status(agent_id, ticker, "Fetching insider trades")
        # Munger values management with skin in the game
        insider_trades = get_insider_trades(
            ticker,
            end_date,
            limit=100,
            api_key=api_key,
        )
        
        progress.update_status(agent_id, ticker, "Fetching company news")
        # Munger avoids businesses with frequent negative press
        company_news = get_company_news(
            ticker,
            end_date,
            limit=10,
            api_key=api_key,
        )
        
        progress.update_status(agent_id, ticker, "Analyzing moat strength")
        moat_analysis = analyze_moat_strength(metrics, financial_line_items)
        
        progress.update_status(agent_id, ticker, "Analyzing management quality")
        management_analysis = analyze_management_quality(financial_line_items, insider_trades)
        
        progress.update_status(agent_id, ticker, "Analyzing business predictability")
        predictability_analysis = analyze_predictability(financial_line_items)
        
        progress.update_status(agent_id, ticker, "Calculating Munger-style valuation")
        valuation_analysis = calculate_munger_valuation(financial_line_items, market_cap)
        
        # Combine partial scores with Munger's weighting preferences
        # Munger weights quality and predictability higher than current valuation
        total_score = (
            moat_analysis["score"] * 0.35 +
            management_analysis["score"] * 0.25 +
            predictability_analysis["score"] * 0.25 +
            valuation_analysis["score"] * 0.15
        )
        
        max_possible_score = 10  # Scale to 0-10
                
        # Generate a simple buy/hold/sell signal
        if total_score >= 7.5:  # Munger has very high standards
            signal = "bullish"
        elif total_score <= 5.5:
            signal = "bearish"
        else:
            signal = "neutral"
        
        analysis_data[ticker] = {
            "signal": signal,
            "score": total_score,
            "max_score": max_possible_score,
            "moat_analysis": moat_analysis,
            "management_analysis": management_analysis,
            "predictability_analysis": predictability_analysis,
            "valuation_analysis": valuation_analysis,
            # Include some qualitative assessment from news
            "news_sentiment": analyze_news_sentiment(company_news) if company_news else "No news data available"
        }
        
        progress.update_status(agent_id, ticker, "Generating Charlie Munger analysis")
        munger_output = generate_munger_output(
            ticker=ticker, 
            analysis_data=analysis_data[ticker],
            state=state,
            agent_id=agent_id,
            confidence_hint=compute_confidence(analysis_data[ticker], signal)
        )
        
        munger_analysis[ticker] = {
            "signal": munger_output.signal,
            "confidence": munger_output.confidence,
            "reasoning": munger_output.reasoning
        }
        
        progress.update_status(agent_id, ticker, "Done", analysis=munger_output.reasoning)
    
    # Wrap results in a single message for the chain
    message = HumanMessage(
        content=json.dumps(munger_analysis),
        name=agent_id
    )
    
    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(munger_analysis, "Charlie Munger Agent")

    progress.update_status(agent_id, None, "Done")
    
    # Add signals to the overall state
    state["data"]["analyst_signals"][agent_id] = munger_analysis

    return {
        "messages": [message],
        "data": state["data"]
    }


def analyze_moat_strength(metrics: list, financial_line_items: list) -> dict:
    """
    Analyze the business's competitive advantage using Munger's approach:
    - Consistent high returns on capital (ROIC)
    - Pricing power (stable/improving gross margins)
    - Low capital requirements
    - Network effects and intangible assets (R&D investments, goodwill)
    """
    score = 0
    details = []
    
    if not metrics or not financial_line_items:
        return {
            "score": 0,
            "details": "Insufficient data to analyze moat strength"
        }
    
    # 1. Return on Invested Capital (ROIC) analysis - Munger's favorite metric
    roic_values = [item.return_on_invested_capital for item in financial_line_items 
                   if hasattr(item, 'return_on_invested_capital') and item.return_on_invested_capital is not None]
    
    if roic_values:
        # Check if ROIC consistently above 15% (Munger's threshold)
        high_roic_count = sum(1 for r in roic_values if r > 0.15)
        if high_roic_count >= len(roic_values) * 0.8:  # 80% of periods show high ROIC
            score += 3
            details.append(f"Excellent ROIC: >15% in {high_roic_count}/{len(roic_values)} periods")
        elif high_roic_count >= len(roic_values) * 0.5:  # 50% of periods
            score += 2
            details.append(f"Good ROIC: >15% in {high_roic_count}/{len(roic_values)} periods")
        elif high_roic_count > 0:
            score += 1
            details.append(f"Mixed ROIC: >15% in only {high_roic_count}/{len(roic_values)} periods")
        else:
            details.append("Poor ROIC: Never exceeds 15% threshold")
    else:
        details.append("No ROIC data available")
    
    # 2. Pricing power - check gross margin stability and trends
    gross_margins = [item.gross_margin for item in financial_line_items 
                    if hasattr(item, 'gross_margin') and item.gross_margin is not None]
    
    if gross_margins and len(gross_margins) >= 3:
        # Munger likes stable or improving gross margins
        margin_trend = sum(1 for i in range(1, len(gross_margins)) if gross_margins[i] >= gross_margins[i-1])
        if margin_trend >= len(gross_margins) * 0.7:  # Improving in 70% of periods
            score += 2
            details.append("Strong pricing power: Gross margins consistently improving")
        elif sum(gross_margins) / len(gross_margins) > 0.3:  # Average margin > 30%
            score += 1
            details.append(f"Good pricing power: Average gross margin {sum(gross_margins)/len(gross_margins):.1%}")
        else:
            details.append("Limited pricing power: Low or declining gross margins")
    else:
        details.append("Insufficient gross margin data")
    
    # 3. Capital intensity - Munger prefers low capex businesses
    if len(financial_line_items) >= 3:
        capex_to_revenue = []
        for item in financial_line_items:
            if (hasattr(item, 'capital_expenditure') and item.capital_expenditure is not None and 
                hasattr(item, 'revenue') and item.revenue is not None and item.revenue > 0):
                # Note: capital_expenditure is typically negative in financial statements
                capex_ratio = abs(item.capital_expenditure) / item.revenue
                capex_to_revenue.append(capex_ratio)
        
        if capex_to_revenue:
            avg_capex_ratio = sum(capex_to_revenue) / len(capex_to_revenue)
            if avg_capex_ratio < 0.05:  # Less than 5% of revenue
                score += 2
                details.append(f"Low capital requirements: Avg capex {avg_capex_ratio:.1%} of revenue")
            elif avg_capex_ratio < 0.10:  # Less than 10% of revenue
                score += 1
                details.append(f"Moderate capital requirements: Avg capex {avg_capex_ratio:.1%} of revenue")
            else:
                details.append(f"High capital requirements: Avg capex {avg_capex_ratio:.1%} of revenue")
        else:
            details.append("No capital expenditure data available")
    else:
        details.append("Insufficient data for capital intensity analysis")
    
    # 4. Intangible assets - Munger values R&D and intellectual property
    r_and_d = [item.research_and_development for item in financial_line_items
              if hasattr(item, 'research_and_development') and item.research_and_development is not None]
    
    goodwill_and_intangible_assets = [item.goodwill_and_intangible_assets for item in financial_line_items
               if hasattr(item, 'goodwill_and_intangible_assets') and item.goodwill_and_intangible_assets is not None]

    if r_and_d and len(r_and_d) > 0:
        if sum(r_and_d) > 0:  # If company is investing in R&D
            score += 1
            details.append("Invests in R&D, building intellectual property")
    
    if (goodwill_and_intangible_assets and len(goodwill_and_intangible_assets) > 0):
        score += 1
        details.append("Significant goodwill/intangible assets, suggesting brand value or IP")
    
    # Scale score to 0-10 range
    final_score = min(10, score * 10 / 9)  # Max possible raw score is 9
    
    return {
        "score": final_score,
        "details": "; ".join(details)
        
    }


def analyze_management_quality(financial_line_items: list, insider_trades: list) -> dict:
    """
    Evaluate management quality using Munger's criteria:
    - Capital allocation wisdom
    - Insider ownership and transactions
    - Cash management efficiency
    - Candor and transparency
    - Long-term focus
    """
    score = 0
    details = []
    
    if not financial_line_items:
        return {
            "score": 0,
            "details": "Insufficient data to analyze management quality"
        }
    
    # 1. Capital allocation - Check FCF to net income ratio
    # Munger values companies that convert earnings to cash
    fcf_values = [item.free_cash_flow for item in financial_line_items 
                 if hasattr(item, 'free_cash_flow') and item.free_cash_flow is not None]
    
    net_income_values = [item.net_income for item in financial_line_items 
                        if hasattr(item, 'net_income') and item.net_income is not None]
    
    if fcf_values and net_income_values and len(fcf_values) == len(net_income_values):
        # Calculate FCF to Net Income ratio for each period
        fcf_to_ni_ratios = []
        for i in range(len(fcf_values)):
            if net_income_values[i] and net_income_values[i] > 0:
                fcf_to_ni_ratios.append(fcf_values[i] / net_income_values[i])
        
        if fcf_to_ni_ratios:
            avg_ratio = sum(fcf_to_ni_ratios) / len(fcf_to_ni_ratios)
            if avg_ratio > 1.1:  # FCF > net income suggests good accounting
                score += 3
                details.append(f"Excellent cash conversion: FCF/NI ratio of {avg_ratio:.2f}")
            elif avg_ratio > 0.9:  # FCF roughly equals net income
                score += 2
                details.append(f"Good cash conversion: FCF/NI ratio of {avg_ratio:.2f}")
            elif avg_ratio > 0.7:  # FCF somewhat lower than net income
                score += 1
                details.append(f"Moderate cash conversion: FCF/NI ratio of {avg_ratio:.2f}")
            else:
                details.append(f"Poor cash conversion: FCF/NI ratio of only {avg_ratio:.2f}")
        else:
            details.append("Could not calculate FCF to Net Income ratios")
    else:
        details.append("Missing FCF or Net Income data")
    
    # 2. Debt management - Munger is cautious about debt
    debt_values = [item.total_debt for item in financial_line_items 
                  if hasattr(item, 'total_debt') and item.total_debt is not None]
    
    equity_values = [item.shareholders_equity for item in financial_line_items 
                    if hasattr(item, 'shareholders_equity') and item.shareholders_equity is not None]
    
    if debt_values and equity_values and len(debt_values) == len(equity_values):
        # Calculate D/E ratio for most recent period
        recent_de_ratio = debt_values[0] / equity_values[0] if equity_values[0] > 0 else float('inf')
        
        if recent_de_ratio < 0.3:  # Very low debt
            score += 3
            details.append(f"Conservative debt management: D/E ratio of {recent_de_ratio:.2f}")
        elif recent_de_ratio < 0.7:  # Moderate debt
            score += 2
            details.append(f"Prudent debt management: D/E ratio of {recent_de_ratio:.2f}")
        elif recent_de_ratio < 1.5:  # Higher but still reasonable debt
            score += 1
            details.append(f"Moderate debt level: D/E ratio of {recent_de_ratio:.2f}")
        else:
            details.append(f"High debt level: D/E ratio of {recent_de_ratio:.2f}")
    else:
        details.append("Missing debt or equity data")
    
    # 3. Cash management efficiency - Munger values appropriate cash levels
    cash_values = [item.cash_and_equivalents for item in financial_line_items
                  if hasattr(item, 'cash_and_equivalents') and item.cash_and_equivalents is not None]
    revenue_values = [item.revenue for item in financial_line_items
                     if hasattr(item, 'revenue') and item.revenue is not None]
    
    if cash_values and revenue_values and len(cash_values) > 0 and len(revenue_values) > 0:
        # Calculate cash to revenue ratio (Munger likes 10-20% for most businesses)
        cash_to_revenue = cash_values[0] / revenue_values[0] if revenue_values[0] > 0 else 0
        
        if 0.1 <= cash_to_revenue <= 0.25:
            # Goldilocks zone - not too much, not too little
            score += 2
            details.append(f"Prudent cash management: Cash/Revenue ratio of {cash_to_revenue:.2f}")
        elif 0.05 <= cash_to_revenue < 0.1 or 0.25 < cash_to_revenue <= 0.4:
            # Reasonable but not ideal
            score += 1
            details.append(f"Acceptable cash position: Cash/Revenue ratio of {cash_to_revenue:.2f}")
        elif cash_to_revenue > 0.4:
            # Too much cash - potentially inefficient capital allocation
            details.append(f"Excess cash reserves: Cash/Revenue ratio of {cash_to_revenue:.2f}")
        else:
            # Too little cash - potentially risky
            details.append(f"Low cash reserves: Cash/Revenue ratio of {cash_to_revenue:.2f}")
    else:
        details.append("Insufficient cash or revenue data")
    
    # 4. Insider activity - Munger values skin in the game
    if insider_trades and len(insider_trades) > 0:
        # Count buys vs. sells
        buys = sum(1 for trade in insider_trades if hasattr(trade, 'transaction_type') and 
                   trade.transaction_type and trade.transaction_type.lower() in ['buy', 'purchase'])
        sells = sum(1 for trade in insider_trades if hasattr(trade, 'transaction_type') and 
                    trade.transaction_type and trade.transaction_type.lower() in ['sell', 'sale'])
        
        # Calculate the buy ratio
        total_trades = buys + sells
        if total_trades > 0:
            buy_ratio = buys / total_trades
            if buy_ratio > 0.7:  # Strong insider buying
                score += 2
                details.append(f"Strong insider buying: {buys}/{total_trades} transactions are purchases")
            elif buy_ratio > 0.4:  # Balanced insider activity
                score += 1
                details.append(f"Balanced insider trading: {buys}/{total_trades} transactions are purchases")
            elif buy_ratio < 0.1 and sells > 5:  # Heavy selling
                score -= 1  # Penalty for excessive selling
                details.append(f"Concerning insider selling: {sells}/{total_trades} transactions are sales")
            else:
                details.append(f"Mixed insider activity: {buys}/{total_trades} transactions are purchases")
        else:
            details.append("No recorded insider transactions")
    else:
        details.append("No insider trading data available")
    
    # 5. Consistency in share count - Munger prefers stable/decreasing shares
    share_counts = [item.outstanding_shares for item in financial_line_items
                   if hasattr(item, 'outstanding_shares') and item.outstanding_shares is not None]
    
    if share_counts and len(share_counts) >= 3:
        if share_counts[0] < share_counts[-1] * 0.95:  # 5%+ reduction in shares
            score += 2
            details.append("Shareholder-friendly: Reducing share count over time")
        elif share_counts[0] < share_counts[-1] * 1.05:  # Stable share count
            score += 1
            details.append("Stable share count: Limited dilution")
        elif share_counts[0] > share_counts[-1] * 1.2:  # >20% dilution
            score -= 1  # Penalty for excessive dilution
            details.append("Concerning dilution: Share count increased significantly")
        else:
            details.append("Moderate share count increase over time")
    else:
        details.append("Insufficient share count data")
    

    # FCF / NI ratios -> already computed for scoring
    insider_buy_ratio = None
    recent_de_ratio = None
    cash_to_revenue = None
    share_count_trend = "unknown"

    # Debt ratio (D/E) -> we compute `recent_de_ratio`
    if debt_values and equity_values and len(debt_values) == len(equity_values):
        recent_de_ratio = debt_values[0] / equity_values[0] if equity_values[0] > 0 else float("inf")

    # Cash/Revenue -> we compute `cash_to_revenue`
    if cash_values and revenue_values and revenue_values[0] and revenue_values[0] > 0:
        cash_to_revenue = cash_values[0] / revenue_values[0]

    # Insider ratio -> we compute `insider_buy_ratio`
    if insider_trades and len(insider_trades) > 0:
        buys = sum(1 for t in insider_trades
                   if getattr(t, "transaction_type", None)
                   and t.transaction_type.lower() in ["buy", "purchase"])
        sells = sum(1 for t in insider_trades
                    if getattr(t, "transaction_type", None)
                    and t.transaction_type.lower() in ["sell", "sale"])
        total = buys + sells
        insider_buy_ratio = (buys / total) if total > 0 else None

    # Share count trend (decreasing / stable / increasing)
    share_counts = [item.outstanding_shares for item in financial_line_items
                    if hasattr(item, "outstanding_shares") and item.outstanding_shares is not None]
    if share_counts and len(share_counts) >= 3:
        if share_counts[0] < share_counts[-1] * 0.95:
            share_count_trend = "decreasing"
        elif share_counts[0] > share_counts[-1] * 1.05:
            share_count_trend = "increasing"
        else:
            share_count_trend = "stable"

    # Scale score to 0-10 range
    # Maximum possible raw score would be 12 (3+3+2+2+2)
    final_score = max(0, min(10, score * 10 / 12))
    
    return {
        "score": final_score,
        "details": "; ".join(details),
        "insider_buy_ratio": insider_buy_ratio,
        "recent_de_ratio": recent_de_ratio,
        "cash_to_revenue": cash_to_revenue,
        "share_count_trend": share_count_trend,
    }


def analyze_predictability(financial_line_items: list) -> dict:
    """
    Assess the predictability of the business - Munger strongly prefers businesses
    whose future operations and cashflows are relatively easy to predict.
    """
    score = 0
    details = []
    
    if not financial_line_items or len(financial_line_items) < 5:
        return {
            "score": 0,
            "details": "Insufficient data to analyze business predictability (need 5+ years)"
        }
    
    # 1. Revenue stability and growth
    revenues = [item.revenue for item in financial_line_items 
               if hasattr(item, 'revenue') and item.revenue is not None]
    
    if revenues and len(revenues) >= 5:
        # Calculate year-over-year growth rates, handling zero division
        growth_rates = []
        for i in range(len(revenues)-1):
            if revenues[i+1] != 0:  # Avoid division by zero
                growth_rate = (revenues[i] / revenues[i+1] - 1)
                growth_rates.append(growth_rate)
        
        if not growth_rates:
            details.append("Cannot calculate revenue growth: zero revenue values found")
        else:
            avg_growth = sum(growth_rates) / len(growth_rates)
            growth_volatility = sum(abs(r - avg_growth) for r in growth_rates) / len(growth_rates)
            
            if avg_growth > 0.05 and growth_volatility < 0.1:
                # Steady, consistent growth (Munger loves this)
                score += 3
                details.append(f"Highly predictable revenue: {avg_growth:.1%} avg growth with low volatility")
            elif avg_growth > 0 and growth_volatility < 0.2:
                # Positive but somewhat volatile growth
                score += 2
                details.append(f"Moderately predictable revenue: {avg_growth:.1%} avg growth with some volatility")
            elif avg_growth > 0:
                # Growing but unpredictable
                score += 1
                details.append(f"Growing but less predictable revenue: {avg_growth:.1%} avg growth with high volatility")
            else:
                details.append(f"Declining or highly unpredictable revenue: {avg_growth:.1%} avg growth")
    else:
        details.append("Insufficient revenue history for predictability analysis")
    
    # 2. Operating income stability
    op_income = [item.operating_income for item in financial_line_items 
                if hasattr(item, 'operating_income') and item.operating_income is not None]
    
    if op_income and len(op_income) >= 5:
        # Count positive operating income periods
        positive_periods = sum(1 for income in op_income if income > 0)
        
        if positive_periods == len(op_income):
            # Consistently profitable operations
            score += 3
            details.append("Highly predictable operations: Operating income positive in all periods")
        elif positive_periods >= len(op_income) * 0.8:
            # Mostly profitable operations
            score += 2
            details.append(f"Predictable operations: Operating income positive in {positive_periods}/{len(op_income)} periods")
        elif positive_periods >= len(op_income) * 0.6:
            # Somewhat profitable operations
            score += 1
            details.append(f"Somewhat predictable operations: Operating income positive in {positive_periods}/{len(op_income)} periods")
        else:
            details.append(f"Unpredictable operations: Operating income positive in only {positive_periods}/{len(op_income)} periods")
    else:
        details.append("Insufficient operating income history")
    
    # 3. Margin consistency - Munger values stable margins
    op_margins = [item.operating_margin for item in financial_line_items 
                 if hasattr(item, 'operating_margin') and item.operating_margin is not None]
    
    if op_margins and len(op_margins) >= 5:
        # Calculate margin volatility
        avg_margin = sum(op_margins) / len(op_margins)
        margin_volatility = sum(abs(m - avg_margin) for m in op_margins) / len(op_margins)
        
        if margin_volatility < 0.03:  # Very stable margins
            score += 2
            details.append(f"Highly predictable margins: {avg_margin:.1%} avg with minimal volatility")
        elif margin_volatility < 0.07:  # Moderately stable margins
            score += 1
            details.append(f"Moderately predictable margins: {avg_margin:.1%} avg with some volatility")
        else:
            details.append(f"Unpredictable margins: {avg_margin:.1%} avg with high volatility ({margin_volatility:.1%})")
    else:
        details.append("Insufficient margin history")
    
    # 4. Cash generation reliability
    fcf_values = [item.free_cash_flow for item in financial_line_items 
                 if hasattr(item, 'free_cash_flow') and item.free_cash_flow is not None]
    
    if fcf_values and len(fcf_values) >= 5:
        # Count positive FCF periods
        positive_fcf_periods = sum(1 for fcf in fcf_values if fcf > 0)
        
        if positive_fcf_periods == len(fcf_values):
            # Consistently positive FCF
            score += 2
            details.append("Highly predictable cash generation: Positive FCF in all periods")
        elif positive_fcf_periods >= len(fcf_values) * 0.8:
            # Mostly positive FCF
            score += 1
            details.append(f"Predictable cash generation: Positive FCF in {positive_fcf_periods}/{len(fcf_values)} periods")
        else:
            details.append(f"Unpredictable cash generation: Positive FCF in only {positive_fcf_periods}/{len(fcf_values)} periods")
    else:
        details.append("Insufficient free cash flow history")
    
    # Scale score to 0-10 range
    # Maximum possible raw score would be 10 (3+3+2+2)
    final_score = min(10, score * 10 / 10)
    
    return {
        "score": final_score,
        "details": "; ".join(details)
    }


def calculate_munger_valuation(financial_line_items: list, market_cap: float) -> dict:
    """
    Calculate intrinsic value using Munger's approach:
    - Focus on owner earnings (approximated by FCF)
    - Simple multiple on normalized earnings
    - Prefer paying a fair price for a wonderful business
    """
    score = 0
    details = []
    
    if not financial_line_items or market_cap is None:
        return {
            "score": 0,
            "details": "Insufficient data to perform valuation"
        }
    
    # Get FCF values (Munger's preferred "owner earnings" metric)
    fcf_values = [item.free_cash_flow for item in financial_line_items 
                 if hasattr(item, 'free_cash_flow') and item.free_cash_flow is not None]
    
    if not fcf_values or len(fcf_values) < 3:
        return {
            "score": 0,
            "details": "Insufficient free cash flow data for valuation"
        }
    
    # 1. Normalize earnings by taking average of last 3-5 years
    # (Munger prefers to normalize earnings to avoid over/under-valuation based on cyclical factors)
    normalized_fcf = sum(fcf_values[:min(5, len(fcf_values))]) / min(5, len(fcf_values))
    
    if normalized_fcf <= 0:
        return {
            "score": 0,
            "details": f"Negative or zero normalized FCF ({normalized_fcf}), cannot value",
            "intrinsic_value": None
        }
    
    # 2. Calculate FCF yield (inverse of P/FCF multiple)
    if market_cap <= 0:
        return {
            "score": 0,
            "details": f"Invalid market cap ({market_cap}), cannot value"
        }
    
    fcf_yield = normalized_fcf / market_cap
    
    # 3. Apply Munger's FCF multiple based on business quality
    # Munger would pay higher multiples for wonderful businesses
    # Let's use a sliding scale where higher FCF yields are more attractive
    if fcf_yield > 0.08:  # >8% FCF yield (P/FCF < 12.5x)
        score += 4
        details.append(f"Excellent value: {fcf_yield:.1%} FCF yield")
    elif fcf_yield > 0.05:  # >5% FCF yield (P/FCF < 20x)
        score += 3
        details.append(f"Good value: {fcf_yield:.1%} FCF yield")
    elif fcf_yield > 0.03:  # >3% FCF yield (P/FCF < 33x)
        score += 1
        details.append(f"Fair value: {fcf_yield:.1%} FCF yield")
    else:
        details.append(f"Expensive: Only {fcf_yield:.1%} FCF yield")
    
    # 4. Calculate simple intrinsic value range
    # Munger tends to use straightforward valuations, avoiding complex DCF models
    conservative_value = normalized_fcf * 10  # 10x FCF = 10% yield
    reasonable_value = normalized_fcf * 15    # 15x FCF ≈ 6.7% yield
    optimistic_value = normalized_fcf * 20    # 20x FCF = 5% yield
    
    # 5. Calculate margins of safety
    margin_of_safety_vs_fair_value = (reasonable_value - market_cap) / market_cap
    
    if margin_of_safety_vs_fair_value > 0.3:  # >30% upside
        score += 3
        details.append(f"Large margin of safety: {margin_of_safety_vs_fair_value:.1%} upside to reasonable value")
    elif margin_of_safety_vs_fair_value > 0.1:  # >10% upside
        score += 2
        details.append(f"Moderate margin of safety: {margin_of_safety_vs_fair_value:.1%} upside to reasonable value")
    elif margin_of_safety_vs_fair_value > -0.1:  # Within 10% of reasonable value
        score += 1
        details.append(f"Fair price: Within 10% of reasonable value ({margin_of_safety_vs_fair_value:.1%})")
    else:
        details.append(f"Expensive: {-margin_of_safety_vs_fair_value:.1%} premium to reasonable value")
    
    # 6. Check earnings trajectory for additional context
    # Munger likes growing owner earnings
    if len(fcf_values) >= 3:
        recent_avg = sum(fcf_values[:3]) / 3
        older_avg = sum(fcf_values[-3:]) / 3 if len(fcf_values) >= 6 else fcf_values[-1]
        
        if recent_avg > older_avg * 1.2:  # >20% growth in FCF
            score += 3
            details.append("Growing FCF trend adds to intrinsic value")
        elif recent_avg > older_avg:
            score += 2
            details.append("Stable to growing FCF supports valuation")
        else:
            details.append("Declining FCF trend is concerning")

    # Scale score to 0-10 range
    # Maximum possible raw score would be 10 (4+3+3)
    final_score = min(10, score * 10 / 10) 
    
    return {
        "score": final_score,
        "details": "; ".join(details),
        "intrinsic_value_range": {
            "conservative": conservative_value,
            "reasonable": reasonable_value,
            "optimistic": optimistic_value
        },
        "fcf_yield": fcf_yield,
        "normalized_fcf": normalized_fcf,
        "margin_of_safety_vs_fair_value": margin_of_safety_vs_fair_value,

    }


def analyze_news_sentiment(news_items: list) -> str:
    """
    Simple qualitative analysis of recent news.
    Munger pays attention to significant news but doesn't overreact to short-term stories.
    """
    if not news_items or len(news_items) == 0:
        return "No news data available"
    
    # Just return a simple count for now - in a real implementation, this would use NLP
    return f"Qualitative review of {len(news_items)} recent news items would be needed"

def _r(x, n=3):
    try:
        return round(float(x), n)
    except Exception:
        return None

def make_munger_facts_bundle(analysis: dict[str, any]) -> dict[str, any]:
    moat = analysis.get("moat_analysis") or {}
    mgmt = analysis.get("management_analysis") or {}
    pred = analysis.get("predictability_analysis") or {}
    val  = analysis.get("valuation_analysis") or {}
    ivr  = val.get("intrinsic_value_range") or {}

    moat_score = _r(moat.get("score"), 2) or 0
    mgmt_score = _r(mgmt.get("score"), 2) or 0
    pred_score = _r(pred.get("score"), 2) or 0
    val_score  = _r(val.get("score"), 2) or 0

    # Simple mental-model flags (booleans/ints = cheap tokens, strong guidance)
    flags = {
        "moat_strong": moat_score >= 7,
        "predictable": pred_score >= 7,
        "owner_aligned": (mgmt_score >= 7) or ((mgmt.get("insider_buy_ratio") or 0) >= 0.6),
        "low_leverage": (mgmt.get("recent_de_ratio") is not None and mgmt.get("recent_de_ratio") < 0.7),
        "sensible_cash": (mgmt.get("cash_to_revenue") is not None and 0.1 <= mgmt.get("cash_to_revenue") <= 0.25),
        "low_capex": None,  # inferred in moat score already; keep placeholder if you later expose a ratio
        "mos_positive": (val.get("mos_to_reasonable") or 0) > 0.0,
        "fcf_yield_ok": (val.get("fcf_yield") or 0) >= 0.05,
        "share_count_friendly": (mgmt.get("share_count_trend") == "decreasing"),
    }

    return {
        "pre_signal": analysis.get("signal"),
        "score": _r(analysis.get("score"), 2),
        "max_score": _r(analysis.get("max_score"), 2),
        "moat_score": moat_score,
        "mgmt_score": mgmt_score,
        "predictability_score": pred_score,
        "valuation_score": val_score,
        "fcf_yield": _r(val.get("fcf_yield"), 4),
        "normalized_fcf": _r(val.get("normalized_fcf"), 0),
        "reasonable_value": _r(ivr.get("reasonable"), 0),
        "margin_of_safety_vs_fair_value": _r(val.get("margin_of_safety_vs_fair_value"), 3),
        "insider_buy_ratio": _r(mgmt.get("insider_buy_ratio"), 2),
        "recent_de_ratio": _r(mgmt.get("recent_de_ratio"), 2),
        "cash_to_revenue": _r(mgmt.get("cash_to_revenue"), 2),
        "share_count_trend": mgmt.get("share_count_trend"),
        "flags": flags,
        # keep one-liners, very short
        "notes": {
            "moat": (moat.get("details") or "")[:120],
            "mgmt": (mgmt.get("details") or "")[:120],
            "predictability": (pred.get("details") or "")[:120],
            "valuation": (val.get("details") or "")[:120],
        },
    }

def compute_confidence(analysis: dict, signal: str) -> int:
    # Pull component scores (0..10 each in your pipeline)
    moat = float((analysis.get("moat_analysis") or {}).get("score") or 0)
    mgmt = float((analysis.get("management_analysis") or {}).get("score") or 0)
    pred = float((analysis.get("predictability_analysis") or {}).get("score") or 0)
    val  = float((analysis.get("valuation_analysis") or {}).get("score") or 0)

    # Quality dominates (Munger): 0.35*moat + 0.25*mgmt + 0.25*pred (max 8.5)
    quality = 0.35 * moat + 0.25 * mgmt + 0.25 * pred  # 0..8.5
    quality_pct = 100 * (quality / 8.5) if quality > 0 else 0  # 0..100

    # Valuation bump from MOS vs “reasonable”
    mos = (analysis.get("valuation_analysis") or {}).get("margin_of_safety_vs_fair_value")
    mos = float(mos) if mos is not None else 0.0
    # Convert MOS into a bounded +/-10pp adjustment
    val_adj = max(-10.0, min(10.0, mos * 100.0 / 3.0))  # ~+/-10pp if MOS is around +/-30%

    # Base confidence: weighted toward quality, then small valuation adjustment
    base = 0.85 * quality_pct + 0.15 * (val * 10)  # val score 0..10 -> 0..100
    base = base + val_adj

    # Ensure bucket semantics by clamping into Munger buckets depending on signal
    if signal == "bullish":
        # If overvalued (mos<0), cap to mixed bucket
        upper = 100 if mos > 0 else 69
        lower = 50 if quality_pct >= 55 else 30
    elif signal == "bearish":
        # If clearly overvalued (mos< -0.05), allow very low bucket
        lower = 10 if mos < -0.05 else 30
        upper = 49
    else:  # neutral
        lower, upper = 50, 69

    conf = int(round(max(lower, min(upper, base))))
    # Keep inside global 10..100
    return max(10, min(100, conf))


def generate_munger_output(
    ticker: str,
    analysis_data: dict[str, any],
    state: AgentState,
    agent_id: str,
    confidence_hint: int,
) -> CharlieMungerSignal:
    facts_bundle = make_munger_facts_bundle(analysis_data)
    template = ChatPromptTemplate.from_messages([
        ("system",
         "You are Charlie Munger. Decide bullish, bearish, or neutral using only the facts. "
         "Return JSON only. Keep reasoning under 120 characters. "
         "Use the provided confidence exactly; do not change it."),
        ("human",
         "Ticker: {ticker}\n"
         "Facts:\n{facts}\n"
         "Confidence: {confidence}\n"
         "Return exactly:\n"
         "{{\n"  # escaped {
         '  "signal": "bullish" | "bearish" | "neutral",\n'
         f'  "confidence": {confidence_hint},\n'
         '  "reasoning": "short justification"\n'
         "}}")  # escaped }
    ])

    prompt = template.invoke({
        "ticker": ticker,
        "facts": json.dumps(facts_bundle, separators=(",", ":"), ensure_ascii=False),
        "confidence": confidence_hint,
    })

    def _default():
        return CharlieMungerSignal(signal="neutral", confidence=confidence_hint, reasoning="Insufficient data")

    return call_llm(
        prompt=prompt,
        pydantic_model=CharlieMungerSignal,
        agent_name=agent_id,
        state=state,
        default_factory=_default,
    )
