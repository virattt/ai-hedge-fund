import json
from datetime import datetime, timedelta

# Simple class to mimic the EnhancedAgentState functionality for dot notation access
class DotDict:
    def __init__(self, data=None):
        if data is None:
            data = {}
        self._data = data
        for key, value in data.items():
            if isinstance(value, dict):
                setattr(self, key, DotDict(value))
            else:
                setattr(self, key, value)
    
    def __getattr__(self, key):
        if key.startswith('_'):
            return super().__getattr__(key)
        return None
    
    def __getitem__(self, key):
        # Support dictionary-like access with square brackets
        if isinstance(self._data, dict) and key in self._data:
            item = self._data[key]
            if isinstance(item, dict):
                return DotDict(item)
            return item
        raise KeyError(key)
    
    def to_dict(self):
        return self._data


class EnhancedAgentState:
    """
    Simplified version of EnhancedAgentState for demonstration purposes.
    Provides dot notation access to nested dictionary data.
    """
    def __init__(self, state_dict):
        self._state = state_dict
        for key, value in state_dict.items():
            if isinstance(value, dict):
                setattr(self, key, DotDict(value))
            else:
                setattr(self, key, value)
    
    def to_dict(self):
        return self._state


# Add strategy accessor method to DotDict for portfolio
setattr(DotDict, 'strategy', lambda self, idx: DotDict(self._data['strategies'][idx]) if 'strategies' in self._data and idx < len(self._data['strategies']) else None)


