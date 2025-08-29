from src.data.models import FinancialMetrics, LineItem
from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import json
from typing_extensions import Literal
from src.tools.api import get_financial_metrics, get_market_cap, search_line_items
from src.utils.llm import call_llm
from src.utils.progress import progress
from src.utils.api_key import get_api_key_from_state

class DonaldTrumpSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def donald_trump_agent(state: AgentState, agent_id: str = "donald_trump_agent"):
    """Analyzes stocks using Trump's principles and LLM reasoning."""
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    # Collect all analysis for LLM reasoning
    analysis_data = {}
    trump_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        # Fetch required data - request more periods for better trend analysis
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=2, api_key=api_key)

        progress.update_status(agent_id, ticker, "Gathering financial line items")
        financial_line_items = search_line_items(
            ticker,
            [
                "free_cash_flow",
                "revenue",
                "gross_margin",
                "total_debt",
                "debt_to_equity",
                "capital_expenditure",
                "research_and_development",
                "outstanding_shares",
                "dividends_and_other_cash_distributions",
            ],
            end_date,
            period="ttm",
            limit=10,
            api_key=api_key,
        )

        progress.update_status(agent_id, ticker, "Getting market cap")
        # Get current market cap
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)

        progress.update_status(agent_id, ticker, "Analyzing policy")

        policy_analysis = analyze_policy(financial_line_items, metrics)

        progress.update_status(agent_id, ticker, "Analyzing debt leverage")
        debt_leverage_analysis = analyze_debt_leverage(financial_line_items, metrics)

        progress.update_status(agent_id, ticker, "Analyzing market sentiment")
        market_sentiment_analysis = analyze_market_sentiment(market_cap, financial_line_items, metrics)

        progress.update_status(agent_id, ticker, "Analyzing macro hedging")
        macro_hedging_analysis = analyze_macro_hedging(financial_line_items, metrics)

        progress.update_status(agent_id, ticker, "Calculating intrinsic value")
        intrinsic_value_analysis = calculate_intrinsic_value(financial_line_items, metrics)

        # Calculate total score without circle of competence (LLM will handle that)
        total_score = (
            policy_analysis["score"] + 
            debt_leverage_analysis["score"] + 
            market_sentiment_analysis["score"] + 
            macro_hedging_analysis["score"]
        )
        
        # Update max possible score calculation
        max_possible_score = (
            10 +  # fundamental_analysis (ROE, debt, margins, current ratio)
            12 + 
            13 +
            13     # book_value_growth (0-5)
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
            "policy_analysis": policy_analysis,
            "debt_leverage_analysis": debt_leverage_analysis,
            "market_sentiment_analysis": market_sentiment_analysis,
            "macro_hedging_analysis": macro_hedging_analysis,
            "intrinsic_value_analysis": intrinsic_value_analysis,
            "market_cap": market_cap,
            "margin_of_safety": margin_of_safety,
        }

        progress.update_status(agent_id, ticker, "Generating Warren Trump analysis")
        trump_output = generate_trump_output(
            ticker=ticker,
            analysis_data=analysis_data,
            state=state,
            agent_id=agent_id,
        )

        # Store analysis in consistent format with other agents
        trump_analysis[ticker] = {
            "signal": trump_output.signal,
            "confidence": trump_output.confidence,
            "reasoning": trump_output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=trump_output.reasoning)

    # Create the message
    message = HumanMessage(content=json.dumps(trump_analysis), name=agent_id)

    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(trump_analysis, agent_id)

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"][agent_id] = trump_analysis

    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}

