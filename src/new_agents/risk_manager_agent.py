from langchain_openai import ChatOpenAI
from graph.state import AgentState, show_agent_reasoning
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from typing_extensions import Literal
from datetime import datetime, timedelta
from utils.progress import progress
from utils.llm import call_llm
import json

"""
Risk Manager Agent: 
 Analyzes each strategy's risk metrics and based on preset thresholds, provides a signal for the management of each strategy.
 Possible signals: no management, close for a profit, close for a loss, roll for a credit, roll for a debit
 There are the possible roll actions:
roll for a credit when Implied Volatility is still high:
   1) roll to the same expiration cycle -> main purpose is to adjust delta when still DTE is around or bigger than 30
   2) roll to the next expiration cycle -> main purpose is to adjust delta and give more time to avoid convexity. Usually when DTE is less than 28 days
In case of roll the agent should find the best strategy to roll to from the option chain of the underlying stock.
"""

# Define the risk management signal model
class RiskManagementSignal(BaseModel):
    """Model for risk management signals for a strategy."""
    signal: Literal["no management", "close for a profit", "close for a loss", 
                    "roll for a credit - same expiry", "roll for a credit - next expiry"]
    confidence: float = Field(..., ge=0.0, le=1.0)  # Confidence level between 0 and 1
    reasoning: str  # Explanation for the signal
    target_strategy: Optional[Dict[str, Any]] = None  # For roll signals, details of the target strategy

# Define the strategy analysis model
class StrategyAnalysis(BaseModel):
    """Model for the analysis of a single strategy."""
    ticker: str
    description: str
    current_pnl: float
    current_pnl_percent: float
    days_to_expiry: int
    risk_metrics: Dict[str, Any]
    signal: RiskManagementSignal

# Define the portfolio risk analysis model
class PortfolioRiskAnalysis(BaseModel):
    """Model for the overall portfolio risk analysis."""
    date: str
    total_portfolio_value: float
    total_margin_used: float
    margin_utilization_percent: float
    total_beta_weighted_delta: float
    strategies_analysis: List[StrategyAnalysis]

# Helper functions
def calculate_days_to_expiry(expiry_date: str) -> int:
    """
    Calculate the number of days to expiry for a strategy.
    
    Args:
        expiry_date: The expiry date in format 'YYYY-MM-DD'
        
    Returns:
        int: Number of days to expiry
    """
    try:
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
        today = datetime.now()
        return max(0, (expiry - today).days)
    except (ValueError, TypeError):
        return 0

def should_close_for_profit(strategy: Dict[str, Any], thresholds: Dict[str, float]) -> tuple:
    """
    Determine if a strategy should be closed for profit based on thresholds.
    
    Args:
        strategy: The strategy data
        thresholds: Dictionary of profit thresholds
        
    Returns:
        tuple: (bool, str) - Whether to close and reasoning
    """
    pnl_percent = strategy.get("pnl_percent", 0)
    
    # Different thresholds based on days to expiry
    expiry = strategy.get("legs", [{}])[0].get("expiry") if strategy.get("legs") else None
    dte = calculate_days_to_expiry(expiry) if expiry else 0
    
    if dte <= 7 and pnl_percent >= thresholds["profit_threshold_close_expiry"]:
        return True, f"Close for profit: {pnl_percent:.2f}% profit with only {dte} days to expiry (threshold: {thresholds['profit_threshold_close_expiry']:.2f}%)"
    
    if dte <= 14 and pnl_percent >= thresholds["profit_threshold_near_expiry"]:
        return True, f"Close for profit: {pnl_percent:.2f}% profit with {dte} days to expiry (threshold: {thresholds['profit_threshold_near_expiry']:.2f}%)"
    
    if pnl_percent >= thresholds["profit_threshold_general"]:
        return True, f"Close for profit: {pnl_percent:.2f}% profit (threshold: {thresholds['profit_threshold_general']:.2f}%)"
    
    return False, ""

