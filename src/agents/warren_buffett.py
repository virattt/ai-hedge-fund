from graph.state import AgentState, show_agent_reasoning
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
import json
from typing_extensions import Literal
from tools.api import get_financial_metrics, get_market_cap, search_line_items
from utils.llm import call_llm
from utils.progress import progress
from utils.api_key import get_api_key_from_state


class WarrenBuffettSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")


def warren_buffett_agent(state: AgentState, agent_id: str = "warren_buffett_agent"):
    """Analyzes stocks using Buffett's principles and LLM reasoning."""
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    # Collect all analysis for LLM reasoning
    analysis_data = {}
    buffett_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        # Fetch required data - request more periods for better trend analysis
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=10, api_key=api_key)

        progress.update_status(agent_id, ticker, "Gathering financial line items")
        financial_line_items = search_line_items(
            ticker,
            [
                "capital_expenditure",
                "depreciation_and_amortization",
                "net_income",
                "outstanding_shares",
                "total_assets",
                "total_liabilities",
                "shareholders_equity",
                "dividends_and_other_cash_distributions",
                "issuance_or_purchase_of_equity_shares",
                "gross_profit",
                "revenue",
                "free_cash_flow",
            ],
            end_date,
            period="ttm",
            limit=10,
            api_key=api_key,
        )

        progress.update_status(agent_id, ticker, "Getting market cap")
        # Get current market cap
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)

        progress.update_status(agent_id, ticker, "Analyzing fundamentals")
        # Analyze fundamentals
        fundamental_analysis = analyze_fundamentals(metrics)

        progress.update_status(agent_id, ticker, "Analyzing consistency")
        consistency_analysis = analyze_consistency(financial_line_items)

        progress.update_status(agent_id, ticker, "Analyzing competitive moat")
        moat_analysis = analyze_moat(metrics)

        progress.update_status(agent_id, ticker, "Analyzing pricing power")
        pricing_power_analysis = analyze_pricing_power(financial_line_items, metrics)

        progress.update_status(agent_id, ticker, "Analyzing book value growth")
        book_value_analysis = analyze_book_value_growth(financial_line_items)

        progress.update_status(agent_id, ticker, "Analyzing management quality")
        mgmt_analysis = analyze_management_quality(financial_line_items)

        progress.update_status(agent_id, ticker, "Calculating intrinsic value")
        intrinsic_value_analysis = calculate_intrinsic_value(financial_line_items)

        # Calculate total score without circle of competence (LLM will handle that)
        total_score = (
                fundamental_analysis["score"] +
                consistency_analysis["score"] +
                moat_analysis["score"] +
                mgmt_analysis["score"] +
                pricing_power_analysis["score"] +
                book_value_analysis["score"]
        )

        # Update max possible score calculation
        max_possible_score = (
                10 +  # fundamental_analysis (ROE, debt, margins, current ratio)
                moat_analysis["max_score"] +
                mgmt_analysis["max_score"] +
                5 +  # pricing_power (0-5)
                5  # book_value_growth (0-5)
        )

        # Add margin of safety analysis if we have both intrinsic value and current price
        margin_of_safety = None
        intrinsic_value = intrinsic_value_analysis["intrinsic_value"]
        if intrinsic_value and market_cap:
            margin_of_safety = (intrinsic_value - market_cap) / market_cap

        # Combine all analysis results for LLM evaluation
        analysis_data[ticker] = {
            "ticker": ticker,
            "score": total_score,
            "max_score": max_possible_score,
            "fundamental_analysis": fundamental_analysis,
            "consistency_analysis": consistency_analysis,
            "moat_analysis": moat_analysis,
            "pricing_power_analysis": pricing_power_analysis,
            "book_value_analysis": book_value_analysis,
            "management_analysis": mgmt_analysis,
            "intrinsic_value_analysis": intrinsic_value_analysis,
            "market_cap": market_cap,
            "margin_of_safety": margin_of_safety,
        }

        progress.update_status(agent_id, ticker, "Generating Warren Buffett analysis")
        buffett_output = generate_buffett_output(
            ticker=ticker,
            analysis_data=analysis_data[ticker],
            state=state,
            agent_id=agent_id,
        )

        # Store analysis in consistent format with other agents
        buffett_analysis[ticker] = {
            "signal": buffett_output.signal,
            "confidence": buffett_output.confidence,
            "reasoning": buffett_output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=buffett_output.reasoning)

    # Create the message
    message = HumanMessage(content=json.dumps(buffett_analysis), name=agent_id)

    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(buffett_analysis, agent_id)

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"][agent_id] = buffett_analysis

    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}