def analyze_policy(financial_line_items: list, metrics: list) -> dict[str, any]:
    """
    Analyze policy arbitrage opportunities based on Trump's operation model.
    Focuses on free cash flow, revenue, gross margin and other policy-sensitive metrics
    to identify companies vulnerable to policy shocks (tariffs, subsidies, etc.).
    """
    score = 0
    details = []
    
    if not metrics or not financial_line_items:
        return {
            "score": 0,
            "details": "Insufficient data to analyze policy arbitrage opportunities"
        }
    
    # Get the latest metrics
    latest_metrics = metrics[0]
    
    # 1. Free Cash Flow analysis (policy sensitivity)
    fcf_vals = [item.free_cash_flow for item in financial_line_items if item.free_cash_flow is not None]
    if fcf_vals:
        # Use the latest FCF value
        latest_fcf = fcf_vals[-1] if fcf_vals else 0
        
        # Check if FCF is negative or declining (vulnerable to policy shocks)
        if latest_fcf < 0:
            score += 2
            details.append(f"Negative free cash flow (${latest_fcf:,.0f}), highly vulnerable to policy shocks.")
        elif len(fcf_vals) >= 2 and fcf_vals[-1] < fcf_vals[-2]:
            score += 1
            details.append(f"Declining free cash flow (${fcf_vals[-2]:,.0f} → ${fcf_vals[-1]:,.0f}), policy-sensitive.")
        else:
            details.append(f"Stable free cash flow (${latest_fcf:,.0f}), moderate policy sensitivity.")
    else:
        details.append("No free cash flow data available.")
    
    # 2. Free Cash Flow Yield analysis (from metrics)
    if latest_metrics.free_cash_flow_yield is not None:
        if latest_metrics.free_cash_flow_yield < 0.03:  # Less than 3% yield
            score += 2
            details.append(f"Low FCF yield ({latest_metrics.free_cash_flow_yield:.2%}), prime target for policy arbitrage.")
        else:
            details.append(f"Reasonable FCF yield ({latest_metrics.free_cash_flow_yield:.2%}).")
    else:
        details.append("No FCF yield data available.")
    
    # 3. Revenue analysis for trade dependency
    revenues = [item.revenue for item in financial_line_items if item.revenue is not None]
    if revenues:
        latest_revenue = revenues[-1]
        
        # Check revenue growth (declining revenue is more policy-sensitive)
        if len(revenues) >= 2:
            growth = (revenues[-1] - revenues[-2]) / abs(revenues[-2]) if revenues[-2] != 0 else 0
            if growth < -0.1:  # More than 10% decline
                score += 2
                details.append(f"Revenue declining ({growth:.1%}), highly sensitive to trade policies.")
            elif growth < 0:
                score += 1
                details.append(f"Revenue slightly declining ({growth:.1%}), policy-sensitive.")
            else:
                details.append(f"Revenue growing ({growth:.1%}), less policy-sensitive.")
    else:
        details.append("No revenue data available.")
    
    # 4. Price to Sales ratio analysis (policy protection potential)
    if latest_metrics.price_to_sales_ratio is not None:
        if latest_metrics.price_to_sales_ratio < 1.5:  # Low P/S ratio
            score += 1
            details.append(f"Low P/S ratio ({latest_metrics.price_to_sales_ratio:.2f}), potential beneficiary of 'Buy American' policies.")
        else:
            details.append(f"P/S ratio ({latest_metrics.price_to_sales_ratio:.2f}) not particularly attractive for policy plays.")
    else:
        details.append("No P/S ratio data available.")
    
    # 5. Free Cash Flow per Share analysis (for market manipulation potential)
    if latest_metrics.free_cash_flow_per_share is not None:
        if latest_metrics.free_cash_flow_per_share < 0:
            score += 1
            details.append(f"Negative FCF per share (${latest_metrics.free_cash_flow_per_share:.2f}), susceptible to negative sentiment campaigns.")
        else:
            details.append(f"Positive FCF per share (${latest_metrics.free_cash_flow_per_share:.2f}).")
    else:
        details.append("No FCF per share data available.")
    
    # Determine overall policy arbitrage opportunity
    opportunity_level = "Low"
    if score >= 8:
        opportunity_level = "Very High"
    elif score >= 6:
        opportunity_level = "High"
    elif score >= 4:
        opportunity_level = "Medium"
    
    details.insert(0, f"Policy arbitrage opportunity: {opportunity_level} (Score: {score}/10)")
    
    return {
        "score": score,
        "details": "; ".join(details)
    }

