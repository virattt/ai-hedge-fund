from __future__ import annotations

"""Valuation Agent

Implements four complementary valuation methodologies and aggregates them with
configurable weights. 
"""

import json
import statistics
from langchain_core.messages import HumanMessage
from src.graph.state import AgentState, show_agent_reasoning
from src.utils.progress import progress
from src.utils.api_key import get_api_key_from_state
from src.tools.api import (
    get_financial_metrics,
    get_market_cap,
    search_line_items,
)

def valuation_analyst_agent(state: AgentState, agent_id: str = "valuation_analyst_agent"):
    """Run valuation across tickers and write signals back to `state`."""

    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    valuation_analysis: dict[str, dict] = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching financial data")

        # --- Historical financial metrics ---
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=8,
            api_key=api_key,
        )
        if not financial_metrics:
            progress.update_status(agent_id, ticker, "Failed: No financial metrics found")
            continue
        most_recent_metrics = financial_metrics[0]

        # --- Enhanced line‑items ---
        progress.update_status(agent_id, ticker, "Gathering comprehensive line items")
        line_items = search_line_items(
            ticker=ticker,
            line_items=[
                "free_cash_flow",
                "net_income",
                "depreciation_and_amortization",
                "capital_expenditure",
                "working_capital",
                "total_debt",
                "cash_and_equivalents", 
                "interest_expense",
                "revenue",
                "operating_income",
                "ebit",
                "ebitda"
            ],
            end_date=end_date,
            period="ttm",
            limit=8,
            api_key=api_key,
        )
        if len(line_items) < 2:
            progress.update_status(agent_id, ticker, "Failed: Insufficient financial line items")
            continue
        li_curr, li_prev = line_items[0], line_items[1]

        # ------------------------------------------------------------------
        # Valuation models
        # ------------------------------------------------------------------
        # Handle potential None values for working capital
        if li_curr.working_capital is not None and li_prev.working_capital is not None:
            wc_change = li_curr.working_capital - li_prev.working_capital
        else:
            wc_change = 0  # Default to 0 if working capital data is unavailable

        # Owner Earnings
        owner_val = calculate_owner_earnings_value(
            net_income=li_curr.net_income,
            depreciation=li_curr.depreciation_and_amortization,
            capex=li_curr.capital_expenditure,
            working_capital_change=wc_change,
            growth_rate=most_recent_metrics.earnings_growth or 0.05,
        )

        # Enhanced Discounted Cash Flow with WACC and scenarios
        progress.update_status(agent_id, ticker, "Calculating WACC and enhanced DCF")
        
        # Calculate WACC
        wacc = calculate_wacc(
            market_cap=most_recent_metrics.market_cap or 0,
            total_debt=getattr(li_curr, 'total_debt', None),
            cash=getattr(li_curr, 'cash_and_equivalents', None),
            interest_coverage=most_recent_metrics.interest_coverage,
            debt_to_equity=most_recent_metrics.debt_to_equity,
        )
        
        # Prepare FCF history for enhanced DCF
        fcf_history = []
        for li in line_items:
            if hasattr(li, 'free_cash_flow') and li.free_cash_flow is not None:
                fcf_history.append(li.free_cash_flow)
        
        # Enhanced DCF with scenarios
        dcf_results = calculate_dcf_scenarios(
            fcf_history=fcf_history,
            growth_metrics={
                'revenue_growth': most_recent_metrics.revenue_growth,
                'fcf_growth': most_recent_metrics.free_cash_flow_growth,
                'earnings_growth': most_recent_metrics.earnings_growth
            },
            wacc=wacc,
            market_cap=most_recent_metrics.market_cap or 0,
            revenue_growth=most_recent_metrics.revenue_growth
        )
        
        dcf_val = dcf_results['expected_value']

        # Implied Equity Value
        ev_ebitda_val = calculate_ev_ebitda_value(financial_metrics)

        # Residual Income Model
        rim_val = calculate_residual_income_value(
            market_cap=most_recent_metrics.market_cap,
            net_income=li_curr.net_income,
            price_to_book_ratio=most_recent_metrics.price_to_book_ratio,
            book_value_growth=most_recent_metrics.book_value_growth or 0.03,
        )

        # ------------------------------------------------------------------
        # Aggregate & signal
        # ------------------------------------------------------------------
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)
        if not market_cap:
            progress.update_status(agent_id, ticker, "Failed: Market cap unavailable")
            continue

        method_values = {
            "dcf": {"value": dcf_val, "weight": 0.35},
            "owner_earnings": {"value": owner_val, "weight": 0.35},
            "ev_ebitda": {"value": ev_ebitda_val, "weight": 0.20},
            "residual_income": {"value": rim_val, "weight": 0.10},
        }

        total_weight = sum(v["weight"] for v in method_values.values() if v["value"] > 0)
        if total_weight == 0:
            progress.update_status(agent_id, ticker, "Failed: All valuation methods zero")
            continue

        for v in method_values.values():
            v["gap"] = (v["value"] - market_cap) / market_cap if v["value"] > 0 else None

        weighted_gap = sum(
            v["weight"] * v["gap"] for v in method_values.values() if v["gap"] is not None
        ) / total_weight

        signal = "bullish" if weighted_gap > 0.15 else "bearish" if weighted_gap < -0.15 else "neutral"
        confidence = round(min(abs(weighted_gap) / 0.30 * 100, 100))

        # Enhanced reasoning with DCF scenario details
        reasoning = {}
        for m, vals in method_values.items():
            if vals["value"] > 0:
                base_details = (
                    f"Value: ${vals['value']:,.2f}, Market Cap: ${market_cap:,.2f}, "
                    f"Gap: {vals['gap']:.1%}, Weight: {vals['weight']*100:.0f}%"
                )
                
                # Add enhanced DCF details
                if m == "dcf" and 'dcf_results' in locals():
                    enhanced_details = (
                        f"{base_details}\n"
                        f"  WACC: {wacc:.1%}, Bear: ${dcf_results['downside']:,.2f}, "
                        f"Bull: ${dcf_results['upside']:,.2f}, Range: ${dcf_results['range']:,.2f}"
                    )
                else:
                    enhanced_details = base_details
                
                reasoning[f"{m}_analysis"] = {
                    "signal": (
                        "bullish" if vals["gap"] and vals["gap"] > 0.15 else
                        "bearish" if vals["gap"] and vals["gap"] < -0.15 else "neutral"
                    ),
                    "details": enhanced_details,
                }
        
        # Add overall DCF scenario summary if available
        if 'dcf_results' in locals():
            reasoning["dcf_scenario_analysis"] = {
                "bear_case": f"${dcf_results['downside']:,.2f}",
                "base_case": f"${dcf_results['scenarios']['base']:,.2f}",  
                "bull_case": f"${dcf_results['upside']:,.2f}",
                "wacc_used": f"{wacc:.1%}",
                "fcf_periods_analyzed": len(fcf_history)
            }

        valuation_analysis[ticker] = {
            "signal": signal,
            "confidence": confidence,
            "reasoning": reasoning,
        }
        progress.update_status(agent_id, ticker, "Done", analysis=json.dumps(reasoning, indent=4))

    # ---- Emit message (for LLM tool chain) ----
    msg = HumanMessage(content=json.dumps(valuation_analysis), name=agent_id)
    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(valuation_analysis, "Valuation Analysis Agent")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"][agent_id] = valuation_analysis

    progress.update_status(agent_id, None, "Done")
    
    return {"messages": [msg], "data": data}

