from langchain_openai import ChatOpenAI
from new_graph.state import AgentState, show_agent_reasoning
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from typing_extensions import Literal
from datetime import datetime, timedelta
from utils.progress import progress
from utils.llm import call_llm
import json


class TastyTradeSignal(BaseModel):
    """Model for TastyTrade management signals."""
    signal: Literal["no management", "close for a profit", "roll for a credit", "close for a loss"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str


def tasty_trade_manager(state: AgentState):
    """
    This will implement the TastyTrade management style for options strategies.
    
    TastyTrade management general principles:
    1. Trade often, Trade Small
    2. 15-50% of portfolio allocation depending on VIX levels
    3. Max size of each strategy 2-5% of net liquidation value
    4. Daily Theta around 0.01%-0.05% of net liquidation value
    5. Profit taking around 25%-50% for naked - defined risk stategies
    6. No stop loss
    7. Manage before 21 DTE:
       -- if profit > 15% -> close
       -- else if u can roll for a credit -> roll
       -- primary goal of roll is to reduce overall delta, and add time to be right
       -- roll up put side when stock goes high, roll down call side when stock goes low
       -- go untill u have a straddle 
       -- do not go inverted (take loss)
    """
    data = state.data
    portfolio = data.portfolio
    market_conditions = data.market_conditions
    
    analysis_data = {}
    tasty_trade_analysis = {}
    
    # Initialize portfolio risk analysis
    portfolio_analysis = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_portfolio_value": portfolio.net_liquidation_value,
        "total_margin_used": portfolio.margin_used,
        "margin_utilization_percent": (portfolio.margin_used / portfolio.max_margin * 100) if portfolio.max_margin > 0 else 0,
        "total_beta_weighted_delta": portfolio.total_beta_weighted_delta,
        "strategies_analysis": []
    }
    
    for strategy in portfolio.strategies:
        ticker = strategy.ticker
        progress.update_status("tasty_trade_manager", ticker, "Analyzing strategy")
        
        # 1. Position Size Analysis
        progress.update_status("tasty_trade_manager", ticker, "Analyzing Position Size")
        position_size_analysis = analyze_position_size(strategy, portfolio.net_liquidation_value)
        
        # 2. DTE Analysis
        progress.update_status("tasty_trade_manager", ticker, "Analyzing Days to Expiry")
        dte_analysis = analyze_days_to_expiry(strategy)
        
        # 3. Profit Analysis
        progress.update_status("tasty_trade_manager", ticker, "Analyzing Profit")
        profit_analysis = analyze_profit(strategy)
        
        # 4. Delta Analysis
        progress.update_status("tasty_trade_manager", ticker, "Analyzing Delta")
        delta_analysis = analyze_delta(strategy)
        
        # 5. Theta Analysis
        progress.update_status("tasty_trade_manager", ticker, "Analyzing Theta")
        theta_analysis = analyze_theta(strategy, portfolio.net_liquidation_value)
        
        # 6. VIX Level Analysis
        progress.update_status("tasty_trade_manager", ticker, "Analyzing VIX Level")
        vix_analysis = analyze_vix_level(market_conditions.vix)
        
        # Combine all analyses
        strategy_analysis = {
            "ticker": ticker,
            "description": strategy.description,
            "position_size_analysis": position_size_analysis,
            "dte_analysis": dte_analysis,
            "profit_analysis": profit_analysis,
            "delta_analysis": delta_analysis,
            "theta_analysis": theta_analysis,
            "vix_analysis": vix_analysis
        }
        
        # Calculate total score
        total_score = (
            position_size_analysis["score"] + 
            dte_analysis["score"] + 
            profit_analysis["score"] + 
            delta_analysis["score"] + 
            theta_analysis["score"] +
            vix_analysis["score"]
        )
        max_possible_score = 30  # Sum of max scores from all analyses
        
        strategy_analysis["total_score"] = total_score
        strategy_analysis["max_score"] = max_possible_score
        strategy_analysis["score_percentage"] = (total_score / max_possible_score) * 100
        
        # Add to portfolio analysis
        portfolio_analysis["strategies_analysis"].append(strategy_analysis)
        
        # Store analysis data for LLM processing
        analysis_data[ticker] = strategy_analysis
        
        # Generate TastyTrade management signal using LLM
        progress.update_status("tasty_trade_manager", ticker, "Generating TastyTrade signal")
        tasty_output = generate_tasty_trade_output(
            ticker=ticker,
            strategy=strategy,
            analysis_data=strategy_analysis,
            model_name=state.metadata.model_name,
            model_provider=state.metadata.model_provider,
        )
        
        # Store the signal
        tasty_trade_analysis[ticker] = {
            "signal": tasty_output.signal,
            "confidence": tasty_output.confidence,
            "reasoning": tasty_output.reasoning
        }
        
        progress.update_status("tasty_trade_manager", ticker, "Done")
    
    # Create message for agent output
    message = HumanMessage(
        content=json.dumps(tasty_trade_analysis),
        name="tasty_trade_manager"
    )
    
    # Show reasoning if enabled
    if state.metadata.get("show_reasoning", False):
        show_agent_reasoning(tasty_trade_analysis, "TastyTrade Manager")
    
    # Add the analysis to the analyst_signals
    if "analyst_signals" not in data:
        data.analyst_signals = {}
    data.analyst_signals["tasty_trade_manager"] = tasty_trade_analysis
    
    # Return updated state
    return AgentState(
        messages=state.messages + [message],
        data=data,
        metadata=state.metadata
    )