def analyze_debt_leverage(financial_line_items: list, metrics: list) -> dict[str, any]:
    """
    Analyze debt leverage crisis opportunities based on Trump's operation model.
    Focuses on high debt levels, weak interest coverage, and poor liquidity ratios
    to identify companies vulnerable to interest rate shocks and debt crises.
    """
    score = 0
    details = []
    
    if not metrics or not financial_line_items:
        return {
            "score": 0,
            "details": "Insufficient data to analyze debt leverage crisis opportunities"
        }
    
    # Get the latest metrics
    latest_metrics = metrics[0]
    
    # 1. Total Debt analysis (absolute debt level)
    total_debts = [item.total_debt for item in financial_line_items if item.total_debt is not None]
    if total_debts:
        latest_debt = total_debts[-1]
        
        # Compare debt to equity to assess relative leverage
        if hasattr(financial_line_items[-1], 'shareholders_equity') and financial_line_items[-1].shareholders_equity:
            debt_to_equity = latest_debt / financial_line_items[-1].shareholders_equity
            if debt_to_equity > 0.8:  # More than 80% debt-to-equity
                score += 3
                details.append(f"Extremely high debt-to-equity ratio ({debt_to_equity:.1%}), prime target for debt crisis.")
            elif debt_to_equity > 0.5:
                score += 2
                details.append(f"High debt-to-equity ratio ({debt_to_equity:.1%}), vulnerable to rate hikes.")
            else:
                details.append(f"Moderate debt-to-equity ratio ({debt_to_equity:.1%}).")
        else:
            details.append(f"Total debt: ${latest_debt:,.0f}, but no equity data for ratio calculation.")
    else:
        details.append("No total debt data available.")
    
    # 2. Debt-to-Equity ratio analysis (from metrics if available)
    if latest_metrics.debt_to_equity is not None:
        if latest_metrics.debt_to_equity > 0.8:  # More than 80%
            score += 2
            details.append(f"Confirmed high debt-to-equity ratio ({latest_metrics.debt_to_equity:.1%}), crisis potential.")
        elif latest_metrics.debt_to_equity > 0.5:
            score += 1
            details.append(f"Elevated debt-to-equity ratio ({latest_metrics.debt_to_equity:.1%}).")
        else:
            details.append(f"Manageable debt-to-equity ratio ({latest_metrics.debt_to_equity:.1%}).")
    else:
        details.append("No debt-to-equity ratio data available.")
    
    # 3. Interest Coverage ratio analysis (ability to service debt)
    if latest_metrics.interest_coverage is not None:
        if latest_metrics.interest_coverage < 1.5:  # Less than 1.5x coverage
            score += 3
            details.append(f"Dangerously low interest coverage ({latest_metrics.interest_coverage:.1f}x), high default risk.")
        elif latest_metrics.interest_coverage < 2.5:
            score += 2
            details.append(f"Low interest coverage ({latest_metrics.interest_coverage:.1f}x), vulnerable to rate increases.")
        elif latest_metrics.interest_coverage < 4:
            score += 1
            details.append(f"Moderate interest coverage ({latest_metrics.interest_coverage:.1f}x).")
        else:
            details.append(f"Strong interest coverage ({latest_metrics.interest_coverage:.1f}x).")
    else:
        details.append("No interest coverage data available.")
    
    # 4. Quick Ratio analysis (short-term liquidity)
    if latest_metrics.quick_ratio is not None:
        if latest_metrics.quick_ratio < 0.8:  # Less than 0.8
            score += 2
            details.append(f"Poor quick ratio ({latest_metrics.quick_ratio:.2f}), liquidity crisis potential.")
        elif latest_metrics.quick_ratio < 1.0:
            score += 1
            details.append(f"Low quick ratio ({latest_metrics.quick_ratio:.2f}), limited liquidity buffer.")
        else:
            details.append(f"Adequate quick ratio ({latest_metrics.quick_ratio:.2f}).")
    else:
        details.append("No quick ratio data available.")
    
    # 5. Debt trend analysis (increasing leverage)
    if len(total_debts) >= 2:
        debt_growth = (total_debts[-1] - total_debts[-2]) / abs(total_debts[-2]) if total_debts[-2] != 0 else 0
        if debt_growth > 0.2:  # More than 20% increase
            score += 2
            details.append(f"Rapid debt growth ({debt_growth:.1%}), accelerating leverage risk.")
        elif debt_growth > 0.05:
            score += 1
            details.append(f"Moderate debt growth ({debt_growth:.1%}).")
        else:
            details.append(f"Stable or declining debt levels ({debt_growth:.1%}).")
    
    # Determine overall debt crisis opportunity
    opportunity_level = "Low"
    if score >= 8:
        opportunity_level = "Very High"
    elif score >= 6:
        opportunity_level = "High"
    elif score >= 4:
        opportunity_level = "Medium"
    
    details.insert(0, f"Debt leverage crisis opportunity: {opportunity_level} (Score: {score}/12)")
    
    return {
        "score": score,
        "details": "; ".join(details)
    }

