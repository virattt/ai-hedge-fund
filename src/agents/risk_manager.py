import math

from langchain_core.messages import HumanMessage

from agents.state import AgentState, show_agent_reasoning
from tools.api import prices_to_df

import json
import ast

##### Risk Management Agent #####
def risk_management_agent(state: AgentState):
    """Evaluates portfolio risk and sets position limits based on comprehensive risk analysis."""
    show_reasoning = state["metadata"]["show_reasoning"]
    portfolio = state["data"]["portfolio"]
    data = state["data"]

    prices_df = prices_to_df(data["prices"])

    # Fetch messages from other agents
    technical_message = next(msg for msg in state["messages"] if msg.name == "technical_analyst_agent")
    fundamentals_message = next(msg for msg in state["messages"] if msg.name == "fundamentals_agent")
    sentiment_message = next(msg for msg in state["messages"] if msg.name == "sentiment_agent")
    valuation_message = next(msg for msg in state["messages"] if msg.name == "valuation_agent")
    try:
        fundamental_signals = json.loads(fundamentals_message.content)
        technical_signals = json.loads(technical_message.content)
        sentiment_signals = json.loads(sentiment_message.content)
        valuation_signals = json.loads(valuation_message.content)
    except Exception as e:
        fundamental_signals = ast.literal_eval(fundamentals_message.content)
        technical_signals = ast.literal_eval(technical_message.content)
        sentiment_signals = ast.literal_eval(sentiment_message.content)
        valuation_signals = ast.literal_eval(valuation_message.content)
        
    agent_signals = {
        "fundamental": fundamental_signals,
        "technical": technical_signals,
        "sentiment": sentiment_signals,
        "valuation": valuation_signals
    }

    # 1. Calculate Risk Metrics
    returns = prices_df['close'].pct_change().dropna()
    daily_vol = returns.std()
    volatility = daily_vol * (252 ** 0.5)  # Annualized volatility approximation
    var_95 = returns.quantile(0.05)         # Simple historical VaR at 95% confidence
    max_drawdown = (prices_df['close'] / prices_df['close'].cummax() - 1).min()

    # 2. Market Risk Assessment
    market_risk_score = 0

    # Volatility scoring
    if volatility > 0.30:     # High volatility
        market_risk_score += 2
    elif volatility > 0.20:   # Moderate volatility
        market_risk_score += 1

    # VaR scoring
    # Note: var_95 is typically negative. The more negative, the worse.
    if var_95 < -0.03:
        market_risk_score += 2
    elif var_95 < -0.02:
        market_risk_score += 1

    # Max Drawdown scoring
    if max_drawdown < -0.20:  # Severe drawdown
        market_risk_score += 2
    elif max_drawdown < -0.10:
        market_risk_score += 1

    # 3. Position Size Limits
    # Consider total portfolio value, not just cash
    current_stock_value = portfolio['stock'] * prices_df['close'].iloc[-1]
    total_portfolio_value = portfolio['cash'] + current_stock_value

    base_position_size = total_portfolio_value * 0.25  # Start with 25% max position of total portfolio
    
    if market_risk_score >= 4:
        # Reduce position for high risk
        max_position_size = base_position_size * 0.5
    elif market_risk_score >= 2:
        # Slightly reduce for moderate risk
        max_position_size = base_position_size * 0.75
    else:
        # Keep base size for low risk
        max_position_size = base_position_size

    # 4. Stress Testing
    stress_test_scenarios = {
        "market_crash": -0.20,
        "moderate_decline": -0.10,
        "slight_decline": -0.05
    }

    stress_test_results = {}
    current_position_value = current_stock_value

    for scenario, decline in stress_test_scenarios.items():
        potential_loss = current_position_value * decline
        portfolio_impact = potential_loss / (portfolio['cash'] + current_position_value) if (portfolio['cash'] + current_position_value) != 0 else math.nan
        stress_test_results[scenario] = {
            "potential_loss": potential_loss,
            "portfolio_impact": portfolio_impact
        }

    # 5. Risk-Adjusted Signals Analysis
    # Convert all confidences to numeric for proper comparison
    def parse_confidence(conf_str):
        return float(conf_str.replace('%', '')) / 100.0
    low_confidence = any(parse_confidence(signal['confidence']) < 0.30 for signal in agent_signals.values())

    # Check the diversity of signals. If all three differ, add to risk score
    # (signal divergence can be seen as increased uncertainty)
    unique_signals = set(signal['signal'] for signal in agent_signals.values())
    signal_divergence = (2 if len(unique_signals) == 3 else 0)

    risk_score = (market_risk_score * 2)  # Market risk contributes up to ~6 points total when doubled
    if low_confidence:
        risk_score += 4  # Add penalty if any signal confidence < 30%
    risk_score += signal_divergence

    # Cap risk score at 10
    risk_score = min(round(risk_score), 10)

    # 6. Generate Trading Action
    # If risk is very high, hold. If moderately high, consider reducing.
    # Else, follow valuation signal as a baseline.
    if risk_score >= 8:
        trading_action = "hold"
    elif risk_score >= 6:
        trading_action = "reduce"
    else:
        trading_action = agent_signals['valuation']['signal']

    message_content = {
        "max_position_size": float(max_position_size),
        "risk_score": risk_score,
        "trading_action": trading_action,
        "risk_metrics": {
            "volatility": float(volatility),
            "value_at_risk_95": float(var_95),
            "max_drawdown": float(max_drawdown),
            "market_risk_score": market_risk_score,
            "stress_test_results": stress_test_results
        },
        "reasoning": f"Risk Score {risk_score}/10: Market Risk={market_risk_score}, "
                     f"Volatility={volatility:.2%}, VaR={var_95:.2%}, "
                     f"Max Drawdown={max_drawdown:.2%}"
    }

    # Create the risk management message
    message = HumanMessage(
        content=json.dumps(message_content),
        name="risk_management_agent",
    )

    if show_reasoning:
        show_agent_reasoning(message_content, "Risk Management Agent")

    return {"messages": state["messages"] + [message]}