#############################
# Helper Valuation Functions
#############################

def calculate_owner_earnings_value(
    net_income: float | None,
    depreciation: float | None,
    capex: float | None,
    working_capital_change: float | None,
    growth_rate: float = 0.05,
    required_return: float = 0.15,
    margin_of_safety: float = 0.25,
    num_years: int = 5,
) -> float:
    """Buffett owner‑earnings valuation with margin‑of‑safety."""
    if not all(isinstance(x, (int, float)) for x in [net_income, depreciation, capex, working_capital_change]):
        return 0

    owner_earnings = net_income + depreciation - capex - working_capital_change
    if owner_earnings <= 0:
        return 0

    pv = 0.0
    for yr in range(1, num_years + 1):
        future = owner_earnings * (1 + growth_rate) ** yr
        pv += future / (1 + required_return) ** yr

    terminal_growth = min(growth_rate, 0.03)
    term_val = (owner_earnings * (1 + growth_rate) ** num_years * (1 + terminal_growth)) / (
        required_return - terminal_growth
    )
    pv_term = term_val / (1 + required_return) ** num_years

    intrinsic = pv + pv_term
    return intrinsic * (1 - margin_of_safety)


def calculate_intrinsic_value(
    free_cash_flow: float | None,
    growth_rate: float = 0.05,
    discount_rate: float = 0.10,
    terminal_growth_rate: float = 0.02,
    num_years: int = 5,
) -> float:
    """Classic DCF on FCF with constant growth and terminal value."""
    if free_cash_flow is None or free_cash_flow <= 0:
        return 0

    pv = 0.0
    for yr in range(1, num_years + 1):
        fcft = free_cash_flow * (1 + growth_rate) ** yr
        pv += fcft / (1 + discount_rate) ** yr

    term_val = (
        free_cash_flow * (1 + growth_rate) ** num_years * (1 + terminal_growth_rate)
    ) / (discount_rate - terminal_growth_rate)
    pv_term = term_val / (1 + discount_rate) ** num_years

    return pv + pv_term