def analyze_market_sentiment(market_cap: float, financial_line_items: list, metrics: list) -> dict[str, any]:
    """
    Analyze market sentiment manipulation opportunities based on Trump's social media-driven model.
    Focuses on share structure, earnings growth, valuation ratios, and dividend patterns
    to identify companies vulnerable to sentiment-driven price swings.
    """
    score = 0
    details = []
    
    if not metrics or not financial_line_items:
        return {
            "score": 0,
            "details": "Insufficient data to analyze market sentiment manipulation opportunities"
        }
    
    # Get the latest metrics
    latest_metrics = metrics[0]
    
    # 1. Outstanding Shares analysis (market manipulation potential)
    outstanding_shares = [item.outstanding_shares for item in financial_line_items if item.outstanding_shares is not None]
    if outstanding_shares:
        latest_shares = outstanding_shares[-1]
        
        # Check share count relative to market cap
        if latest_metrics.market_cap and latest_shares:
            share_price = latest_metrics.market_cap / latest_shares
            if share_price < 10:  # Low-priced stocks are easier to manipulate
                score += 3
                details.append(f"Low share price (${share_price:.2f}), highly susceptible to sentiment manipulation.")
            elif share_price < 25:
                score += 2
                details.append(f"Moderate share price (${share_price:.2f}), manipulable with targeted campaigns.")
            else:
                details.append(f"Higher share price (${share_price:.2f}), requires significant capital to move.")
    else:
        details.append("No outstanding shares data available.")
    
    # 2. EPS Growth analysis (expectation gap creation)
    if latest_metrics.earnings_per_share_growth is not None:
        if latest_metrics.earnings_per_share_growth < -0.2:  # More than 20% decline
            score += 3
            details.append(f"Severe EPS decline ({latest_metrics.earnings_per_share_growth:.1%}), prime for negative sentiment campaigns.")
        elif latest_metrics.earnings_per_share_growth < 0:
            score += 2
            details.append(f"EPS decline ({latest_metrics.earnings_per_share_growth:.1%}), vulnerable to bearish narratives.")
        elif latest_metrics.earnings_per_share_growth > 0.5:
            score += 1
            details.append(f"High EPS growth ({latest_metrics.earnings_per_share_growth:.1%}), potential for hype-driven rallies.")
        else:
            details.append(f"Moderate EPS growth ({latest_metrics.earnings_per_share_growth:.1%}).")
    else:
        details.append("No EPS growth data available.")
    
    # 3. PEG Ratio analysis (growth narrative manipulation)
    if latest_metrics.peg_ratio is not None:
        if latest_metrics.peg_ratio < 0.5:  # Extremely low PEG
            score += 2
            details.append(f"Very low PEG ratio ({latest_metrics.peg_ratio:.2f}), can be hyped as 'undervalued growth' opportunity.")
        elif latest_metrics.peg_ratio < 1.0:
            score += 1
            details.append(f"Low PEG ratio ({latest_metrics.peg_ratio:.2f}), potential for growth narrative manipulation.")
        elif latest_metrics.peg_ratio > 2.0:
            score += 1
            details.append(f"High PEG ratio ({latest_metrics.peg_ratio:.2f}), vulnerable to 'overvalued' criticism.")
        else:
            details.append(f"Reasonable PEG ratio ({latest_metrics.peg_ratio:.2f}).")
    else:
        details.append("No PEG ratio data available.")
    
    # 4. Dividend analysis (sentiment manipulation tool)
    dividend_vals = [item.dividends_and_other_cash_distributions for item in financial_line_items if item.dividends_and_other_cash_distributions is not None]
    if dividend_vals:
        latest_dividend = dividend_vals[-1]
        
        # Check dividend trend
        if len(dividend_vals) >= 2:
            dividend_change = (dividend_vals[-1] - dividend_vals[-2]) / abs(dividend_vals[-2]) if dividend_vals[-2] != 0 else 0
            if dividend_change > 0.5:  # More than 50% increase
                score += 2
                details.append(f"Significant dividend increase ({dividend_change:.1%}), can be used to create 'shareholder-friendly' narrative.")
            elif dividend_change < -0.3:  # More than 30% decrease
                score += 2
                details.append(f"Major dividend cut ({dividend_change:.1%}), vulnerable to negative sentiment attacks.")
            elif dividend_change > 0:
                score += 1
                details.append(f"Moderate dividend increase ({dividend_change:.1%}), potential for positive sentiment creation.")
        
        # Check dividend yield
        if hasattr(financial_line_items[-1], 'revenue') and financial_line_items[-1].revenue and latest_metrics.market_cap:
            dividend_yield = latest_dividend / latest_metrics.market_cap
            if dividend_yield > 0.05:  # High dividend yield
                score += 1
                details.append(f"High dividend yield ({dividend_yield:.2%}), useful for attracting retail investors.")
    else:
        details.append("No dividend data available.")
    
    # 5. Short interest analysis (from external data, simulated here)
    # Trump often targets high short interest stocks for "short squeeze" campaigns
    # We'll simulate this by looking at recent price volatility
    if len(financial_line_items) >= 3:
        prices = [market_cap / item.outstanding_shares for item in financial_line_items if item.outstanding_shares]
        if len(prices) >= 3:
            volatility = (max(prices[-3:]) - min(prices[-3:])) / min(prices[-3:])
            if volatility > 0.3:  # More than 30% volatility
                score += 2
                details.append(f"High recent volatility ({volatility:.1%}), indicates potential for short squeeze campaigns.")
    
    # Determine overall sentiment manipulation opportunity
    opportunity_level = "Low"
    if score >= 8:
        opportunity_level = "Very High"
    elif score >= 6:
        opportunity_level = "High"
    elif score >= 4:
        opportunity_level = "Medium"
    
    details.insert(0, f"Market sentiment manipulation opportunity: {opportunity_level} (Score: {score}/12)")
    
    return {
        "score": score,
        "details": "; ".join(details)
    }
  