def should_close_for_loss(strategy: Dict[str, Any], thresholds: Dict[str, float]) -> tuple:
    """
    Determine if a strategy should be closed for loss based on thresholds.
    
    Args:
        strategy: The strategy data
        thresholds: Dictionary of loss thresholds
        
    Returns:
        tuple: (bool, str) - Whether to close and reasoning
    """
    pnl_percent = strategy.get("pnl_percent", 0)
    risk_profile = strategy.get("risk_profile", {})
    
    # Check if loss exceeds max loss threshold
    if pnl_percent <= -thresholds["max_loss_threshold"]:
        return True, f"Close for loss: {pnl_percent:.2f}% loss exceeds max loss threshold of {thresholds['max_loss_threshold']:.2f}%"
    
    # Check if CVaR is too high relative to portfolio
    cvar = risk_profile.get("CVaR", 0)
    if cvar > thresholds["cvar_threshold"]:
        return True, f"Close for loss: CVaR of ${cvar:.2f} exceeds threshold of ${thresholds['cvar_threshold']:.2f}"
    
    return False, ""

def should_roll_strategy(strategy: Dict[str, Any], thresholds: Dict[str, float]) -> tuple:
    """
    Determine if a strategy should be rolled based on thresholds.
    
    Args:
        strategy: The strategy data
        thresholds: Dictionary of roll thresholds
        
    Returns:
        tuple: (bool, str, roll_type) - Whether to roll, reasoning, and roll type
    """
    # Get expiry from first leg
    expiry = strategy.get("legs", [{}])[0].get("expiry") if strategy.get("legs") else None
    dte = calculate_days_to_expiry(expiry) if expiry else 0
    
    # Get IV rank
    ivr = strategy.get("ivr", 0)
    
    # Check delta exposure
    delta = strategy.get("greeks", {}).get("delta", 0) if hasattr(strategy, "greeks") else 0
    
    # If IV is high and DTE is low, consider rolling to next cycle
    if ivr > thresholds["high_iv_threshold"] and dte < 28:
        return True, f"Roll to next expiry cycle: {dte} DTE with high IV rank of {ivr:.2f}", "roll for a credit - next expiry"
    
    # If IV is high and delta needs adjustment, consider rolling in same cycle
    if ivr > thresholds["high_iv_threshold"] and abs(delta) > thresholds["delta_adjustment_threshold"] and dte >= 30:
        return True, f"Roll in same expiry cycle: Delta of {delta:.2f} needs adjustment with {dte} DTE", "roll for a credit - same expiry"
    
    # If DTE is very low, consider rolling to next cycle
    if dte < 14:
        # If IV is still high, roll for credit
        if ivr > thresholds["medium_iv_threshold"]:
            return True, f"Roll to next expiry cycle: Only {dte} DTE remaining with IV rank of {ivr:.2f}", "roll for a credit - next expiry"
        else:
            return True, f"Roll to next expiry cycle: Only {dte} DTE remaining with low IV rank of {ivr:.2f}", "roll for a debit - next expiry"
    
    return False, "", ""

def analyze_strategy(strategy: Dict[str, Any], thresholds: Dict[str, float]) -> RiskManagementSignal:
    """
    Analyze a strategy and determine the appropriate risk management signal.
    
    Args:
        strategy: The strategy data
        thresholds: Dictionary of thresholds for different signals
        
    Returns:
        RiskManagementSignal: The risk management signal for the strategy
    """
    # Check if should close for profit
    close_profit, profit_reason = should_close_for_profit(strategy, thresholds)
    if close_profit:
        return RiskManagementSignal(
            signal="close for a profit",
            confidence=0.9,
            reasoning=profit_reason
        )
    
    # Check if should close for loss
    close_loss, loss_reason = should_close_for_loss(strategy, thresholds)
    if close_loss:
        return RiskManagementSignal(
            signal="close for a loss",
            confidence=0.85,
            reasoning=loss_reason
        )
    
    # Check if should roll
    should_roll, roll_reason, roll_type = should_roll_strategy(strategy, thresholds)
    if should_roll:
        return RiskManagementSignal(
            signal=roll_type,
            confidence=0.8,
            reasoning=roll_reason
        )
    
    # Default: no management needed
    return RiskManagementSignal(
        signal="no management",
        confidence=0.7,
        reasoning="Strategy is performing within acceptable parameters"
    )

def get_default_thresholds() -> Dict[str, float]:
    """
    Get default thresholds for risk management decisions.
    
    Returns:
        Dict[str, float]: Dictionary of threshold values
    """
    return {
        # Profit thresholds
        "profit_threshold_general": 50.0,  # 50% of max profit
        "profit_threshold_near_expiry": 30.0,  # 30% of max profit if near expiry
        "profit_threshold_close_expiry": 20.0,  # 20% of max profit if very close to expiry
        
        # Loss thresholds
        "max_loss_threshold": 25.0,  # 25% of max loss
        "cvar_threshold": 5000.0,  # $5000 CVaR threshold
        
        # Roll thresholds
        "high_iv_threshold": 0.7,  # IV rank > 70%
        "medium_iv_threshold": 0.5,  # IV rank > 50%
        "delta_adjustment_threshold": 0.3,  # Delta > 0.3 or < -0.3
    }