def analyze_fundamentals(metrics: list) -> dict[str, any]:
    """Analyze company fundamentals based on Buffett's criteria."""
    if not metrics:
        return {"score": 0, "details": "Insufficient fundamental data"}

    latest_metrics = metrics[0]

    score = 0
    reasoning = []

    # Check ROE (Return on Equity)
    if latest_metrics.return_on_equity and latest_metrics.return_on_equity > 0.15:  # 15% ROE threshold
        score += 2
        reasoning.append(f"Strong ROE of {latest_metrics.return_on_equity:.1%}")
    elif latest_metrics.return_on_equity:
        reasoning.append(f"Weak ROE of {latest_metrics.return_on_equity:.1%}")
    else:
        reasoning.append("ROE data not available")

    # Check Debt to Equity
    if latest_metrics.debt_to_equity and latest_metrics.debt_to_equity < 0.5:
        score += 2
        reasoning.append("Conservative debt levels")
    elif latest_metrics.debt_to_equity:
        reasoning.append(f"High debt to equity ratio of {latest_metrics.debt_to_equity:.1f}")
    else:
        reasoning.append("Debt to equity data not available")

    # Check Operating Margin
    if latest_metrics.operating_margin and latest_metrics.operating_margin > 0.15:
        score += 2
        reasoning.append("Strong operating margins")
    elif latest_metrics.operating_margin:
        reasoning.append(f"Weak operating margin of {latest_metrics.operating_margin:.1%}")
    else:
        reasoning.append("Operating margin data not available")

    # Check Current Ratio
    if latest_metrics.current_ratio and latest_metrics.current_ratio > 1.5:
        score += 1
        reasoning.append("Good liquidity position")
    elif latest_metrics.current_ratio:
        reasoning.append(f"Weak liquidity with current ratio of {latest_metrics.current_ratio:.1f}")
    else:
        reasoning.append("Current ratio data not available")

    return {"score": score, "details": "; ".join(reasoning), "metrics": latest_metrics.model_dump()}


def analyze_consistency(financial_line_items: list) -> dict[str, any]:
    """Analyze earnings consistency and growth."""
    if len(financial_line_items) < 4:  # Need at least 4 periods for trend analysis
        return {"score": 0, "details": "Insufficient historical data"}

    score = 0
    reasoning = []

    # Check earnings growth trend
    earnings_values = [item.net_income for item in financial_line_items if item.net_income]
    if len(earnings_values) >= 4:
        # Simple check: is each period's earnings bigger than the next?
        earnings_growth = all(earnings_values[i] > earnings_values[i + 1] for i in range(len(earnings_values) - 1))

        if earnings_growth:
            score += 3
            reasoning.append("Consistent earnings growth over past periods")
        else:
            reasoning.append("Inconsistent earnings growth pattern")

        # Calculate total growth rate from oldest to latest
        if len(earnings_values) >= 2 and earnings_values[-1] != 0:
            growth_rate = (earnings_values[0] - earnings_values[-1]) / abs(earnings_values[-1])
            reasoning.append(f"Total earnings growth of {growth_rate:.1%} over past {len(earnings_values)} periods")
    else:
        reasoning.append("Insufficient earnings data for trend analysis")

    return {
        "score": score,
        "details": "; ".join(reasoning),
    }