def analyze_macro_hedging(financial_line_items: list, metrics: list) -> dict[str, any]:
    """
    Analyze macro hedging opportunities based on Trump's policy cycle arbitrage model.
    Focuses on growth metrics, valuation multiples, and capital investment patterns
    to identify companies sensitive to policy shifts (tariffs, sanctions, subsidies).
    """
    score = 0
    details = []
    
    if not metrics or not financial_line_items:
        return {
            "score": 0,
            "details": "Insufficient data to analyze macro hedging opportunities"
        }
    
    # Get the latest metrics
    latest_metrics = metrics[0]
    
    # 1. Revenue Growth analysis (policy sensitivity)
    if latest_metrics.revenue_growth is not None:
        if latest_metrics.revenue_growth < -0.1:  # More than 10% decline
            score += 3
            details.append(f"Significant revenue decline ({latest_metrics.revenue_growth:.1%}), highly sensitive to trade policies.")
        elif latest_metrics.revenue_growth < 0:
            score += 2
            details.append(f"Revenue decline ({latest_metrics.revenue_growth:.1%}), policy-sensitive.")
        elif latest_metrics.revenue_growth > 0.2:
            score += 1
            details.append(f"Strong revenue growth ({latest_metrics.revenue_growth:.1%}), potential policy beneficiary.")
        else:
            details.append(f"Moderate revenue growth ({latest_metrics.revenue_growth:.1%}).")
    else:
        details.append("No revenue growth data available.")
    
    # 2. EBITDA Growth analysis (operational efficiency sensitivity)
    if latest_metrics.ebitda_growth is not None:
        if latest_metrics.ebitda_growth < -0.15:  # More than 15% decline
            score += 3
            details.append(f"Severe EBITDA decline ({latest_metrics.ebitda_growth:.1%}), highly vulnerable to policy shocks.")
        elif latest_metrics.ebitda_growth < 0:
            score += 2
            details.append(f"EBITDA decline ({latest_metrics.ebitda_growth:.1%}), sensitive to operational disruptions.")
        elif latest_metrics.ebitda_growth > 0.25:
            score += 1
            details.append(f"Strong EBITDA growth ({latest_metrics.ebitda_growth:.1%}), potential policy winner.")
        else:
            details.append(f"Moderate EBITDA growth ({latest_metrics.ebitda_growth:.1%}).")
    else:
        details.append("No EBITDA growth data available.")
    
    # 3. EV/EBITDA analysis (valuation distortion opportunities)
    if latest_metrics.enterprise_value_to_ebitda_ratio is not None:
        if latest_metrics.enterprise_value_to_ebitda_ratio < 5:  # Low valuation
            score += 2
            details.append(f"Low EV/EBITDA ({latest_metrics.enterprise_value_to_ebitda_ratio:.1f}x), potential beneficiary of policy support.")
        elif latest_metrics.enterprise_value_to_ebitda_ratio > 15:  # High valuation
            score += 1
            details.append(f"High EV/EBITDA ({latest_metrics.enterprise_value_to_ebitda_ratio:.1f}x), vulnerable to policy headwinds.")
        else:
            details.append(f"Reasonable EV/EBITDA ({latest_metrics.enterprise_value_to_ebitda_ratio:.1f}x).")
    else:
        details.append("No EV/EBITDA data available.")
    
    # 4. Capital Expenditure analysis (investment sensitivity)
    capex_vals = [item.capital_expenditure for item in financial_line_items if item.capital_expenditure is not None]
    if capex_vals:
        # Check capex trend
        if len(capex_vals) >= 2:
            capex_change = (capex_vals[-1] - capex_vals[-2]) / abs(capex_vals[-2]) if capex_vals[-2] != 0 else 0
            if capex_change < -0.2:  # More than 20% decline
                score += 2
                details.append(f"Significant capex cut ({capex_change:.1%}), vulnerable to policy uncertainty.")
            elif capex_change < 0:
                score += 1
                details.append(f"Moderate capex cut ({capex_change:.1%}), policy-sensitive.")
            else:
                details.append(f"Stable or growing capex ({capex_change:.1%}).")
        else:
            details.append("Insufficient capex data for trend analysis.")
    else:
        details.append("No capital expenditure data available.")
    
    # 5. Research & Development analysis (innovation sensitivity)
    rnd_vals = [item.research_and_development for item in financial_line_items if item.research_and_development is not None]
    if rnd_vals:
        # Check R&D trend
        if len(rnd_vals) >= 2:
            rnd_change = (rnd_vals[-1] - rnd_vals[-2]) / abs(rnd_vals[-2]) if rnd_vals[-2] != 0 else 0
            if rnd_change < -0.15:  # More than 15% decline
                score += 2
                details.append(f"Significant R&D cut ({rnd_change:.1%}), vulnerable to technology sanctions.")
            elif rnd_change < 0:
                score += 1
                details.append(f"Moderate R&D cut ({rnd_change:.1%}), sensitive to innovation policies.")
            else:
                details.append(f"Stable or growing R&D ({rnd_change:.1%}).")
        
        # Check R&D intensity
        if hasattr(financial_line_items[-1], 'revenue') and financial_line_items[-1].revenue:
            rnd_intensity = rnd_vals[-1] / financial_line_items[-1].revenue
            if rnd_intensity > 0.15:  # High R&D intensity
                score += 1
                details.append(f"High R&D intensity ({rnd_intensity:.1%}), prime target for technology policy impacts.")
            elif rnd_intensity > 0.1:
                details.append(f"Moderate R&D intensity ({rnd_intensity:.1%}).")
            else:
                details.append(f"Low R&D intensity ({rnd_intensity:.1%}).")
        else:
            details.append("R&D data available but insufficient revenue for intensity analysis.")
    else:
        details.append("No R&D data available.")
    
    # 6. Policy cycle positioning (summary)
    if score >= 8:
        details.append("Strong alignment with policy cycle opportunities.")
    elif score >= 5:
        details.append("Moderate alignment with policy cycle opportunities.")
    else:
        details.append("Limited alignment with current policy cycle opportunities.")
    
    # Determine overall macro hedging opportunity
    opportunity_level = "Low"
    if score >= 10:
        opportunity_level = "Very High"
    elif score >= 7:
        opportunity_level = "High"
    elif score >= 5:
        opportunity_level = "Medium"
    
    details.insert(0, f"Macro hedging opportunity: {opportunity_level} (Score: {score}/12)")
    
    return {
        "score": score,
        "details": "; ".join(details)
    }