def create_basic_state():
    """
    Create a basic state dictionary
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    prev_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    basic_state = {
        "data": {
            "date": current_date,
            "watchlist": ["SPY", "QQQ", "AAPL"],
            "profile": {
                "max_daily_drawdown": 0.02,
                "max_size_position": 0.05,
                "management_style": 2  # moderate
            },
            "market_conditions": {
                "spx": 5200.0,
                "vix": 15.5,
                "ivr": 45,
                "trend": "bullish"
            },
            "portfolio": {
                "net_liquidation_value": 100000.0,
                "cash": 25000.0,
                "margin_used": 15000.0,
                "max_margin": 50000.0,
                "beta_weighted_delta": 0.35,
                "pnl": 2500.0,
                "pnl_percent": 2.5,
                "pnl_history": {
                    week_ago: 1200.0,
                    prev_date: 2100.0,
                    current_date: 2500.0
                },
                "strategies": [
                    {
                        "ticker": "SPY",
                        "asset_class": "equity",
                        "description": "SPY Iron Condor",
                        "price": 470.0,
                        "ivr": 40,
                        "beta": 1.0,
                        "premium": -1500.0,  # Negative for credit, positive for debit
                        "date": current_date,
                        "assumptions": {
                            "underlying_direction": "neutral",
                            "volatility_direction": "decreasing",
                            "days_to_expiry": 45
                        },
                        "risk_profile": {
                            "risk_category": "defined",
                            "margin": 1000.0,
                            "expected_delta_move": 0.15,
                            "expected_convexity_move": 0.05,
                            "CVaR": 950.0
                        },
                        "pnl": 350.0,
                        "pnl_percent": 23.3,  # As percentage of premium
                        "pnl_history": {
                            week_ago: 120.0,
                            prev_date: 280.0,
                            current_date: 350.0
                        },
                        "survival_probabilities": {
                            "prob_profit_10_percent": 0.75,
                            "prob_profit_25_percent": 0.60,
                            "prob_profit_50_percent": 0.35
                        },
                        "number_of_contracts": 2,
                        "legs": [
                            {
                                "id": "SPY_C_480",
                                "description": "SPY 480 Call (Short)",
                                "type": "option",
                                "position_type": "short",
                                "call": 1,
                                "expiry": "2025-05-15",
                                "strike": 480.0,
                                "cost_basis": -2.50,  # Negative for credit received
                                "position_size": -2,  # Negative for short
                                "multiplier": 100,
                                "greeks": {
                                    "delta": -0.30,
                                    "gamma": -0.02,
                                    "theta": 0.15,
                                    "vega": -0.25
                                }
                            },
                            {
                                "id": "SPY_C_490",
                                "description": "SPY 490 Call (Long)",
                                "type": "option",
                                "position_type": "long",
                                "call": 1,
                                "expiry": "2025-05-15",
                                "strike": 490.0,
                                "cost_basis": 1.25,  # Positive for debit paid
                                "position_size": 2,  # Positive for long
                                "multiplier": 100,
                                "greeks": {
                                    "delta": 0.20,
                                    "gamma": 0.015,
                                    "theta": -0.10,
                                    "vega": 0.20
                                }
                            },
                            {
                                "id": "SPY_P_460",
                                "description": "SPY 460 Put (Short)",
                                "type": "option",
                                "position_type": "short",
                                "call": 0,
                                "expiry": "2025-05-15",
                                "strike": 460.0,
                                "cost_basis": -2.25,  # Negative for credit received
                                "position_size": -2,  # Negative for short
                                "multiplier": 100,
                                "greeks": {
                                    "delta": 0.25,
                                    "gamma": -0.02,
                                    "theta": 0.12,
                                    "vega": -0.22
                                }
                            },
                            {
                                "id": "SPY_P_450",
                                "description": "SPY 450 Put (Long)",
                                "type": "option",
                                "position_type": "long",
                                "call": 0,
                                "expiry": "2025-05-15",
                                "strike": 450.0,
                                "cost_basis": 1.00,  # Positive for debit paid
                                "position_size": 2,  # Positive for long
                                "multiplier": 100,
                                "greeks": {
                                    "delta": -0.15,
                                    "gamma": 0.01,
                                    "theta": -0.08,
                                    "vega": 0.18
                                }
                            }
                        ]
                    },
                    {
                        "ticker": "AAPL",
                        "asset_class": "equity",
                        "description": "AAPL Covered Call",
                        "price": 210.0,
                        "ivr": 35,
                        "beta": 1.2,
                        "premium": 350.0,  # Positive for debit (stock purchase)
                        "date": current_date,
                        "assumptions": {
                            "underlying_direction": "bullish",
                            "volatility_direction": "stable",
                            "days_to_expiry": 30
                        },
                        "risk_profile": {
                            "risk_category": "undefined",
                            "margin": 21000.0,
                            "expected_delta_move": 0.25,
                            "expected_convexity_move": 0.02,
                            "CVaR": 1800.0
                        },
                        "pnl": 450.0,
                        "pnl_percent": 2.1,  # As percentage of position value
                        "pnl_history": {
                            week_ago: 180.0,
                            prev_date: 320.0,
                            current_date: 450.0
                        },
                        "survival_probabilities": {
                            "prob_profit_10_percent": 0.65,
                            "prob_profit_25_percent": 0.40,
                            "prob_profit_50_percent": 0.20
                        },
                        "number_of_contracts": 1,
                        "legs": [
                            {
                                "id": "AAPL_STOCK",
                                "description": "AAPL Stock",
                                "type": "stock",
                                "position_type": "long",
                                "cost_basis": 205.0,
                                "position_size": 100,
                                "multiplier": 1,
                                "greeks": {
                                    "delta": 1.0,
                                    "gamma": 0.0,
                                    "theta": 0.0,
                                    "vega": 0.0
                                }
                            },
                            {
                                "id": "AAPL_C_220",
                                "description": "AAPL 220 Call (Short)",
                                "type": "option",
                                "position_type": "short",
                                "call": 1,
                                "expiry": "2025-05-01",
                                "strike": 220.0,
                                "cost_basis": -3.50,  # Negative for credit received
                                "position_size": -1,  # Negative for short
                                "multiplier": 100,
                                "greeks": {
                                    "delta": -0.35,
                                    "gamma": -0.03,
                                    "theta": 0.18,
                                    "vega": -0.30
                                }
                            }
                        ]
                    }
                ]
            },
            "analyst_signals": {
                "portfolio_metrics_agent": {
                    "strategy_metrics": {
                        "SPY": {
                            "pnl_attribution": {
                                "delta": 120.0,
                                "gamma": 45.0,
                                "theta": 180.0,
                                "vega": -25.0,
                                "other": 30.0
                            }
                        },
                        "AAPL": {
                            "pnl_attribution": {
                                "delta": 380.0,
                                "gamma": 20.0,
                                "theta": 65.0,
                                "vega": -35.0,
                                "other": 20.0
                            }
                        }
                    }
                }
            }
        },
        "metadata": {
            "show_reasoning": True
        }
    }
    
    return basic_state


def calculate_portfolio_cvar(portfolio, expected_daily_move=0.02):
    """
    Calculate the portfolio-level Conditional Value at Risk (CVaR).
    
    This is a simplified implementation that can be replaced with a more sophisticated
    model in the future (e.g., using historical simulation, Monte Carlo simulation,
    or parametric methods).
    
    Args:
        portfolio: Portfolio object containing strategies
        expected_daily_move: Expected daily move of the market (default: 2%)
        
    Returns:
        float: Portfolio CVaR value
    """
    # Initialize the total CVaR
    portfolio_cvar = 0.0
    
    # Get the total portfolio value
    portfolio_value = getattr(portfolio, 'net_liquidation_value', 0) if hasattr(portfolio, 'net_liquidation_value') else portfolio.get('net_liquidation_value', 0)
    
    # Get the strategies list
    strategies = getattr(portfolio, 'strategies', []) if hasattr(portfolio, 'strategies') else portfolio.get('strategies', [])
    
    # Calculate the weighted sum of strategy CVaRs
    # In a real implementation, this would account for correlations between strategies
    for strategy in strategies:
        # Get the strategy weight in the portfolio
        # For simplicity, we'll use equal weights
        strategy_weight = 1.0 / len(strategies) if strategies else 0
        
        # Get the strategy CVaR
        strategy_cvar = 0.0
        
        # Handle both object and dictionary access patterns
        if isinstance(strategy, dict):
            if 'risk_profile' in strategy and isinstance(strategy['risk_profile'], dict):
                strategy_cvar = strategy['risk_profile'].get('CVaR', 0)
        else:
            if hasattr(strategy, 'risk_profile') and hasattr(strategy.risk_profile, 'CVaR'):
                strategy_cvar = strategy.risk_profile.CVaR
        
        # Add the weighted strategy CVaR to the portfolio CVaR
        portfolio_cvar += strategy_weight * strategy_cvar
    
    # Apply a diversification benefit
    # In a real implementation, this would be calculated based on correlations
    diversification_benefit = 0.85  # Assume 15% diversification benefit
    portfolio_cvar *= diversification_benefit
    
    return portfolio_cvar


def calculate_marginal_contribution_to_risk(portfolio, strategy_cvars, portfolio_cvar):
    """
    Calculate the marginal contribution to risk (MCR) for each strategy in the portfolio.
    
    MCR measures how much each strategy contributes to the overall portfolio risk.
    It's useful for risk budgeting and identifying which strategies are adding the most risk.
    
    This is a simplified implementation that can be replaced with a more sophisticated
    model in the future (e.g., using component VaR or expected shortfall).
    
    Args:
        portfolio: Portfolio object containing strategies
        strategy_cvars: Dictionary of strategy CVaRs
        portfolio_cvar: Total portfolio CVaR
        
    Returns:
        dict: Dictionary of marginal contributions to risk for each strategy
    """
    # Initialize the result dictionary
    mcr_dict = {}
    
    # Get the strategies list
    strategies = getattr(portfolio, 'strategies', []) if hasattr(portfolio, 'strategies') else portfolio.get('strategies', [])
    
    # For simplicity, we'll use equal weights for all strategies
    strategy_weights = {}
    for strategy in strategies:
        # Handle both object and dictionary access patterns
        if isinstance(strategy, dict):
            strategy_id = strategy.get('id', f"strategy_{id(strategy)}")
        else:
            strategy_id = getattr(strategy, 'id', f"strategy_{id(strategy)}")
            
        strategy_weights[strategy_id] = 1.0 / len(strategies) if strategies else 0
    
    # Calculate the marginal contribution to risk for each strategy
    for strategy in strategies:
        # Handle both object and dictionary access patterns
        if isinstance(strategy, dict):
            strategy_id = strategy.get('id', f"strategy_{id(strategy)}")
        else:
            strategy_id = getattr(strategy, 'id', f"strategy_{id(strategy)}")
            
        if strategy_id in strategy_cvars and portfolio_cvar > 0:
            # MCR = strategy_weight * strategy_cvar / portfolio_cvar
            # This is a simplified formula that assumes independence between strategies
            # A more sophisticated approach would account for correlations between strategies
            mcr = strategy_weights[strategy_id] * strategy_cvars[strategy_id] / portfolio_cvar
            mcr_dict[strategy_id] = mcr
        else:
            mcr_dict[strategy_id] = 0
    
    return mcr_dict


def calculate_portfolio_risk_metrics(enhanced_state):
    """
    Calculate portfolio risk metrics including CVaR and marginal contribution to risk.
    
    This function serves as a modular entry point for risk calculations that can be
    replaced with more sophisticated implementations in the future.
    
    Args:
        enhanced_state: EnhancedAgentState containing the portfolio data
        
    Returns:
        tuple: (portfolio_cvar, mcr_dict) - The calculated portfolio CVaR and marginal contributions
    """
    # Access the portfolio data
    portfolio = enhanced_state.data.portfolio
    
    # Calculate portfolio CVaR
    portfolio_cvar = calculate_portfolio_cvar(portfolio)
    
    # Store the CVaR in the portfolio model
    # Handle both object and dictionary access patterns
    if hasattr(portfolio, 'CVaR'):
        portfolio.CVaR = portfolio_cvar
    elif isinstance(portfolio, dict):
        portfolio['CVaR'] = portfolio_cvar
    
    # Get the strategies list
    strategies = getattr(portfolio, 'strategies', []) if hasattr(portfolio, 'strategies') else portfolio.get('strategies', [])
    
    # Calculate strategy CVaRs
    strategy_cvars = {}
    for strategy in strategies:
        # Handle both object and dictionary access patterns
        if isinstance(strategy, dict):
            strategy_id = strategy.get('id', f"strategy_{id(strategy)}")
            strategy_cvar = 0
            if 'risk_profile' in strategy and isinstance(strategy['risk_profile'], dict):
                strategy_cvar = strategy['risk_profile'].get('CVaR', 0)
        else:
            strategy_id = getattr(strategy, 'id', f"strategy_{id(strategy)}")
            strategy_cvar = 0
            if hasattr(strategy, 'risk_profile') and hasattr(strategy.risk_profile, 'CVaR'):
                strategy_cvar = strategy.risk_profile.CVaR
                
        strategy_cvars[strategy_id] = strategy_cvar
    
    # Calculate marginal contribution to risk and store it in each strategy's risk profile
    for strategy in strategies:
        # Handle both object and dictionary access patterns
        if isinstance(strategy, dict):
            strategy_id = strategy.get('id', f"strategy_{id(strategy)}")
            # Calculate a simple MCR (equal weight for this example)
            mcr = 1.0 / len(strategies) if len(strategies) > 0 else 0
            
            # Store in risk profile
            if 'risk_profile' in strategy:
                if isinstance(strategy['risk_profile'], dict):
                    strategy['risk_profile']['marginal_contribution_to_risk'] = mcr
        else:
            strategy_id = getattr(strategy, 'id', f"strategy_{id(strategy)}")
            # Calculate a simple MCR (equal weight for this example)
            mcr = 1.0 / len(strategies) if len(strategies) > 0 else 0
            
            # Store in risk profile
            if hasattr(strategy, 'risk_profile'):
                strategy.risk_profile.marginal_contribution_to_risk = mcr
    
    # For compatibility, still return a dictionary of MCRs
    mcr_dict = {}
    for strategy in strategies:
        if isinstance(strategy, dict):
            strategy_id = strategy.get('id', f"strategy_{id(strategy)}")
            if 'risk_profile' in strategy and isinstance(strategy['risk_profile'], dict):
                mcr = strategy['risk_profile'].get('marginal_contribution_to_risk', 0)
                mcr_dict[strategy_id] = mcr
        else:
            strategy_id = getattr(strategy, 'id', f"strategy_{id(strategy)}")
            if hasattr(strategy, 'risk_profile'):
                mcr = getattr(strategy.risk_profile, 'marginal_contribution_to_risk', 0)
                mcr_dict[strategy_id] = mcr
    
    return portfolio_cvar, mcr_dict


def display_portfolio_risk_metrics(portfolio, strategy=None):
    """
    Display portfolio risk metrics including CVaR and marginal contribution to risk.
    
    Args:
        portfolio: Portfolio object containing risk metrics
        strategy: Optional specific strategy to display metrics for
        
    Returns:
        None (prints to console)
    """
    # Display portfolio CVaR
    portfolio_cvar = None
    if hasattr(portfolio, 'CVaR'):
        portfolio_cvar = portfolio.CVaR
    elif isinstance(portfolio, dict):
        portfolio_cvar = portfolio.get('CVaR')
        
    if portfolio_cvar:
        print(f"Portfolio CVaR: ${portfolio_cvar:,.2f}")
    
    # If a specific strategy is provided, display its marginal contribution to risk
    if strategy:
        risk_profile = None
        if isinstance(strategy, dict) and 'risk_profile' in strategy:
            risk_profile = strategy['risk_profile']
        elif hasattr(strategy, 'risk_profile'):
            risk_profile = strategy.risk_profile
            
        if risk_profile:
            mcr = 0.0
            if isinstance(risk_profile, dict):
                mcr = risk_profile.get('marginal_contribution_to_risk', 0.0)
            else:
                mcr = getattr(risk_profile, 'marginal_contribution_to_risk', 0.0)
                
            mcr_percent = mcr * 100
            print(f"Marginal contribution to portfolio risk: {mcr_percent:.2f}%")
    else:
        # Display MCR for all strategies
        print("\nMarginal Contribution to Risk:")
        for i, strategy in enumerate(portfolio.strategies):
            strategy_description = strategy.get('description', f'Strategy {i+1}') if isinstance(strategy, dict) else getattr(strategy, 'description', f'Strategy {i+1}')
            
            risk_profile = None
            if isinstance(strategy, dict) and 'risk_profile' in strategy:
                risk_profile = strategy['risk_profile']
            elif hasattr(strategy, 'risk_profile'):
                risk_profile = strategy.risk_profile
                
            if risk_profile:
                mcr = 0.0
                if isinstance(risk_profile, dict):
                    mcr = risk_profile.get('marginal_contribution_to_risk', 0.0)
                else:
                    mcr = getattr(risk_profile, 'marginal_contribution_to_risk', 0.0)
                    
                mcr_percent = mcr * 100
                print(f"  {strategy_description}: {mcr_percent:.2f}%")
    

def example_usage():
    """
    Example usage of the enhanced agent state.
    """
    # Create a basic state
    basic_state = create_basic_state()
    
    # Convert to enhanced state for structured access
    enhanced_state = EnhancedAgentState(basic_state)
    
    # Calculate portfolio risk metrics
    portfolio_cvar, mcr_dict = calculate_portfolio_risk_metrics(enhanced_state)
    
    # Now we can access data using dot notation
    portfolio = enhanced_state.data.portfolio
    print(f"Portfolio value: ${portfolio.net_liquidation_value:,.2f}")
    print(f"Portfolio P&L: ${portfolio.pnl:,.2f} ({portfolio.pnl_percent:.1f}%)")
    
    # Display portfolio risk metrics
    display_portfolio_risk_metrics(portfolio)
    print()
    
    # Print strategy information
    for i, strategy in enumerate(portfolio.strategies):
        # Handle both object and dictionary access patterns
        strategy_description = strategy.get('description', 'Unknown') if isinstance(strategy, dict) else getattr(strategy, 'description', 'Unknown')
        strategy_ticker = strategy.get('ticker', 'Unknown') if isinstance(strategy, dict) else getattr(strategy, 'ticker', 'Unknown')
        strategy_pnl = strategy.get('pnl', 0.0) if isinstance(strategy, dict) else getattr(strategy, 'pnl', 0.0)
        strategy_pnl_percent = strategy.get('pnl_percent', 0.0) if isinstance(strategy, dict) else getattr(strategy, 'pnl_percent', 0.0)
        
        print(f"Strategy {i+1}: {strategy_description} on {strategy_ticker}")
        print(f"Strategy P&L: ${strategy_pnl:,.2f} ({strategy_pnl_percent:.1f}%)")
        
        # Print risk metrics
        risk_profile = None
        if isinstance(strategy, dict) and 'risk_profile' in strategy:
            risk_profile = strategy['risk_profile']
        elif hasattr(strategy, 'risk_profile'):
            risk_profile = strategy.risk_profile
            
        if risk_profile:
            risk_category = risk_profile.get('risk_category', 'undefined') if isinstance(risk_profile, dict) else getattr(risk_profile, 'risk_category', 'undefined')
            expected_delta_move = risk_profile.get('expected_delta_move', 0) if isinstance(risk_profile, dict) else getattr(risk_profile, 'expected_delta_move', 0)
            cvar = risk_profile.get('CVaR', 0) if isinstance(risk_profile, dict) else getattr(risk_profile, 'CVaR', 0)
            mcr = risk_profile.get('marginal_contribution_to_risk', 0) if isinstance(risk_profile, dict) else getattr(risk_profile, 'marginal_contribution_to_risk', 0)
            
            print(f"Risk category: {risk_category}")
            print(f"Expected delta move: {expected_delta_move:.2f}")
            print(f"CVaR: ${cvar:,.2f}")
            print(f"Marginal contribution to portfolio risk: {mcr*100:.2f}%")
            
            # Display marginal contribution to risk for this strategy
            display_portfolio_risk_metrics(portfolio, strategy)
    
    # Access the first strategy
    strategy = portfolio.strategy(0)
    print(f"\nStrategy 1: {strategy.description} on {strategy.ticker}")
    print(f"Strategy P&L: ${strategy.pnl:,.2f} ({strategy.pnl_percent:.1f}%)")
    print(f"Survival probabilities:")
    print(f"  10% profit: {strategy.survival_probabilities.prob_profit_10_percent:.2f}")
    print(f"  25% profit: {strategy.survival_probabilities.prob_profit_25_percent:.2f}")
    print(f"  50% profit: {strategy.survival_probabilities.prob_profit_50_percent:.2f}")
    
    # Access P&L attribution
    attribution = enhanced_state.data.analyst_signals.portfolio_metrics_agent.strategy_metrics["SPY"].pnl_attribution
    print(f"\nP&L Attribution for {strategy.ticker}:")
    print(f"  Delta: ${attribution['delta']:,.2f}")
    print(f"  Gamma: ${attribution['gamma']:,.2f}")
    print(f"  Theta: ${attribution['theta']:,.2f}")
    print(f"  Vega: ${attribution['vega']:,.2f}")
    print(f"  Other: ${attribution['other']:,.2f}")
    
    # Access the second strategy
    strategy2 = portfolio.strategy(1)
    print(f"\nStrategy 2: {strategy2.description} on {strategy2.ticker}")
    print(f"Strategy P&L: ${strategy2.pnl:,.2f} ({strategy2.pnl_percent:.1f}%)")
    
    # Access risk profile
    risk_profile = strategy2.risk_profile
    print(f"Risk category: {risk_profile.risk_category}")
    print(f"Expected delta move: {risk_profile.expected_delta_move}")
    print(f"CVaR: ${risk_profile.CVaR:,.2f}")
    print(f"Marginal contribution to portfolio risk: {risk_profile.marginal_contribution_to_risk*100:.2f}%")
    
    # Access the legs
    print(f"\nStrategy legs:")
    for i, leg_dict in enumerate(strategy2._data["legs"]):
        leg = DotDict(leg_dict)
        print(f"Leg {i+1}: {leg.description}, Type: {leg.type}, Position: {leg.position_size}")
        if "strike" in leg_dict:
            print(f"  Strike: ${leg.strike:.2f}, Expiry: {leg.expiry}")
        print(f"  Cost basis: ${leg.cost_basis:.2f}, Delta: {leg.greeks.delta:.2f}")
    
    # Make changes to the data
    enhanced_state.data.portfolio.cash = 30000.0
    strategy.risk_profile.expected_delta_move = 0.18
    strategy.pnl = 400.0  # Update P&L
    
    # Convert back to dictionary format
    updated_dict = enhanced_state.to_dict()
    print("\nUpdated state as dictionary:")
    print(json.dumps(updated_dict["data"]["portfolio"]["cash"], indent=2))
    print(json.dumps(updated_dict["data"]["portfolio"]["strategies"][0]["risk_profile"], indent=2))
    print(json.dumps(updated_dict["data"]["portfolio"]["strategies"][0]["pnl"], indent=2))
    
    print("\n\n=== Demonstrating Market Data Service with Risk Calculator ===")
    print("This example shows how real market data is used for P&L calculations")
    
    # Import necessary modules
    import sys
    import os
    # Add the src directory to the path so we can import from services
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from services.market_data import get_market_data_for_strategy
    from risk_calculator import format_market_data_for_pnl, calculate_strategy_pnl
    
    # Get the second strategy from our example (AAPL Covered Call)
    strategy = enhanced_state.data.portfolio.strategy(1)
    print(f"\nStrategy: {strategy.description} on {strategy.ticker}")
    
    # Get raw market data from the market data service
    market_data = get_market_data_for_strategy(strategy)
    print("\nRaw Market Data from Service:")
    print(f"  Ticker: {market_data['ticker']}")
    print(f"  Date: {market_data['date']}")
    if 'underlying' in market_data and market_data['underlying']:
        print(f"  Current Price: ${market_data['underlying'].get('current_price', 'N/A')}")
        print(f"  Previous Price: ${market_data['underlying'].get('previous_price', 'N/A')}")
    
    # Print the structure of the options data
    print("\nOptions Data Structure:")
    if 'options' in market_data:
        print(f"  Options Type: {type(market_data['options'])}")
        if isinstance(market_data['options'], dict):
            print(f"  Options Keys: {market_data['options'].keys()}")
        elif isinstance(market_data['options'], list):
            print(f"  Options Count: {len(market_data['options'])}")
            if len(market_data['options']) > 0:
                print(f"  First Option Type: {type(market_data['options'][0])}")
                if isinstance(market_data['options'][0], dict):
                    print(f"  First Option Keys: {market_data['options'][0].keys()}")
    else:
        print("  No options data available")
    
    # Format the market data for P&L calculations
    formatted_data = format_market_data_for_pnl(market_data, strategy)
    print("\nFormatted Data for P&L Calculations:")
    print(f"  Underlying Price: ${formatted_data['underlying_price']:.2f}")
    print(f"  Previous Underlying Price: ${formatted_data['prev_underlying_price']:.2f}")
    print(f"  Days Passed: {formatted_data['days_passed']}")
    print(f"  Number of Legs: {len(formatted_data['legs_data'])}")
    
    # Display detailed information for the first leg
    if formatted_data['legs_data']:
        first_leg = formatted_data['legs_data'][0]
        print("\nSample Leg Data (First Leg):")
        print(f"  ID: {first_leg['id']}")
        print(f"  Type: {first_leg['type']}")
        print(f"  Position Size: {first_leg['position_size']}")
        print(f"  Cost Basis: ${first_leg['cost_basis']:.2f}")
        if first_leg['current_price'] is not None:
            print(f"  Current Market Price: ${first_leg['current_price']:.2f}")
        if first_leg['greeks']:
            print("  Greeks:")
            for greek, value in first_leg['greeks'].items():
                print(f"    {greek.capitalize()}: {value:.4f}")
    
    # Calculate P&L using real market data
    pnl, pnl_percent, attribution = calculate_strategy_pnl(strategy)
    print("\nCalculated P&L (Based on Real Market Data):")
    print(f"  Total P&L: ${pnl:.2f}")
    print(f"  P&L Percent: {pnl_percent:.2f}%")
    print("\nP&L Attribution:")
    for component, value in attribution.items():
        print(f"  {component.capitalize()}: ${value:.2f}")
    
    print("\nThis demonstrates how real market data is used for P&L calculations.")
    print("The market data service provides raw data that is then formatted by the risk calculator.")
    print("P&L is calculated based on actual market prices rather than assumptions.")
    
    # Print the whole state at the end of the example
    print("\n=== Complete State ===")
    # Convert the state to a dictionary and print it
    state_dict = enhanced_state.to_dict()
    print(json.dumps(state_dict, indent=2, default=str))
    
    return enhanced_state


if __name__ == "__main__":
    # Run the example
    enhanced_state = example_usage()