def analyze_moat(metrics: list) -> dict[str, any]:
    """
    Evaluate whether the company likely has a durable competitive advantage (moat).
    Enhanced to include multiple moat indicators that Buffett actually looks for:
    1. Consistent high returns on capital
    2. Pricing power (stable/growing margins)
    3. Scale advantages (improving metrics with size)
    4. Brand strength (inferred from margins and consistency)
    5. Switching costs (inferred from customer retention)
    """
    if not metrics or len(metrics) < 5:  # Need more data for proper moat analysis
        return {"score": 0, "max_score": 5, "details": "Insufficient data for comprehensive moat analysis"}

    reasoning = []
    moat_score = 0
    max_score = 5

    # 1. Return on Capital Consistency (Buffett's favorite moat indicator)
    historical_roes = [m.return_on_equity for m in metrics if m.return_on_equity is not None]
    historical_roics = [m.return_on_invested_capital for m in metrics if
                        hasattr(m, 'return_on_invested_capital') and m.return_on_invested_capital is not None]

    if len(historical_roes) >= 5:
        # Check for consistently high ROE (>15% for most periods)
        high_roe_periods = sum(1 for roe in historical_roes if roe > 0.15)
        roe_consistency = high_roe_periods / len(historical_roes)

        if roe_consistency >= 0.8:  # 80%+ of periods with ROE > 15%
            moat_score += 2
            avg_roe = sum(historical_roes) / len(historical_roes)
            reasoning.append(
                f"Excellent ROE consistency: {high_roe_periods}/{len(historical_roes)} periods >15% (avg: {avg_roe:.1%}) - indicates durable competitive advantage")
        elif roe_consistency >= 0.6:
            moat_score += 1
            reasoning.append(f"Good ROE performance: {high_roe_periods}/{len(historical_roes)} periods >15%")
        else:
            reasoning.append(f"Inconsistent ROE: only {high_roe_periods}/{len(historical_roes)} periods >15%")
    else:
        reasoning.append("Insufficient ROE history for moat analysis")

    # 2. Operating Margin Stability (Pricing Power Indicator)
    historical_margins = [m.operating_margin for m in metrics if m.operating_margin is not None]
    if len(historical_margins) >= 5:
        # Check for stable or improving margins (sign of pricing power)
        avg_margin = sum(historical_margins) / len(historical_margins)
        recent_margins = historical_margins[:3]  # Last 3 periods
        older_margins = historical_margins[-3:]  # First 3 periods

        recent_avg = sum(recent_margins) / len(recent_margins)
        older_avg = sum(older_margins) / len(older_margins)

        if avg_margin > 0.2 and recent_avg >= older_avg:  # 20%+ margins and stable/improving
            moat_score += 1
            reasoning.append(f"Strong and stable operating margins (avg: {avg_margin:.1%}) indicate pricing power moat")
        elif avg_margin > 0.15:  # At least decent margins
            reasoning.append(f"Decent operating margins (avg: {avg_margin:.1%}) suggest some competitive advantage")
        else:
            reasoning.append(f"Low operating margins (avg: {avg_margin:.1%}) suggest limited pricing power")

    # 3. Asset Efficiency and Scale Advantages
    if len(metrics) >= 5:
        # Check asset turnover trends (revenue efficiency)
        asset_turnovers = []
        for m in metrics:
            if hasattr(m, 'asset_turnover') and m.asset_turnover is not None:
                asset_turnovers.append(m.asset_turnover)

        if len(asset_turnovers) >= 3:
            if any(turnover > 1.0 for turnover in asset_turnovers):  # Efficient asset use
                moat_score += 1
                reasoning.append("Efficient asset utilization suggests operational moat")

    # 4. Competitive Position Strength (inferred from trend stability)
    if len(historical_roes) >= 5 and len(historical_margins) >= 5:
        # Calculate coefficient of variation (stability measure)
        roe_avg = sum(historical_roes) / len(historical_roes)
        roe_variance = sum((roe - roe_avg) ** 2 for roe in historical_roes) / len(historical_roes)
        roe_stability = 1 - (roe_variance ** 0.5) / roe_avg if roe_avg > 0 else 0

        margin_avg = sum(historical_margins) / len(historical_margins)
        margin_variance = sum((margin - margin_avg) ** 2 for margin in historical_margins) / len(historical_margins)
        margin_stability = 1 - (margin_variance ** 0.5) / margin_avg if margin_avg > 0 else 0

        overall_stability = (roe_stability + margin_stability) / 2

        if overall_stability > 0.7:  # High stability indicates strong competitive position
            moat_score += 1
            reasoning.append(f"High performance stability ({overall_stability:.1%}) suggests strong competitive moat")

    # Cap the score at max_score
    moat_score = min(moat_score, max_score)

    return {
        "score": moat_score,
        "max_score": max_score,
        "details": "; ".join(reasoning) if reasoning else "Limited moat analysis available",
    }