def calculate_intrinsic_value(financial_line_items: list, metrics: list) -> dict[str, any]:
    """
    Trump-style intrinsic value calculation based on policy arbitrage and market sentiment factors.
    Uses only the specified financial line items and metrics from our previous discussions.
    """
    # Check for sufficient data
    if not financial_line_items or not metrics:
        return {
            "trump_intrinsic_value": None,
            "details": "Insufficient data for Trump-style intrinsic value calculation"
        }
    
    latest_line_item = financial_line_items[0]
    latest_metric = metrics[0]
    
    # 1. Base Valuation Components
    base_value = _calculate_base_value(latest_line_item, latest_metric)
    
    # 2. Policy Sensitivity Score (0-100)
    policy_score = _calculate_policy_sensitivity(latest_line_item, latest_metric)
    
    # 3. Market Sentiment Score (0-100)
    sentiment_score = _calculate_sentiment_score(latest_line_item, latest_metric)
    
    # 4. Debt Risk Discount (0-30%)
    debt_discount = _calculate_debt_risk_discount(latest_line_item, latest_metric)
    
    # 5. Trump Intrinsic Value Calculation
    #    = Base Value × (1 + Policy Score/100) × (1 + Sentiment Score/100) × (1 - Debt Discount)
    trump_value = base_value * (1 + policy_score/100) * (1 + sentiment_score/100) * (1 - debt_discount)
    
    # Prepare detailed report
    details = [
        f"Base value: ${base_value:,.0f}",
        f"Policy sensitivity score: {policy_score}/100",
        f"Market sentiment score: {sentiment_score}/100",
        f"Debt risk discount: {debt_discount:.1%}",
        f"Trump intrinsic value: ${trump_value:,.0f}"
    ]
    
    return {
        "base_value": base_value,
        "policy_sensitivity_score": policy_score,
        "market_sentiment_score": sentiment_score,
        "debt_risk_discount": debt_discount,
        "intrinsic_value": trump_value,
        "details": "; ".join(details)
    }


