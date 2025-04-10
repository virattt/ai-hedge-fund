#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Portfolio Risk Dashboard Example

This example demonstrates how to use the portfolio_metrics_agent in a LangChain graph
to calculate and visualize risk metrics for a portfolio.
"""

import os
import sys
import math
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from matplotlib.gridspec import GridSpec
import gc  # Add garbage collection
from memory_profiler import profile  # Add memory profiling

# Add the src directory to the path so we can import modules as they expect
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'src'))

# Import with the structure expected by the project modules
from new_graph.state import AgentState, EnhancedAgentState
from new_models.portfolio import ExpectedDailyMove, RiskProfile
from new_agents.portfolio_metrics_agent import portfolio_metrics_agent

# Set up plotting style - reduce default figure size to save memory
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (10, 8)  # Reduced from (14, 10)
plt.rcParams['font.size'] = 12


def initialize_agent_state():
    """
    Initialize the agent state with a sample portfolio and market conditions.
    """
    # Create a dictionary-based state that mimics the structure expected by the portfolio_metrics_agent
    state = AgentState(
        data={
            "portfolio": {
                "net_liquidation_value": 100000,
                "cash": 20000,
                "margin_used": 30000,
                "max_margin": 80000,
                "total_beta_weighted_delta": 0,
                "total_beta_weighted_gamma": 0,
                "theta": 0,
                "pnl": 0,
                "pnl_percent": 0,
                "expected_daily_move": {
                    "directional_exposure": 0,
                    "convexity_exposure": 0,
                    "time_decay": 0,
                    "volatility_exposure": 0
                },
                "strategies": [
                    {
                        "ticker": "SPX",
                        "asset_class": "equity",
                        "description": "SPX Iron Condor",
                        "beta": 1.0,
                        "premium": 1500,
                        "price": 4700,
                        "pnl": 0,
                        "risk_profile": {
                            "risk_category": "defined",
                            "margin": 12000,
                            "expected_delta_move": 0,
                            "expected_convexity_move": 0,
                            "CVaR": 2000,
                            "marginal_contribution_to_risk": 0,
                            "survival_probability_10": 0.8,
                            "survival_probability_25": 0.6,
                            "survival_probability_50": 0.4
                        },
                        "assumptions": {
                            "underlying_direction": "neutral",
                            "volatility_direction": "neutral"
                        },
                        "legs": [
                            {
                                "id": "SPX_SC_4800",
                                "description": "SPX Short Call 4800",
                                "type": "option",
                                "strike": 4800,
                                "expiry": "2025-05-15",
                                "call": -1,
                                "put": 0,
                                "multiplier": 100,
                                "cost_basis": -500,
                                "greeks": {
                                    "delta": -0.30,
                                    "gamma": 0.01,
                                    "theta": -1.5,
                                    "vega": 0.8
                                }
                            },
                            {
                                "id": "SPX_LC_4850",
                                "description": "SPX Long Call 4850",
                                "type": "option",
                                "strike": 4850,
                                "expiry": "2025-05-15",
                                "call": 1,
                                "put": 0,
                                "multiplier": 100,
                                "cost_basis": 300,
                                "greeks": {
                                    "delta": 0.25,
                                    "gamma": 0.008,
                                    "theta": -1.2,
                                    "vega": 0.7
                                }
                            },
                            {
                                "id": "SPX_SP_4600",
                                "description": "SPX Short Put 4600",
                                "type": "option",
                                "strike": 4600,
                                "expiry": "2025-05-15",
                                "call": 0,
                                "put": -1,
                                "multiplier": 100,
                                "cost_basis": -450,
                                "greeks": {
                                    "delta": 0.30,
                                    "gamma": 0.01,
                                    "theta": -1.5,
                                    "vega": 0.8
                                }
                            },
                            {
                                "id": "SPX_LP_4550",
                                "description": "SPX Long Put 4550",
                                "type": "option",
                                "strike": 4550,
                                "expiry": "2025-05-15",
                                "call": 0,
                                "put": 1,
                                "multiplier": 100,
                                "cost_basis": 250,
                                "greeks": {
                                    "delta": -0.25,
                                    "gamma": 0.008,
                                    "theta": -1.2,
                                    "vega": 0.7
                                }
                            }
                        ]
                    },
                    {
                        "ticker": "QQQ",
                        "asset_class": "equity",
                        "description": "QQQ Bull Call Spread",
                        "beta": 1.2,
                        "premium": -1200,
                        "price": 400,
                        "pnl": 0,
                        "risk_profile": {
                            "risk_category": "defined",
                            "margin": 8000,
                            "expected_delta_move": 0,
                            "expected_convexity_move": 0,
                            "CVaR": 1500,
                            "marginal_contribution_to_risk": 0,
                            "survival_probability_10": 0.7,
                            "survival_probability_25": 0.5,
                            "survival_probability_50": 0.3
                        },
                        "assumptions": {
                            "underlying_direction": "long",
                            "volatility_direction": "neutral"
                        },
                        "legs": [
                            {
                                "id": "QQQ_LC_400",
                                "description": "QQQ Long Call 400",
                                "type": "option",
                                "strike": 400,
                                "expiry": "2025-06-20",
                                "call": 5,
                                "put": 0,
                                "multiplier": 100,
                                "cost_basis": 2000,
                                "greeks": {
                                    "delta": 0.60,
                                    "gamma": 0.03,
                                    "theta": -0.8,
                                    "vega": 0.5
                                }
                            },
                            {
                                "id": "QQQ_SC_420",
                                "description": "QQQ Short Call 420",
                                "type": "option",
                                "strike": 420,
                                "expiry": "2025-06-20",
                                "call": -5,
                                "put": 0,
                                "multiplier": 100,
                                "cost_basis": -800,
                                "greeks": {
                                    "delta": -0.40,
                                    "gamma": -0.02,
                                    "theta": 0.5,
                                    "vega": -0.3
                                }
                            }
                        ]
                    }
                ]
            },
            "market_conditions": {
                "date": datetime.now().strftime("%Y-%m-%d"),  # Use a string date format
                "spx": 4700,
                "vix": 18.5,
                "vvix": 85,
                "expected_daily_move": 0.0117,  # 1.17% daily move based on VIX
                "market_regime": "normal",
                "interest_rate": 0.0375,
                "yield_curve": "normal"
            }
        },
        metadata={
            "model_name": "gpt-4",
            "model_provider": "openai",
            "show_reasoning": True
        }
    )
    
    # Add market data
    state["data"]["market_data"] = {
        "SPX": {
            "price": 4700,
            "iv": 0.185,
            "beta": 1.0,
            "sector": "index"
        },
        "QQQ": {
            "price": 400,
            "iv": 0.22,
            "beta": 1.2,
            "sector": "technology"
        }
    }
    
    return state


@profile
def run_portfolio_metrics_agent(state):
    """
    Run a simplified version of the portfolio_metrics_agent to calculate all metrics.
    This avoids issues with the agent's assumptions about the data structure.
    """
    print("Running portfolio metrics agent...")
    
    # Convert state to the format expected by the agent
    if isinstance(state, dict):
        agent_state = state
    else:
        agent_state = state._state
    
    # Run the agent to calculate metrics
    updated_state = portfolio_metrics_agent(agent_state)
    
    # Convert back to EnhancedAgentState for easier access
    return EnhancedAgentState(updated_state)


def cleanup_memory():
    """
    Force garbage collection to free memory.
    """
    plt.close('all')  # Close all matplotlib figures
    gc.collect()      # Run garbage collection


@profile
def plot_portfolio_dashboard(enhanced_state):
    """
    Plot a comprehensive dashboard for portfolio risk analysis.
    """
    print("Generating portfolio risk dashboard...")
    
    # Extract data from the enhanced state
    portfolio = enhanced_state.data.portfolio
    market_conditions = enhanced_state.data.market_conditions
    
    # Create a figure with a grid layout
    fig = plt.figure(figsize=(12, 9))  # Reduced size for memory efficiency
    gs = GridSpec(3, 3, figure=fig)
    
    # 1. Portfolio Summary (top left)
    ax1 = fig.add_subplot(gs[0, 0])
    plot_portfolio_summary(ax1, portfolio)
    
    # 2. Risk Allocation (top middle)
    ax2 = fig.add_subplot(gs[0, 1])
    plot_risk_allocation(ax2, portfolio)
    
    # 3. Expected Daily Move (top right)
    ax3 = fig.add_subplot(gs[0, 2])
    plot_expected_daily_move(ax3, portfolio)
    
    # 4. Strategy Risk Profiles (middle row)
    ax4 = fig.add_subplot(gs[1, :])
    plot_strategy_risk_profiles(ax4, portfolio)
    
    # 5. Market Conditions (bottom left)
    ax5 = fig.add_subplot(gs[2, 0])
    plot_market_conditions(ax5, market_conditions)
    
    # 6. Margin Usage (bottom middle)
    ax6 = fig.add_subplot(gs[2, 1])
    plot_margin_usage(ax6, portfolio)
    
    # 7. Survival Probabilities (bottom right)
    ax7 = fig.add_subplot(gs[2, 2])
    plot_survival_probabilities(ax7, portfolio)
    
    plt.tight_layout()
    plt.savefig("portfolio_risk_dashboard.png", dpi=150)  # Save as a file instead of showing
    print("Dashboard saved as portfolio_risk_dashboard.png")
    
    # Clean up to free memory
    plt.close(fig)
    del fig, gs, ax1, ax2, ax3, ax4, ax5, ax6, ax7
    gc.collect()


def plot_portfolio_summary(ax, portfolio):
    """Helper function to plot portfolio summary."""
    data = {
        'Net Liquidation Value': portfolio.net_liquidation_value,
        'Cash': portfolio.cash,
        'Margin Used': portfolio.margin_used,
        'Beta-Weighted Delta': portfolio.total_beta_weighted_delta * 100
    }
    
    # Create a horizontal bar chart
    bars = ax.barh(list(data.keys()), list(data.values()), color='skyblue')
    
    # Add value labels
    for bar in bars:
        width = bar.get_width()
        ax.text(width + 0.5, bar.get_y() + bar.get_height()/2, f'${width:,.0f}' if width > 100 else f'{width:.2f}',
                ha='left', va='center')
    
    ax.set_title('Portfolio Summary')
    ax.set_xlabel('Value ($)')


def plot_risk_allocation(ax, portfolio):
    """Helper function to plot risk allocation."""
    # Extract CVaR values for each strategy
    strategies = portfolio.strategies
    labels = [s.description for s in strategies]
    sizes = [s.risk_profile.CVaR for s in strategies]
    
    # Create a pie chart
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=sns.color_palette("pastel"))
    ax.set_title('Risk Allocation by Strategy (CVaR)')


def plot_expected_daily_move(ax, portfolio):
    """Helper function to plot expected daily move components."""
    edm = portfolio.expected_daily_move
    
    # Data for the chart
    categories = ['Directional', 'Convexity', 'Time Decay', 'Volatility']
    values = [
        edm.directional_exposure,
        edm.convexity_exposure,
        edm.time_decay,
        edm.volatility_exposure
    ]
    
    # Create a horizontal bar chart
    bars = ax.barh(categories, values, color=['#ff9999', '#66b3ff', '#99ff99', '#ffcc99'])
    
    # Add value labels
    for bar in bars:
        width = bar.get_width()
        ax.text(width + 0.5, bar.get_y() + bar.get_height()/2, f'${width:,.0f}',
                ha='left', va='center')
    
    ax.set_title('Expected Daily Move Components')
    ax.set_xlabel('Value ($)')


def plot_strategy_risk_profiles(ax, portfolio):
    """Helper function to plot strategy risk profiles."""
    strategies = portfolio.strategies
    
    # Create data for a grouped bar chart
    labels = [s.description for s in strategies]
    margin_values = [s.risk_profile.margin for s in strategies]
    cvar_values = [s.risk_profile.CVaR for s in strategies]
    
    x = np.arange(len(labels))
    width = 0.35
    
    # Create the bars
    ax.bar(x - width/2, margin_values, width, label='Margin Required')
    ax.bar(x + width/2, cvar_values, width, label='Conditional Value at Risk (CVaR)')
    
    # Add labels and legend
    ax.set_title('Strategy Risk Profiles')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel('Value ($)')
    ax.legend()
    
    # Add value labels
    for i, v in enumerate(margin_values):
        ax.text(i - width/2, v + 100, f'${v:,.0f}', ha='center', va='bottom')
    
    for i, v in enumerate(cvar_values):
        ax.text(i + width/2, v + 100, f'${v:,.0f}', ha='center', va='bottom')


def plot_market_conditions(ax, market_conditions):
    """Helper function to plot market conditions."""
    # Data for the chart
    categories = ['SPX', 'VIX', 'VVIX', 'Daily Move (%)']
    values = [
        market_conditions.spx,
        market_conditions.vix,
        market_conditions.vvix,
        market_conditions.expected_daily_move * 100
    ]
    
    # Create a horizontal bar chart with different colors
    colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99']
    bars = ax.barh(categories, values, color=colors)
    
    # Add value labels
    for bar in bars:
        width = bar.get_width()
        ax.text(width + 0.5, bar.get_y() + bar.get_height()/2, f'{width:,.2f}',
                ha='left', va='center')
    
    ax.set_title('Market Conditions')
    ax.set_xlabel('Value')


def plot_margin_usage(ax, portfolio):
    """Helper function to plot margin usage."""
    # Data for the chart
    used = portfolio.margin_used
    available = portfolio.max_margin - used
    
    # Create a pie chart
    sizes = [used, available]
    labels = [f'Used (${used:,.0f})', f'Available (${available:,.0f})']
    colors = ['#ff9999', '#66b3ff']
    
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors)
    ax.set_title('Margin Usage')


def plot_survival_probabilities(ax, portfolio):
    """Helper function to plot survival probabilities for strategies."""
    strategies = portfolio.strategies
    
    # Data for the chart
    labels = [s.description for s in strategies]
    prob_10 = [s.risk_profile.survival_probability_10 * 100 for s in strategies]
    prob_25 = [s.risk_profile.survival_probability_25 * 100 for s in strategies]
    prob_50 = [s.risk_profile.survival_probability_50 * 100 for s in strategies]
    
    x = np.arange(len(labels))
    width = 0.25
    
    # Create the bars
    ax.bar(x - width, prob_10, width, label='10% Profit')
    ax.bar(x, prob_25, width, label='25% Profit')
    ax.bar(x + width, prob_50, width, label='50% Profit')
    
    # Add labels and legend
    ax.set_title('Strategy Survival Probabilities')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Probability (%)')
    ax.set_ylim(0, 100)
    ax.legend()


@profile
def print_portfolio_summary(enhanced_state):
    """
    Print a summary of portfolio metrics.
    """
    portfolio = enhanced_state.data.portfolio
    market_conditions = enhanced_state.data.market_conditions
    
    print("\n" + "="*50)
    print("PORTFOLIO RISK DASHBOARD SUMMARY")
    print("="*50)
    
    # Fix date access - use current date as fallback
    try:
        date_str = market_conditions.date if hasattr(market_conditions, 'date') else datetime.now().strftime("%Y-%m-%d")
        print(f"\nDate: {date_str}")
    except:
        print(f"\nDate: {datetime.now().strftime('%Y-%m-%d')}")
    
    print(f"SPX: {market_conditions.spx:.2f}")
    print(f"VIX: {market_conditions.vix:.2f}")
    print(f"Expected Daily Move: {market_conditions.expected_daily_move*100:.2f}%")
    
    print("\nPORTFOLIO SUMMARY:")
    print(f"Net Liquidation Value: ${portfolio.net_liquidation_value:,.2f}")
    print(f"Cash: ${portfolio.cash:,.2f}")
    print(f"Margin Used: ${portfolio.margin_used:,.2f} ({portfolio.margin_used/portfolio.max_margin*100:.2f}% of max)")
    print(f"Beta-Weighted Delta: {portfolio.total_beta_weighted_delta*100:.2f}")
    
    print("\nEXPECTED DAILY MOVE BREAKDOWN:")
    edm = portfolio.expected_daily_move
    print(f"Directional Exposure: ${edm.directional_exposure:,.2f}")
    print(f"Convexity Exposure: ${edm.convexity_exposure:,.2f}")
    print(f"Time Decay: ${edm.time_decay:,.2f}")
    print(f"Volatility Exposure: ${edm.volatility_exposure:,.2f}")
    
    print("\nSTRATEGY RISK PROFILES:")
    for strategy in portfolio.strategies:
        print(f"\n{strategy.description} ({strategy.ticker}):")
        print(f"  Margin Required: ${strategy.risk_profile.margin:,.2f}")
        print(f"  CVaR (95%): ${strategy.risk_profile.CVaR:,.2f}")
        print(f"  Survival Probability (10% profit): {strategy.risk_profile.survival_probability_10*100:.2f}%")
        print(f"  Survival Probability (25% profit): {strategy.risk_profile.survival_probability_25*100:.2f}%")
        print(f"  Survival Probability (50% profit): {strategy.risk_profile.survival_probability_50*100:.2f}%")
    
    print("\n" + "="*50)


@profile
def main():
    """
    Main function to run the portfolio risk dashboard example.
    """
    print("Starting Portfolio Risk Dashboard Example...")
    
    # Initialize the agent state
    state = initialize_agent_state()
    
    try:
        # Run the portfolio metrics agent
        enhanced_state = run_portfolio_metrics_agent(state)
        
        # Clean up memory after calculations
        cleanup_memory()
        
        # Print a summary of the portfolio metrics
        print_portfolio_summary(enhanced_state)
        
        # Plot the portfolio dashboard
        plot_portfolio_dashboard(enhanced_state)
        
        # Final cleanup
        cleanup_memory()
        
        print("Portfolio Risk Dashboard Example completed successfully.")
        
    except Exception as e:
        print(f"Error running dashboard: {str(e)}")
        import traceback
        traceback.print_exc()
        # Clean up even if there's an error
        cleanup_memory()


if __name__ == "__main__":
    main()