def analyze_management_quality(financial_line_items: list) -> dict[str, any]:
    """
    Checks for share dilution or consistent buybacks, and some dividend track record.
    A simplified approach:
      - if there's net share repurchase or stable share count, it suggests management
        might be shareholder-friendly.
      - if there's a big new issuance, it might be a negative sign (dilution).
    """
    if not financial_line_items:
        return {"score": 0, "max_score": 2, "details": "Insufficient data for management analysis"}

    reasoning = []
    mgmt_score = 0

    latest = financial_line_items[0]
    if hasattr(latest,
               "issuance_or_purchase_of_equity_shares") and latest.issuance_or_purchase_of_equity_shares and latest.issuance_or_purchase_of_equity_shares < 0:
        # Negative means the company spent money on buybacks
        mgmt_score += 1
        reasoning.append("Company has been repurchasing shares (shareholder-friendly)")

    if hasattr(latest,
               "issuance_or_purchase_of_equity_shares") and latest.issuance_or_purchase_of_equity_shares and latest.issuance_or_purchase_of_equity_shares > 0:
        # Positive issuance means new shares => possible dilution
        reasoning.append("Recent common stock issuance (potential dilution)")
    else:
        reasoning.append("No significant new stock issuance detected")

    # Check for any dividends
    if hasattr(latest,
               "dividends_and_other_cash_distributions") and latest.dividends_and_other_cash_distributions and latest.dividends_and_other_cash_distributions < 0:
        mgmt_score += 1
        reasoning.append("Company has a track record of paying dividends")
    else:
        reasoning.append("No or minimal dividends paid")

    return {
        "score": mgmt_score,
        "max_score": 2,
        "details": "; ".join(reasoning),
    }


def calculate_owner_earnings(financial_line_items: list) -> dict[str, any]:
    """
    Calculate owner earnings (Buffett's preferred measure of true earnings power).
    Enhanced methodology: Net Income + Depreciation/Amortization - Maintenance CapEx - Working Capital Changes
    Uses multi-period analysis for better maintenance capex estimation.
    """
    if not financial_line_items or len(financial_line_items) < 2:
        return {"owner_earnings": None, "details": ["Insufficient data for owner earnings calculation"]}

    latest = financial_line_items[0]
    details = []

    # Core components
    net_income = latest.net_income
    depreciation = latest.depreciation_and_amortization
    capex = latest.capital_expenditure

    if not all([net_income is not None, depreciation is not None, capex is not None]):
        missing = []
        if net_income is None: missing.append("net income")
        if depreciation is None: missing.append("depreciation")
        if capex is None: missing.append("capital expenditure")
        return {"owner_earnings": None, "details": [f"Missing components: {', '.join(missing)}"]}

    # Enhanced maintenance capex estimation using historical analysis
    maintenance_capex = estimate_maintenance_capex(financial_line_items)

    # Working capital change analysis (if data available)
    working_capital_change = 0
    if len(financial_line_items) >= 2:
        try:
            current_assets_current = getattr(latest, 'current_assets', None)
            current_liab_current = getattr(latest, 'current_liabilities', None)

            previous = financial_line_items[1]
            current_assets_previous = getattr(previous, 'current_assets', None)
            current_liab_previous = getattr(previous, 'current_liabilities', None)

            if all([current_assets_current, current_liab_current, current_assets_previous, current_liab_previous]):
                wc_current = current_assets_current - current_liab_current
                wc_previous = current_assets_previous - current_liab_previous
                working_capital_change = wc_current - wc_previous
                details.append(f"Working capital change: ${working_capital_change:,.0f}")
        except:
            pass  # Skip working capital adjustment if data unavailable

    # Calculate owner earnings
    owner_earnings = net_income + depreciation - maintenance_capex - working_capital_change

    # Sanity checks
    if owner_earnings < net_income * 0.3:  # Owner earnings shouldn't be less than 30% of net income typically
        details.append("Warning: Owner earnings significantly below net income - high capex intensity")

    if maintenance_capex > depreciation * 2:  # Maintenance capex shouldn't typically exceed 2x depreciation
        details.append("Warning: Estimated maintenance capex seems high relative to depreciation")

    details.extend([
        f"Net income: ${net_income:,.0f}",
        f"Depreciation: ${depreciation:,.0f}",
        f"Estimated maintenance capex: ${maintenance_capex:,.0f}",
        f"Owner earnings: ${owner_earnings:,.0f}"
    ])

    return {
        "owner_earnings": owner_earnings,
        "components": {
            "net_income": net_income,
            "depreciation": depreciation,
            "maintenance_capex": maintenance_capex,
            "working_capital_change": working_capital_change,
            "total_capex": abs(capex)
        },
        "details": details,
    }