def _calculate_base_value(line_item, metric) -> float:
    """Calculate base value using free cash flow and P/S ratio"""
    # Use free cash flow if available
    if line_item.free_cash_flow is not None:
        fcf = line_item.free_cash_flow
    else:
        # Fallback: use operating cash flow minus capital expenditure
        op_cash_flow = getattr(line_item, 'operating_cash_flow', 0) or 0
        capex = abs(getattr(line_item, 'capital_expenditure', 0)) or 0
        fcf = op_cash_flow - capex
    
    # Apply P/S ratio multiplier if available
    if metric.price_to_sales_ratio and line_item.revenue:
        base_value = fcf * metric.price_to_sales_ratio
    else:
        # Conservative fallback: 15x FCF
        base_value = fcf * 15
    
    return base_value


def _calculate_policy_sensitivity(line_item, metric) -> float:
    """Calculate policy sensitivity score (0-100)"""
    score = 0
    
    # 1. Revenue growth volatility (high growth or decline indicates sensitivity)
    if metric.revenue_growth:
        # Absolute value of growth rate (high = more sensitive)
        score += min(abs(metric.revenue_growth) * 200, 30)  # Max 30 points
    
    # 2. Gross margin vulnerability
    if line_item.gross_margin:
        # Lower margins = more vulnerable to input cost increases
        if line_item.gross_margin < 0.3:
            score += (0.3 - line_item.gross_margin) * 100  # Max 30 points
    
    # 3. EBITDA growth volatility
    if metric.ebitda_growth:
        # Absolute value of growth rate
        score += min(abs(metric.ebitda_growth) * 150, 20)  # Max 20 points
    
    # 4. Capital expenditure intensity
    if line_item.capital_expenditure and line_item.revenue:
        capex_intensity = abs(line_item.capital_expenditure) / line_item.revenue
        score += min(capex_intensity * 200, 20)  # Max 20 points
    
    return min(score, 100)  # Cap at 100


def _calculate_sentiment_score(line_item, metric) -> float:
    """Calculate market sentiment score (0-100)"""
    score = 0
    
    # 1. EPS growth potential (for hype)
    if metric.earnings_per_share_growth:
        # High growth = more hype potential
        if metric.earnings_per_share_growth > 0.15:
            score += min((metric.earnings_per_share_growth - 0.15) * 200, 30)  # Max 30 points
    
    # 2. PEG ratio (undervalued growth potential)
    if metric.peg_ratio:
        if metric.peg_ratio < 0.7:  # Low PEG = undervalued growth
            score += min((0.7 - metric.peg_ratio) * 100, 20)  # Max 20 points
    
    # 3. Dividend payments (attract retail investors)
    if line_item.dividends_and_other_cash_distributions:
        # Dividend payments increase sentiment
        score += 10
    
    # 4. Share structure (low float = easier to manipulate)
    if line_item.outstanding_shares and metric.market_cap:
        share_price = metric.market_cap / line_item.outstanding_shares
        if share_price < 15:  # Low price stocks easier to move
            score += 15
    
    return min(score, 100)  # Cap at 100


def _calculate_debt_risk_discount(line_item, metric) -> float:
    """Calculate debt risk discount (0-30%)"""
    discount = 0.0
    
    # 1. Debt-to-equity ratio
    if line_item.debt_to_equity:
        if line_item.debt_to_equity > 1.0:  # Debt > equity
            discount += 0.10
        elif line_item.debt_to_equity > 0.8:
            discount += 0.05
    
    # 2. Interest coverage
    if metric.interest_coverage:
        if metric.interest_coverage < 1.5:  # Coverage < 1.5x
            discount += 0.15
        elif metric.interest_coverage < 3.0:
            discount += 0.05
    
    # 3. Quick ratio (liquidity risk)
    if metric.quick_ratio:
        if metric.quick_ratio < 0.8:
            discount += 0.05
    
    return min(discount, 0.30)  # Max 30% discount