def risk_manager_agent(state: AgentState):
    """
    Analyzes each strategy's risk metrics and provides a signal for management.
    
    This agent evaluates each strategy in the portfolio based on:
    1. Current P&L
    2. Days to expiry
    3. Risk metrics (CVaR, delta exposure, etc.)
    4. Market conditions (IV rank)
    
    It then provides a signal for each strategy:
    - No management needed
    - Close for a profit
    - Close for a loss
    - Roll for a credit (same expiry or next expiry)
    - Roll for a debit (same expiry or next expiry)
    
    Args:
        state: The current agent state containing portfolio and market data
        
    Returns:
        Updated agent state with risk management signals
    """
    progress.update_status("risk_manager_agent", "all", "Analyzing portfolio strategies")
    
    # Extract portfolio and market data from state
    data = state.data
    portfolio = data.portfolio
    market_conditions = data.market_conditions
    
    # Get default thresholds (could be customized based on profile in the future)
    thresholds = get_default_thresholds()
    
    # Initialize portfolio risk analysis
    portfolio_analysis = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_portfolio_value": portfolio.net_liquidation_value,
        "total_margin_used": portfolio.margin_used,
        "margin_utilization_percent": (portfolio.margin_used / portfolio.max_margin * 100) if portfolio.max_margin > 0 else 0,
        "total_beta_weighted_delta": portfolio.total_beta_weighted_delta,
        "strategies_analysis": []
    }
    
    # Analyze each strategy in the portfolio
    for idx, strategy in enumerate(portfolio.strategies):
        progress.update_status("risk_manager_agent", strategy.ticker, "Analyzing strategy risk")
        
        # Calculate days to expiry (use first leg's expiry as reference)
        expiry = strategy.legs[0].expiry if strategy.legs else None
        days_to_expiry = calculate_days_to_expiry(expiry) if expiry else 0
        
        # Extract risk metrics for analysis
        risk_metrics = {
            "CVaR": strategy.risk_profile.CVaR,
            "margin": strategy.risk_profile.margin,
            "survival_probability_50": strategy.risk_profile.survival_probability_50,
            "expected_delta_move": strategy.risk_profile.expected_delta_move,
            "expected_convexity_move": strategy.risk_profile.expected_convexity_move,
            "days_to_expiry": days_to_expiry,
            "ivr": strategy.ivr
        }
        
        # Generate risk management signal
        signal = analyze_strategy(strategy.dict(), thresholds)
        
        # Add strategy analysis to portfolio analysis
        strategy_analysis = {
            "ticker": strategy.ticker,
            "description": strategy.description,
            "current_pnl": strategy.pnl,
            "current_pnl_percent": strategy.pnl_percent,
            "days_to_expiry": days_to_expiry,
            "risk_metrics": risk_metrics,
            "signal": signal.dict()
        }
        
        portfolio_analysis["strategies_analysis"].append(strategy_analysis)
        progress.update_status("risk_manager_agent", strategy.ticker, "Analysis complete")
    
    """ Methodic to calculate the total risk management score
       analyze_mechanical_management -> close before 21DTE
       analyze_strategic_management (strategy assumption) -> hold until max profit
       analyze_risk_score -> a combined score indicating 
       1) defined risk strategies: (we assume the spreads are used in two strategies)
           - short out of money (high prob of profit) credit spreads
              -- close for a profit target (50%) before 21 DTE. 
              -- close in profit 
              -- never manage 
           - long directional debit spreads at the money
           
    """
    
    # Create message for agent output
    message = HumanMessage(
        content=json.dumps(portfolio_analysis),
        name="risk_manager_agent",
    )
    
    # Show reasoning if enabled
    if state.metadata.get("show_reasoning", False):
        show_agent_reasoning(portfolio_analysis, "Risk Manager Agent")
    
    # Add the analysis to the analyst_signals
    if "analyst_signals" not in data:
        data.analyst_signals = {}
    data.analyst_signals["risk_manager_agent"] = portfolio_analysis
    
    # Return updated state
    return AgentState(
        messages=state.messages + [message],
        data=data,
        metadata=state.metadata
    )