def estimate_maintenance_capex(financial_line_items: list) -> float:
    """
    Estimate maintenance capital expenditure using historical data.
    Uses multi-year average of capex relative to depreciation and revenue.
    """
    if len(financial_line_items) < 3:
        # Fallback: use latest period's depreciation as proxy
        latest = financial_line_items[0]
        if hasattr(latest, 'depreciation_and_amortization') and latest.depreciation_and_amortization:
            return abs(latest.depreciation_and_amortization)
        return 0.0

    # Calculate historical capex-to-depreciation ratios
    capex_ratios = []
    for item in financial_line_items[:5]:  # Use last 5 periods if available
        if (item.capital_expenditure is not None and 
            item.depreciation_and_amortization is not None and 
            item.depreciation_and_amortization != 0):
            ratio = abs(item.capital_expenditure) / abs(item.depreciation_and_amortization)
            capex_ratios.append(ratio)

    if not capex_ratios:
        # Fallback to current depreciation
        latest = financial_line_items[0]
        return abs(latest.depreciation_and_amortization) if latest.depreciation_and_amortization else 0.0

    # Use median ratio to avoid outlier bias, apply to current depreciation
    capex_ratios.sort()
    median_ratio = capex_ratios[len(capex_ratios) // 2]
    
    # Cap the ratio to reasonable bounds (0.5x to 3x depreciation)
    median_ratio = max(0.5, min(3.0, median_ratio))
    
    latest = financial_line_items[0]
    current_depreciation = abs(latest.depreciation_and_amortization) if latest.depreciation_and_amortization else 0.0
    
    return current_depreciation * median_ratio


def analyze_pricing_power(financial_line_items: list, metrics: list) -> dict[str, any]:
    """Analyze pricing power through margin trends and revenue growth during inflationary periods."""
    if len(financial_line_items) < 3 or not metrics:
        return {"score": 0, "details": "Insufficient data for pricing power analysis"}

    score = 0
    reasoning = []

    # Check gross margin trends (pricing power indicator)
    gross_margins = []
    for item in financial_line_items[:5]:  # Last 5 periods
        if item.revenue and item.gross_profit:
            margin = item.gross_profit / item.revenue
            gross_margins.append(margin)

    if len(gross_margins) >= 3:
        # Check if margins are stable or improving
        recent_margin = sum(gross_margins[:2]) / 2  # Average of last 2 periods
        older_margin = sum(gross_margins[-2:]) / 2  # Average of oldest 2 periods
        
        if recent_margin >= older_margin and recent_margin > 0.3:  # Stable/improving and >30%
            score += 2
            reasoning.append(f"Strong pricing power: gross margin stable/improving at {recent_margin:.1%}")
        elif recent_margin >= older_margin:
            score += 1
            reasoning.append(f"Some pricing power: gross margin stable/improving at {recent_margin:.1%}")
        else:
            reasoning.append(f"Declining pricing power: gross margin falling from {older_margin:.1%} to {recent_margin:.1%}")

    # Check operating margin stability
    if metrics and len(metrics) >= 3:
        operating_margins = [m.operating_margin for m in metrics[:3] if m.operating_margin is not None]
        if len(operating_margins) >= 3:
            if all(margin > 0.15 for margin in operating_margins):  # Consistently high operating margins
                score += 1
                reasoning.append("Consistent high operating margins suggest strong pricing power")

    # Check revenue growth consistency (ability to raise prices)
    revenue_growth_rates = []
    for i in range(len(financial_line_items) - 1):
        current = financial_line_items[i]
        previous = financial_line_items[i + 1]
        if current.revenue and previous.revenue and previous.revenue != 0:
            growth_rate = (current.revenue - previous.revenue) / previous.revenue
            revenue_growth_rates.append(growth_rate)

    if len(revenue_growth_rates) >= 3:
        avg_growth = sum(revenue_growth_rates) / len(revenue_growth_rates)
        if avg_growth > 0.05:  # >5% average revenue growth
            score += 1
            reasoning.append(f"Strong revenue growth ({avg_growth:.1%} avg) suggests pricing power")
        elif avg_growth > 0:
            reasoning.append(f"Modest revenue growth ({avg_growth:.1%} avg)")
        else:
            score -= 1
            reasoning.append(f"Declining revenue ({avg_growth:.1%} avg) suggests weak pricing power")

    # Ensure score doesn't go negative
    score = max(0, score)

    return {
        "score": score,
        "details": "; ".join(reasoning) if reasoning else "Limited pricing power analysis",
    }


def analyze_book_value_growth(financial_line_items: list) -> dict[str, any]:
    """Analyze book value per share growth over time."""
    if len(financial_line_items) < 4:
        return {"score": 0, "details": "Insufficient data for book value analysis"}

    score = 0
    reasoning = []

    # Calculate book value growth (shareholders equity / shares outstanding)
    book_values = []
    for item in financial_line_items[:5]:  # Last 5 periods
        if item.shareholders_equity and item.outstanding_shares and item.outstanding_shares > 0:
            bv_per_share = item.shareholders_equity / item.outstanding_shares
            book_values.append(bv_per_share)

    if len(book_values) >= 4:
        # Check for consistent book value growth
        growth_periods = 0
        for i in range(len(book_values) - 1):
            if book_values[i] > book_values[i + 1]:
                growth_periods += 1

        growth_rate = growth_periods / (len(book_values) - 1)
        if growth_rate >= 0.75:  # 75%+ of periods showing growth
            score += 3
            total_growth = (book_values[0] - book_values[-1]) / book_values[-1] if book_values[-1] != 0 else 0
            reasoning.append(f"Excellent book value growth: {growth_periods}/{len(book_values)-1} periods positive (total: {total_growth:.1%})")
        elif growth_rate >= 0.5:
            score += 2
            reasoning.append(f"Good book value growth: {growth_periods}/{len(book_values)-1} periods positive")
        else:
            score += 1
            reasoning.append(f"Inconsistent book value growth: {growth_periods}/{len(book_values)-1} periods positive")
    else:
        reasoning.append("Insufficient data for book value per share analysis")

    return {
        "score": score,
        "details": "; ".join(reasoning),
    }


def calculate_intrinsic_value(financial_line_items: list) -> dict[str, any]:
    """Calculate intrinsic value using owner earnings and growth estimates."""
    owner_earnings_analysis = calculate_owner_earnings(financial_line_items)
    
    if not owner_earnings_analysis.get("owner_earnings"):
        return {
            "intrinsic_value": None,
            "details": "Cannot calculate intrinsic value without owner earnings",
        }

    owner_earnings = owner_earnings_analysis["owner_earnings"]
    
    # Simple perpetuity model with conservative assumptions
    # IV = Owner Earnings / (Discount Rate - Growth Rate)
    discount_rate = 0.10  # 10% required return (Buffett typically uses 10-15%)
    growth_rate = 0.03   # Conservative 3% long-term growth
    
    # Safety check - growth rate must be less than discount rate
    if growth_rate >= discount_rate:
        growth_rate = discount_rate - 0.01
    
    intrinsic_value = owner_earnings / (discount_rate - growth_rate)
    
    # Apply additional conservatism - reduce by 25% for margin of safety
    conservative_intrinsic_value = intrinsic_value * 0.75
    
    return {
        "intrinsic_value": conservative_intrinsic_value,
        "base_calculation": intrinsic_value,
        "owner_earnings": owner_earnings,
        "assumptions": {
            "discount_rate": discount_rate,
            "growth_rate": growth_rate,
            "conservatism_factor": 0.75
        },
        "details": f"Intrinsic value: ${conservative_intrinsic_value:,.0f} (base: ${intrinsic_value:,.0f}) using {discount_rate:.1%} discount rate, {growth_rate:.1%} growth",
    }


def generate_buffett_output(
    ticker: str,
    analysis_data: dict,
    state: AgentState,
    agent_id: str,
) -> WarrenBuffettSignal:
    """Generate final Buffett analysis using LLM with all the quantitative analysis."""
    
    template = ChatPromptTemplate.from_messages([
        ("system", 
         "You are Warren Buffett analyzing a stock investment opportunity. "
         "You have been provided with comprehensive fundamental analysis data. "
         "Make your final investment decision based on your value investing principles: "
         "look for companies with strong moats, excellent management, consistent earnings, "
         "reasonable valuation, and businesses you understand. "
         "Consider the margin of safety principle - only invest when the price is "
         "significantly below intrinsic value."),
        ("human",
         "Analyze this investment opportunity for {ticker}:\n\n"
         "FUNDAMENTAL ANALYSIS:\n{fundamental_analysis}\n\n"
         "CONSISTENCY ANALYSIS:\n{consistency_analysis}\n\n"
         "COMPETITIVE MOAT ANALYSIS:\n{moat_analysis}\n\n"
         "MANAGEMENT QUALITY:\n{management_analysis}\n\n"
         "PRICING POWER:\n{pricing_power_analysis}\n\n"
         "BOOK VALUE GROWTH:\n{book_value_analysis}\n\n"
         "INTRINSIC VALUE:\n{intrinsic_value_analysis}\n\n"
         "MARKET CAP: ${market_cap:,}\n"
         "MARGIN OF SAFETY: {margin_of_safety}\n\n"
         "QUANTITATIVE SCORE: {score}/{max_score}\n\n"
         "Provide your investment signal (bullish/bearish/neutral), "
         "confidence level (0-100), and concise reasoning focusing on "
         "the most important Buffett-style factors.")
    ])
    
    # Format margin of safety for display
    margin_of_safety_str = f"{analysis_data['margin_of_safety']:.1%}" if analysis_data['margin_of_safety'] is not None else "Cannot calculate (missing market cap or intrinsic value)"
    
    prompt = template.invoke({
        "ticker": ticker,
        "fundamental_analysis": analysis_data["fundamental_analysis"]["details"],
        "consistency_analysis": analysis_data["consistency_analysis"]["details"],
        "moat_analysis": analysis_data["moat_analysis"]["details"],
        "management_analysis": analysis_data["management_analysis"]["details"],
        "pricing_power_analysis": analysis_data["pricing_power_analysis"]["details"],
        "book_value_analysis": analysis_data["book_value_analysis"]["details"],
        "intrinsic_value_analysis": analysis_data["intrinsic_value_analysis"]["details"],
        "market_cap": analysis_data["market_cap"] or 0,
        "margin_of_safety": margin_of_safety_str,
        "score": analysis_data["score"],
        "max_score": analysis_data["max_score"]
    })
    
    def default_factory():
        return WarrenBuffettSignal(
            signal="neutral",
            confidence=50,
            reasoning="Unable to generate analysis - using neutral default"
        )
    
    return call_llm(
        prompt=prompt,
        pydantic_model=WarrenBuffettSignal,
        agent_name=agent_id,
        state=state,
        default_factory=default_factory
    )