def analyze_position_size(strategy: Any, portfolio_value: float) -> dict:
    """
    Analyze if the position size follows TastyTrade principles:
    - Max size of each strategy 2-5% of net liquidation value
    
    Args:
        strategy: The strategy to analyze
        portfolio_value: Total portfolio value
        
    Returns:
        dict: Analysis results with score and details
    """
    score = 0
    details = []
    
    # Get strategy size (use margin for defined risk, CVaR for undefined)
    if hasattr(strategy, "risk_profile") and hasattr(strategy.risk_profile, "risk_category"):
        if strategy.risk_profile.risk_category == "defined":
            strategy_size = strategy.risk_profile.margin
        else:
            strategy_size = strategy.risk_profile.CVaR
    else:
        strategy_size = strategy.risk_profile.margin if hasattr(strategy.risk_profile, "margin") else 0
    
    # Calculate position size as percentage of portfolio
    position_size_percent = (strategy_size / portfolio_value) * 100 if portfolio_value > 0 else 0
    
    # Score based on TastyTrade guidelines (2-5% of portfolio)
    if 2 <= position_size_percent <= 5:
        score += 5
        details.append(f"Ideal position size: {position_size_percent:.2f}% of portfolio (target: 2-5%)")
    elif 1 <= position_size_percent < 2:
        score += 3
        details.append(f"Slightly small position size: {position_size_percent:.2f}% of portfolio (target: 2-5%)")
    elif 5 < position_size_percent <= 7:
        score += 2
        details.append(f"Slightly large position size: {position_size_percent:.2f}% of portfolio (target: 2-5%)")
    elif position_size_percent < 1:
        score += 1
        details.append(f"Too small position size: {position_size_percent:.2f}% of portfolio (target: 2-5%)")
    else:  # > 7%
        score += 0
        details.append(f"Too large position size: {position_size_percent:.2f}% of portfolio (target: 2-5%)")
    
    return {
        "score": score,
        "max_score": 5,
        "details": "; ".join(details),
        "position_size_percent": position_size_percent
    }