def generate_trump_output(
    ticker: str,
    analysis_data: dict[str, any],
    state: AgentState,
    agent_id: str = "donald_trump_agent",
) -> DonaldTrumpSignal:
    """Get investment decision from LLM with Trump's principles"""
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are Donald J. Trump, the 45th President of the United States and a world-class dealmaker. Analyze investment opportunities using my proven methodology developed over decades of building a tremendous business empire:

                MY CORE INVESTMENT PRINCIPLES:
                1. WINNING IS EVERYTHING: "I only win. I win at everything." Look for companies that are winners, not losers.
                2. BRAND POWER: "The most important thing is the brand." Companies with strong brands are worth billions.
                3. REAL ESTATE VALUE: "I love real estate. It's tangible, it's real." Value companies with significant real estate holdings.
                4. MEDIA PRESENCE: "The show is Trump, and it is sold-out performances everywhere." Media coverage is worth its weight in gold.
                5. POLICY IMPACT: "I know how to make deals with governments." Companies benefiting from tax cuts and subsidies are winners.
                6. AMERICA FIRST: "We will follow two simple rules: Buy American and Hire American." Companies making products in America deserve a premium.
                7. EXECUTIVE POWER: "I alone can fix it." Strong leadership is crucial - weak executives ruin companies.
                8. DEALMAKING: "Deals are my art form." Look for companies with restructuring potential and non-core assets to unlock value.
                9. RISK AVERSION: "I hate losers." Avoid companies with litigation risks, tariff exposures, or financial distress.

                MY INVESTMENT PREFERENCES:
                STRONGLY PREFER:
                - Real estate developers and REITs
                - Media and entertainment companies
                - Luxury brands and consumer goods
                - Companies with government contracts and subsidies
                - Businesses with iconic American brands
                - Companies with strong social media presence
                - Firms with powerful executives (like me)

                GENERALLY AVOID:
                - Foreign companies (especially China)
                - Weak brands and "loser" companies
                - Businesses with high tariff exposure
                - Companies with litigation problems
                - Complex tech without tangible assets
                - Environmental and "woke" companies
                - Businesses with weak leadership

                MY INVESTMENT CRITERIA HIERARCHY:
                First: Brand Power and Media Presence - Is this a famous, well-known company?
                Second: Real Estate Value - Does it have valuable properties?
                Third: Policy Benefits - Is it getting tax breaks or subsidies?
                Fourth: Executive Strength - Does it have a strong leader?
                Fifth: American Manufacturing - Is it making products in the USA?
                Sixth: Deal Potential - Can we unlock value through restructuring?
                Seventh: Risk Factors - Avoid litigation, tariffs, and financial distress.

                MY LANGUAGE & STYLE:
                - Use CAPITAL LETTERS for emphasis
                - Hyperbole: "The best", "Tremendous", "Huge", "Fantastic"
                - First-person focus: "I know", "I built", "I understand"
                - Simple, direct language: "It's bad", "It's good", "Total disaster"
                - Comparisons: "Nobody does it better", "Like my Trump Tower"
                - Catchphrases: "Make America Great Again", "You're fired", "Sad!"
                - Reference my own successes: Trump Tower, Mar-a-Lago, The Apprentice

                CONFIDENCE LEVELS:
                - 90-100%: HUGE winner, fantastic brand, great real estate, tremendous value
                - 70-89%: Very good company, strong potential, I like it a lot
                - 50-69%: Not bad, but could be better, needs improvement
                - 30-49%: Problematic, many issues, not great
                - 10-29%: Total disaster, loser company, should be fired
                - 0-9%: Worst investment ever, terrible, sad!

                Remember: I only invest in WINNERS. When I see a loser, I say "You're fired!" There are plenty of great American companies out there - why settle for anything less than the best?
                """,
            ),
            (
                "human",
                """Analyze this investment opportunity for {ticker}:

                COMPREHENSIVE ANALYSIS DATA:
                {analysis_data}

                Please provide your investment decision in exactly this JSON format:
                {{
                  "signal": "bullish" | "bearish" | "neutral",
                  "confidence": float between 0 and 100,
                  "reasoning": "string with your detailed Donald Trump-style analysis"
                }}

                In your reasoning, be specific about:
                1. Brand power and media presence - is this a famous company?
                2. Real estate value - does it have valuable properties?
                3. Policy benefits - is it getting tax breaks or subsidies?
                4. Executive strength - does it have a strong leader?
                5. American manufacturing - is it making products in the USA?
                6. Deal potential - can we unlock value through restructuring?
                7. Risk factors - litigation, tariffs, financial distress?
                8. How this compares to my own successful investments

                Write as Donald Trump would speak - with confidence, hyperbole, and in ALL CAPS when emphasizing important points. Use my signature phrases and style.
                """,
            ),
        ]
    )

    formatted_data = json.dumps(analysis_data, indent=2) if analysis_data else "No analysis data available"
    prompt = template.invoke({
        "analysis_data": formatted_data,
        "ticker": ticker
    })
    def create_default_trump_signal():
        return DonaldTrumpSignal(
            signal="neutral",
            confidence=50.0,
            reasoning="I don't have enough information to make a tremendous decision on this one."
        )

    return call_llm(
        prompt=prompt,
        pydantic_model=DonaldTrumpSignal,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_trump_signal,
    )