def calculate_ev_ebitda_value(financial_metrics: list):
    """Implied equity value via median EV/EBITDA multiple."""
    if not financial_metrics:
        return 0
    m0 = financial_metrics[0]
    if not (m0.enterprise_value and m0.enterprise_value_to_ebitda_ratio):
        return 0
    if m0.enterprise_value_to_ebitda_ratio == 0:
        return 0

    ebitda_now = m0.enterprise_value / m0.enterprise_value_to_ebitda_ratio
    med_mult = statistics.median([
        m.enterprise_value_to_ebitda_ratio for m in financial_metrics if m.enterprise_value_to_ebitda_ratio
    ])
    ev_implied = med_mult * ebitda_now
    net_debt = (m0.enterprise_value or 0) - (m0.market_cap or 0)
    return max(ev_implied - net_debt, 0)


def calculate_residual_income_value(
    market_cap: float | None,
    net_income: float | None,
    price_to_book_ratio: float | None,
    book_value_growth: float = 0.03,
    cost_of_equity: float = 0.10,
    terminal_growth_rate: float = 0.03,
    num_years: int = 5,
):
    """Residual Income Model (Edwards‑Bell‑Ohlson)."""
    if not (market_cap and net_income and price_to_book_ratio and price_to_book_ratio > 0):
        return 0

    book_val = market_cap / price_to_book_ratio
    ri0 = net_income - cost_of_equity * book_val
    if ri0 <= 0:
        return 0

    pv_ri = 0.0
    for yr in range(1, num_years + 1):
        ri_t = ri0 * (1 + book_value_growth) ** yr
        pv_ri += ri_t / (1 + cost_of_equity) ** yr

    term_ri = ri0 * (1 + book_value_growth) ** (num_years + 1) / (
        cost_of_equity - terminal_growth_rate
    )
    pv_term = term_ri / (1 + cost_of_equity) ** num_years

    intrinsic = book_val + pv_ri + pv_term
    return intrinsic * 0.8  # 20% margin of safety


####################################
# Enhanced DCF Helper Functions
####################################

def calculate_wacc(
    market_cap: float,
    total_debt: float | None,
    cash: float | None,
    interest_coverage: float | None,
    debt_to_equity: float | None,
    beta_proxy: float = 1.0,
    risk_free_rate: float = 0.045,
    market_risk_premium: float = 0.06
) -> float:
    """Calculate WACC using available financial data."""
    
    # Cost of Equity (CAPM)
    cost_of_equity = risk_free_rate + beta_proxy * market_risk_premium
    
    # Cost of Debt - estimate from interest coverage
    if interest_coverage and interest_coverage > 0:
        # Higher coverage = lower cost of debt
        cost_of_debt = max(risk_free_rate + 0.01, risk_free_rate + (10 / interest_coverage))
    else:
        cost_of_debt = risk_free_rate + 0.05  # Default spread
    
    # Weights
    net_debt = max((total_debt or 0) - (cash or 0), 0)
    total_value = market_cap + net_debt
    
    if total_value > 0:
        weight_equity = market_cap / total_value
        weight_debt = net_debt / total_value
        
        # Tax shield (assume 25% corporate tax rate)
        wacc = (weight_equity * cost_of_equity) + (weight_debt * cost_of_debt * 0.75)
    else:
        wacc = cost_of_equity
    
    return min(max(wacc, 0.06), 0.20)  # Floor 6%, cap 20%