def analyze_days_to_expiry(strategy: Any) -> dict:
    """
    Analyze days to expiry (DTE) based on TastyTrade principles:
    - Manage before 21 DTE
    - Close or roll when approaching 21 DTE
    
    Args:
        strategy: The strategy to analyze
        
    Returns:
        dict: Analysis results with score and details
    """
    score = 0
    details = []
    
    # Get DTE from first leg
    dte = 0
    if hasattr(strategy, "legs") and strategy.legs:
        first_leg = strategy.legs[0]
        if hasattr(first_leg, "DTE"):
            dte = first_leg.DTE
        elif hasattr(first_leg, "expiry"):
            try:
                expiry_date = datetime.strptime(first_leg.expiry, "%Y-%m-%d")
                today = datetime.now()
                dte = max(0, (expiry_date - today).days)
            except (ValueError, TypeError):
                dte = 0
    
    # Score based on TastyTrade DTE guidelines
    if 30 <= dte <= 45:
        score += 5
        details.append(f"Ideal DTE: {dte} days (target: 30-45 days)")
    elif 21 <= dte < 30:
        score += 4
        details.append(f"Good DTE: {dte} days (approaching management window)")
    elif 45 < dte <= 60:
        score += 3
        details.append(f"Acceptable DTE: {dte} days (slightly longer than ideal)")
    elif dte < 21:
        if dte <= 7:
            score += 0
            details.append(f"Critical DTE: {dte} days (immediate management needed)")
        else:
            score += 1
            details.append(f"Low DTE: {dte} days (management needed, < 21 days)")
    else:  # > 60 days
        score += 2
        details.append(f"Extended DTE: {dte} days (longer than ideal TastyTrade timeframe)")
    
    return {
        "score": score,
        "max_score": 5,
        "details": "; ".join(details),
        "dte": dte
    }


def analyze_profit(strategy: Any) -> dict:
    """
    Analyze profit based on TastyTrade principles:
    - Take profit at 25-50% of max profit for defined risk strategies
    - If DTE < 21, take profit at 15%+
    
    Args:
        strategy: The strategy to analyze
        
    Returns:
        dict: Analysis results with score and details
    """
    score = 0
    details = []
    
    # Get profit metrics
    pnl_percent = strategy.pnl_percent if hasattr(strategy, "pnl_percent") else 0
    
    # Get DTE for context
    dte = 0
    if hasattr(strategy, "legs") and strategy.legs:
        first_leg = strategy.legs[0]
        if hasattr(first_leg, "DTE"):
            dte = first_leg.DTE
        elif hasattr(first_leg, "expiry"):
            try:
                expiry_date = datetime.strptime(first_leg.expiry, "%Y-%m-%d")
                today = datetime.now()
                dte = max(0, (expiry_date - today).days)
            except (ValueError, TypeError):
                dte = 0
    
    # Score based on TastyTrade profit-taking guidelines
    if pnl_percent >= 50:
        score += 5
        details.append(f"Take profit: {pnl_percent:.2f}% profit (≥ 50% target)")
    elif 25 <= pnl_percent < 50:
        score += 4
        details.append(f"Consider taking profit: {pnl_percent:.2f}% (within 25-50% target range)")
    elif 15 <= pnl_percent < 25:
        if dte < 21:
            score += 4
            details.append(f"Take profit due to low DTE: {pnl_percent:.2f}% profit with {dte} DTE")
        else:
            score += 3
            details.append(f"Moderate profit: {pnl_percent:.2f}% (below target range)")
    elif 0 <= pnl_percent < 15:
        score += 2
        details.append(f"Small profit: {pnl_percent:.2f}% (below target range)")
    else:  # negative P&L
        if pnl_percent > -25:
            score += 1
            details.append(f"Small loss: {pnl_percent:.2f}% (TastyTrade suggests no stop loss)")
        else:
            score += 0
            details.append(f"Significant loss: {pnl_percent:.2f}% (consider adjustment if possible)")
    
    return {
        "score": score,
        "max_score": 5,
        "details": "; ".join(details),
        "pnl_percent": pnl_percent,
        "dte_context": dte
    }


def analyze_delta(strategy: Any) -> dict:
    """
    Analyze delta exposure based on TastyTrade principles:
    - Goal is to reduce overall delta when rolling
    - Balance portfolio delta exposure
    
    Args:
        strategy: The strategy to analyze
        
    Returns:
        dict: Analysis results with score and details
    """
    score = 0
    details = []
    
    # Calculate total delta for the strategy
    total_delta = 0
    
    # Check if strategy has legs with greeks
    if hasattr(strategy, "legs"):
        for leg in strategy.legs:
            if hasattr(leg, "greeks") and hasattr(leg.greeks, "delta"):
                # Multiply by position (put/call) and multiplier
                position = leg.put if leg.put != 0 else leg.call
                multiplier = leg.multiplier if hasattr(leg, "multiplier") else 100
                total_delta += leg.greeks.delta * position * multiplier
    
    # Score based on delta exposure
    if -0.1 <= total_delta <= 0.1:
        score += 5
        details.append(f"Neutral delta: {total_delta:.2f} (ideal)")
    elif -0.2 <= total_delta < -0.1 or 0.1 < total_delta <= 0.2:
        score += 4
        details.append(f"Slight directional bias: {total_delta:.2f} (acceptable)")
    elif -0.3 <= total_delta < -0.2 or 0.2 < total_delta <= 0.3:
        score += 3
        details.append(f"Moderate directional bias: {total_delta:.2f} (consider adjustment)")
    elif -0.5 <= total_delta < -0.3 or 0.3 < total_delta <= 0.5:
        score += 2
        details.append(f"Strong directional bias: {total_delta:.2f} (adjustment needed)")
    else:
        score += 1
        details.append(f"Extreme directional bias: {total_delta:.2f} (immediate adjustment needed)")
    
    return {
        "score": score,
        "max_score": 5,
        "details": "; ".join(details),
        "total_delta": total_delta
    }


def analyze_theta(strategy: Any, portfolio_value: float) -> dict:
    """
    Analyze theta based on TastyTrade principles:
    - Daily theta around 0.01%-0.05% of net liquidation value
    
    Args:
        strategy: The strategy to analyze
        portfolio_value: Total portfolio value
        
    Returns:
        dict: Analysis results with score and details
    """
    score = 0
    details = []
    
    # Calculate total theta for the strategy
    total_theta = 0
    
    # Check if strategy has legs with greeks
    if hasattr(strategy, "legs"):
        for leg in strategy.legs:
            if hasattr(leg, "greeks") and hasattr(leg.greeks, "theta"):
                # Multiply by position (put/call) and multiplier
                position = leg.put if leg.put != 0 else leg.call
                multiplier = leg.multiplier if hasattr(leg, "multiplier") else 100
                total_theta += leg.greeks.theta * position * multiplier
    
    # Calculate theta as percentage of portfolio value
    theta_percent = (abs(total_theta) / portfolio_value) * 100 if portfolio_value > 0 else 0
    
    # Score based on TastyTrade theta guidelines (0.01%-0.05% of portfolio)
    if 0.01 <= theta_percent <= 0.05:
        score += 5
        details.append(f"Ideal theta: {theta_percent:.3f}% of portfolio (target: 0.01-0.05%)")
    elif 0.005 <= theta_percent < 0.01:
        score += 3
        details.append(f"Low theta: {theta_percent:.3f}% of portfolio (target: 0.01-0.05%)")
    elif 0.05 < theta_percent <= 0.07:
        score += 3
        details.append(f"High theta: {theta_percent:.3f}% of portfolio (target: 0.01-0.05%)")
    elif theta_percent < 0.005:
        score += 1
        details.append(f"Very low theta: {theta_percent:.3f}% of portfolio (target: 0.01-0.05%)")
    else:  # > 0.07%
        score += 1
        details.append(f"Excessive theta: {theta_percent:.3f}% of portfolio (target: 0.01-0.05%)")
    
    return {
        "score": score,
        "max_score": 5,
        "details": "; ".join(details),
        "theta_value": total_theta,
        "theta_percent": theta_percent
    }