def calculate_fcf_volatility(fcf_history: list[float]) -> float:
    """Calculate FCF volatility as coefficient of variation."""
    if len(fcf_history) < 3:
        return 0.5  # Default moderate volatility
    
    # Filter out zeros and negatives for volatility calc
    positive_fcf = [fcf for fcf in fcf_history if fcf > 0]
    if len(positive_fcf) < 2:
        return 0.8  # High volatility if mostly negative FCF
    
    try:
        mean_fcf = statistics.mean(positive_fcf)
        std_fcf = statistics.stdev(positive_fcf)
        return min(std_fcf / mean_fcf, 1.0) if mean_fcf > 0 else 0.8
    except:
        return 0.5


def calculate_enhanced_dcf_value(
    fcf_history: list[float],
    growth_metrics: dict,
    wacc: float,
    market_cap: float,
    revenue_growth: float | None = None
) -> float:
    """Enhanced DCF with multi-stage growth."""
    
    if not fcf_history or fcf_history[0] <= 0:
        return 0
    
    # Analyze FCF trend and quality
    fcf_current = fcf_history[0]
    fcf_avg_3yr = sum(fcf_history[:3]) / min(3, len(fcf_history))
    fcf_volatility = calculate_fcf_volatility(fcf_history)
    
    # Stage 1: High Growth (Years 1-3)
    # Use revenue growth but cap based on business maturity
    high_growth = min(revenue_growth or 0.05, 0.25) if revenue_growth else 0.05
    if market_cap > 50_000_000_000:  # Large cap
        high_growth = min(high_growth, 0.10)
    
    # Stage 2: Transition (Years 4-7)
    transition_growth = (high_growth + 0.03) / 2
    
    # Stage 3: Terminal (steady state)
    terminal_growth = min(0.03, high_growth * 0.6)
    
    # Project FCF with stages
    pv = 0
    base_fcf = max(fcf_current, fcf_avg_3yr * 0.85)  # Conservative base
    
    # High growth stage
    for year in range(1, 4):
        fcf_projected = base_fcf * (1 + high_growth) ** year
        pv += fcf_projected / (1 + wacc) ** year
    
    # Transition stage
    for year in range(4, 8):
        transition_rate = transition_growth * (8 - year) / 4  # Declining
        fcf_projected = base_fcf * (1 + high_growth) ** 3 * (1 + transition_rate) ** (year - 3)
        pv += fcf_projected / (1 + wacc) ** year
    
    # Terminal value
    final_fcf = base_fcf * (1 + high_growth) ** 3 * (1 + transition_growth) ** 4
    if wacc <= terminal_growth:
        terminal_growth = wacc * 0.8  # Adjust if invalid
    terminal_value = (final_fcf * (1 + terminal_growth)) / (wacc - terminal_growth)
    pv_terminal = terminal_value / (1 + wacc) ** 7
    
    # Quality adjustment based on FCF volatility
    quality_factor = max(0.7, 1 - (fcf_volatility * 0.5))
    
    return (pv + pv_terminal) * quality_factor


def calculate_dcf_scenarios(
    fcf_history: list[float],
    growth_metrics: dict,
    wacc: float,
    market_cap: float,
    revenue_growth: float | None = None
) -> dict:
    """Calculate DCF under multiple scenarios."""
    
    scenarios = {
        'bear': {'growth_adj': 0.5, 'wacc_adj': 1.2, 'terminal_adj': 0.8},
        'base': {'growth_adj': 1.0, 'wacc_adj': 1.0, 'terminal_adj': 1.0},
        'bull': {'growth_adj': 1.5, 'wacc_adj': 0.9, 'terminal_adj': 1.2}
    }
    
    results = {}
    base_revenue_growth = revenue_growth or 0.05
    
    for scenario, adjustments in scenarios.items():
        adjusted_revenue_growth = base_revenue_growth * adjustments['growth_adj']
        adjusted_wacc = wacc * adjustments['wacc_adj']
        
        results[scenario] = calculate_enhanced_dcf_value(
            fcf_history=fcf_history,
            growth_metrics=growth_metrics,
            wacc=adjusted_wacc,
            market_cap=market_cap,
            revenue_growth=adjusted_revenue_growth
        )
    
    # Probability-weighted average
    expected_value = (
        results['bear'] * 0.2 + 
        results['base'] * 0.6 + 
        results['bull'] * 0.2
    )
    
    return {
        'scenarios': results,
        'expected_value': expected_value,
        'range': results['bull'] - results['bear'],
        'upside': results['bull'],
        'downside': results['bear']
    }