def analyze_vix_level(vix: float) -> dict:
    """
    Analyze VIX level based on TastyTrade principles:
    - 15-50% of portfolio allocation depending on VIX levels
    - Higher VIX = higher allocation
    
    Args:
        vix: Current VIX value
        
    Returns:
        dict: Analysis results with score and details
    """
    score = 0
    details = []
    
    # Determine ideal allocation based on VIX
    if vix < 15:
        ideal_allocation = "15-20%"
        allocation_score = 1
        details.append(f"Low VIX environment: {vix:.1f} (reduce allocation to {ideal_allocation})")
    elif 15 <= vix < 20:
        ideal_allocation = "20-30%"
        allocation_score = 3
        details.append(f"Moderate VIX environment: {vix:.1f} (allocation: {ideal_allocation})")
    elif 20 <= vix < 30:
        ideal_allocation = "30-40%"
        allocation_score = 5
        details.append(f"Ideal VIX environment: {vix:.1f} (allocation: {ideal_allocation})")
    elif 30 <= vix < 40:
        ideal_allocation = "40-50%"
        allocation_score = 4
        details.append(f"High VIX environment: {vix:.1f} (allocation: {ideal_allocation})")
    else:  # VIX >= 40
        ideal_allocation = "30-40%"
        allocation_score = 2
        details.append(f"Extreme VIX environment: {vix:.1f} (reduce allocation to {ideal_allocation})")
    
    score += allocation_score
    
    return {
        "score": score,
        "max_score": 5,
        "details": "; ".join(details),
        "vix": vix,
        "ideal_allocation": ideal_allocation
    }


def generate_tasty_trade_output(
    ticker: str,
    strategy: Any,
    analysis_data: dict,
    model_name: str,
    model_provider: str,
) -> TastyTradeSignal:
    """
    Generates management decisions in the style of TastyTrade.
    
    Args:
        ticker: The ticker symbol
        strategy: The strategy object
        analysis_data: Analysis data for the strategy
        model_name: LLM model name
        model_provider: LLM provider
        
    Returns:
        TastyTradeSignal: The management signal
    """
    template = ChatPromptTemplate.from_messages([
        (
            "system",
            """You are a TastyTrade options management AI agent, making position management decisions using TastyTrade principles:

            1. Trade small, trade often
            2. Manage winners, not losers
            3. Close trades at 25-50% of max profit for defined risk strategies
            4. Manage positions before 21 DTE (days to expiration)
            5. If DTE < 21 and profit > 15%, close the position
            6. If DTE < 21 and can roll for a credit, roll the position
            7. No stop losses - let trades work themselves out
            8. Roll up put side when stock goes high, roll down call side when stock goes low
            9. Primary goal of rolling is to reduce overall delta and add time

            Rules:
            - If profit target is reached (25-50%), close the position
            - If approaching 21 DTE, evaluate for closing or rolling
            - If delta is too high or too low, consider rolling to adjust
            - Never go inverted - take the loss instead
            - Provide a data-driven recommendation (no management, close for profit, roll for credit)
            
            When providing your reasoning, be specific by:
            1. Referencing the specific metrics that led to your decision (DTE, profit %, position size, etc.)
            2. Explaining how your recommendation aligns with TastyTrade principles
            3. Providing clear next steps for managing the position
            
            For example, if recommending to close: "With a 42% profit and 18 DTE, this position has reached the TastyTrade profit target range (25-50%) and is approaching the 21 DTE management point. TastyTrade principles suggest taking profits now rather than risking theta decay and gamma risk."
            
            For example, if recommending to roll: "With 19 DTE and a delta of -0.32, this position needs adjustment. Following TastyTrade principles, we should roll to reduce delta exposure and add more time, which can be done for a credit due to the high IV rank."
            """
        ),
        (
            "human",
            """Based on the following analysis, create a TastyTrade-style management signal for {ticker}.

            Strategy: {strategy}
            
            Analysis Data:
            {analysis_data}

            Return the management signal in this JSON format:
            {{
              "signal": "no management/close for a profit/roll for a credit",
              "confidence": float (0-1),
              "reasoning": "string"
            }}
            """
        )
    ])

    prompt = template.invoke({
        "ticker": ticker,
        "strategy": strategy.description if hasattr(strategy, "description") else ticker,
        "analysis_data": json.dumps(analysis_data, indent=2)
    })

    def create_default_tasty_trade_signal():
        return TastyTradeSignal(
            signal="no management",
            confidence=0.5,
            reasoning="Insufficient data for analysis, defaulting to no management"
        )

    return call_llm(
        prompt=prompt,
        model_name=model_name,
        model_provider=model_provider,
        pydantic_model=TastyTradeSignal,
        agent_name="tasty_trade_manager",
        default_factory=create_default_tasty_trade_signal,
    )

# source: https://tastytrade.com