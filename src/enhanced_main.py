"""
Enhanced AI Hedge Fund with Trading Universe and Comprehensive Analysis.
Integrates all enhanced features: trading universes, sentiment analysis, 
economic indicators, political signals, and advanced portfolio management.
"""

import sys
import os
import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph
from colorama import Fore, Style, init
import questionary
import argparse
from datetime import datetime
from dateutil.relativedelta import relativedelta
import json

from src.agents.enhanced_portfolio_manager import enhanced_portfolio_management_agent
from src.agents.risk_manager import risk_management_agent
from src.graph.state import AgentState
from src.utils.display import print_trading_output
from src.utils.analysts import ANALYST_ORDER, get_analyst_nodes
from src.utils.progress import progress
from src.llm.models import LLM_ORDER, OLLAMA_LLM_ORDER, get_model_info, ModelProvider
from src.utils.ollama import ensure_ollama_and_model
from src.data.trading_universes import TRADING_UNIVERSES, list_trading_universes

# Load environment variables
load_dotenv()
init(autoreset=True)

# Enhanced universe options with descriptions
UNIVERSE_OPTIONS = [
    ("S&P 500 Universe - Large cap stocks with high liquidity", "sp500"),
    ("High-Volume Tech Stocks - Technology sector focus", "tech"), 
    ("Sector ETFs - Diversified sector rotation", "sector_etf"),
    ("Options Trading Universe - Liquid options markets", "options"),
    ("Conservative Large Cap - Blue-chip dividend stocks", "conservative"),
    ("Aggressive Growth - Tech + Options strategies", "aggressive_growth"),
    ("Balanced Portfolio - S&P 500 + Sector ETFs", "balanced")
]

def get_api_keys_from_env() -> dict:
    """Extract API keys from environment variables"""
    api_keys = {}
    
    # LLM API keys
    for key in ["OPENAI_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY"]:
        if os.getenv(key):
            api_keys[key.lower()] = os.getenv(key)
    
    # Financial data API key
    if os.getenv("FINANCIAL_DATASETS_API_KEY"):
        api_keys["financial_datasets_api_key"] = os.getenv("FINANCIAL_DATASETS_API_KEY")
    
    # Enhanced features API keys
    if os.getenv("FRED_API_KEY"):
        api_keys["fred_api_key"] = os.getenv("FRED_API_KEY")
    
    if os.getenv("NEWSAPI_KEY"):
        api_keys["newsapi_key"] = os.getenv("NEWSAPI_KEY")
    
    if os.getenv("REDDIT_API_KEY"):
        api_keys["reddit_key"] = os.getenv("REDDIT_API_KEY")
    
    if os.getenv("TWITTER_API_KEY"):
        api_keys["twitter_key"] = os.getenv("TWITTER_API_KEY")
    
    return api_keys

def check_enhanced_features_availability(api_keys: dict) -> dict:
    """Check which enhanced features are available based on API keys"""
    features = {
        "economic_indicators": bool(api_keys.get("fred_api_key")),
        "political_signals": bool(api_keys.get("newsapi_key")),
        "social_sentiment": bool(api_keys.get("reddit_key") or api_keys.get("twitter_key")),
        "financial_data": bool(api_keys.get("financial_datasets_api_key")),
        "basic_features": True  # Always available with free data
    }
    return features

def display_feature_status(features: dict):
    """Display status of enhanced features"""
    print(f"\n{Fore.CYAN}📊 Enhanced Features Status:{Style.RESET_ALL}")
    
    status_icon = lambda available: f"{Fore.GREEN}✅" if available else f"{Fore.YELLOW}⚠️"
    
    print(f"  {status_icon(features['basic_features'])} Basic Analysis (Free AAPL, GOOGL, MSFT, NVDA, TSLA data)")
    print(f"  {status_icon(features['economic_indicators'])} Economic Indicators (FRED API)")
    print(f"  {status_icon(features['political_signals'])} Political Signals (NewsAPI)")
    print(f"  {status_icon(features['social_sentiment'])} Social Sentiment (Reddit/Twitter API)")
    print(f"  {status_icon(features['financial_data'])} Extended Financial Data (Financial Datasets API)")
    
    if not all(features.values()):
        print(f"\n{Fore.YELLOW}💡 To enable all features, add these API keys to your .env file:{Style.RESET_ALL}")
        if not features['economic_indicators']:
            print("  FRED_API_KEY=your_fred_api_key (free from https://fred.stlouisfed.org/docs/api/)")
        if not features['political_signals']:
            print("  NEWSAPI_KEY=your_newsapi_key (from https://newsapi.org/)")
        if not features['social_sentiment']:
            print("  REDDIT_API_KEY=your_reddit_key and/or TWITTER_API_KEY=your_twitter_key")
        if not features['financial_data']:
            print("  FINANCIAL_DATASETS_API_KEY=your_key (for extended tickers)")
    
    print()

async def run_enhanced_hedge_fund(
    tickers: list[str],
    start_date: str,
    end_date: str,
    portfolio: dict,
    universe_name: str = "sp500",
    show_reasoning: bool = False,
    selected_analysts: list[str] = [],
    model_name: str = "gpt-4o",
    model_provider: str = "OpenAI",
    api_keys: dict = None
):
    """Run the enhanced hedge fund with comprehensive analysis"""
    
    if api_keys is None:
        api_keys = get_api_keys_from_env()
    
    # Start progress tracking
    progress.start()
    
    try:
        # Create enhanced workflow
        workflow = create_enhanced_workflow(selected_analysts, universe_name, api_keys)
        agent = workflow.compile()
        
        final_state = await agent.ainvoke({
            "messages": [
                HumanMessage(content="Make enhanced trading decisions with comprehensive analysis.")
            ],
            "data": {
                "tickers": tickers,
                "portfolio": portfolio,
                "start_date": start_date,
                "end_date": end_date,
                "analyst_signals": {},
                "universe_name": universe_name,
                "api_keys": api_keys
            },
            "metadata": {
                "show_reasoning": show_reasoning,
                "model_name": model_name,
                "model_provider": model_provider,
            },
        })
        
        return {
            "decisions": json.loads(final_state["messages"][-1].content),
            "analyst_signals": final_state["data"]["analyst_signals"],
            "enhanced_analysis": final_state["data"].get("enhanced_analysis", {})
        }
    
    finally:
        progress.stop()

def create_enhanced_workflow(selected_analysts=None, universe_name="sp500", api_keys=None):
    """Create enhanced workflow with comprehensive analysis"""
    
    workflow = StateGraph(AgentState)
    workflow.add_node("start_node", start)
    
    # Get analyst nodes
    analyst_nodes = get_analyst_nodes()
    
    # Default to all analysts if none selected
    if selected_analysts is None:
        selected_analysts = list(analyst_nodes.keys())
    
    # Add selected analyst nodes
    for analyst_key in selected_analysts:
        node_name, node_func = analyst_nodes[analyst_key]
        workflow.add_node(node_name, node_func)
        workflow.add_edge("start_node", node_name)
    
    # Add risk management
    workflow.add_node("risk_management_agent", risk_management_agent)
    
    # Add enhanced portfolio manager
    async def enhanced_portfolio_wrapper(state):
        return await enhanced_portfolio_management_agent(state, universe_name, api_keys or {})
    
    workflow.add_node("enhanced_portfolio_manager", enhanced_portfolio_wrapper)
    
    # Connect workflow
    for analyst_key in selected_analysts:
        node_name = analyst_nodes[analyst_key][0]
        workflow.add_edge(node_name, "risk_management_agent")
    
    workflow.add_edge("risk_management_agent", "enhanced_portfolio_manager")
    workflow.add_edge("enhanced_portfolio_manager", END)
    
    workflow.set_entry_point("start_node")
    return workflow

def start(state: AgentState):
    """Initialize the enhanced workflow"""
    return state

def parse_enhanced_response(response):
    """Parse enhanced response with error handling"""
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        print(f"JSON decoding error: {e}")
        return None
    except Exception as e:
        print(f"Error parsing response: {e}")
        return None

def main():
    """Enhanced main function with comprehensive features"""
    
    parser = argparse.ArgumentParser(description="Enhanced AI Hedge Fund with comprehensive analysis")
    parser.add_argument("--initial-cash", type=float, default=100000.0, help="Initial cash position")
    parser.add_argument("--margin-requirement", type=float, default=0.0, help="Initial margin requirement")
    parser.add_argument("--tickers", type=str, required=True, help="Comma-separated list of tickers")
    parser.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--show-reasoning", action="store_true", help="Show detailed reasoning")
    parser.add_argument("--universe", type=str, choices=list_trading_universes(), 
                       default="sp500", help="Trading universe to use")
    parser.add_argument("--ollama", action="store_true", help="Use Ollama for local LLM")
    parser.add_argument("--demo", action="store_true", help="Run demo with sample data")
    
    args = parser.parse_args()
    
    # Get API keys and check feature availability
    api_keys = get_api_keys_from_env()
    features = check_enhanced_features_availability(api_keys)
    
    print(f"\n{Fore.GREEN}🚀 Enhanced AI Hedge Fund{Style.RESET_ALL}")
    print(f"{Fore.BLUE}📈 Advanced Portfolio Management with Comprehensive Analysis{Style.RESET_ALL}")
    
    display_feature_status(features)
    
    if args.demo:
        print(f"{Fore.CYAN}🎯 Running Demo Mode with Sample Data{Style.RESET_ALL}")
        tickers = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]
        args.universe = "tech"
        args.show_reasoning = True
    else:
        tickers = [ticker.strip().upper() for ticker in args.tickers.split(",")]
    
    # Select trading universe
    if not args.demo:
        universe_choice = questionary.select(
            "Select your trading universe:",
            choices=[questionary.Choice(display, value=value) for display, value in UNIVERSE_OPTIONS],
            default=args.universe,
            style=questionary.Style([
                ("selected", "fg:green bold"),
                ("pointer", "fg:green bold"), 
                ("highlighted", "fg:green"),
                ("answer", "fg:green bold"),
            ])
        ).ask()
        
        if not universe_choice:
            print("\nExiting...")
            sys.exit(0)
        
        universe_name = universe_choice
    else:
        universe_name = args.universe
    
    print(f"\n{Fore.GREEN}📊 Selected Universe: {universe_name.title().replace('_', ' ')}{Style.RESET_ALL}")
    
    # Display universe details
    universe = TRADING_UNIVERSES[universe_name]
    print(f"   📋 Description: {universe.description}")
    print(f"   🎯 Asset Classes: {', '.join(universe.asset_classes)}")
    if universe.max_positions:
        print(f"   📈 Max Positions: {universe.max_positions}")
    
    # Select analysts
    selected_analysts = questionary.checkbox(
        "Select your AI analysts:",
        choices=[questionary.Choice(display, value=value) for display, value in ANALYST_ORDER],
        instruction="\nPress Space to select, 'a' for all, Enter when done",
        validate=lambda x: len(x) > 0 or "You must select at least one analyst.",
        style=questionary.Style([
            ("checkbox-selected", "fg:green"),
            ("selected", "fg:green noinherit"),
            ("highlighted", "noinherit"),
            ("pointer", "noinherit"),
        ])
    ).ask()
    
    if not selected_analysts:
        print("\nExiting...")
        sys.exit(0)
    
    print(f"\n{Fore.GREEN}🤖 Selected Analysts: {', '.join(choice.title().replace('_', ' ') for choice in selected_analysts)}{Style.RESET_ALL}")
    
    # Select LLM model
    model_name, model_provider = select_llm_model(args.ollama)
    
    # Set dates
    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
    if not args.start_date:
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        start_date = (end_date_obj - relativedelta(months=3)).strftime("%Y-%m-%d")
    else:
        start_date = args.start_date
    
    # Initialize portfolio
    portfolio = create_initial_portfolio(tickers, args.initial_cash, args.margin_requirement)
    
    print(f"\n{Fore.BLUE}📅 Analysis Period: {start_date} to {end_date}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}💰 Initial Cash: ${args.initial_cash:,.2f}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}🎯 Tickers: {', '.join(tickers)}{Style.RESET_ALL}")
    
    # Run enhanced hedge fund
    print(f"\n{Fore.YELLOW}🔄 Running Enhanced Analysis...{Style.RESET_ALL}")
    
    result = asyncio.run(run_enhanced_hedge_fund(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        portfolio=portfolio,
        universe_name=universe_name,
        show_reasoning=args.show_reasoning,
        selected_analysts=selected_analysts,
        model_name=model_name,
        model_provider=model_provider,
        api_keys=api_keys
    ))
    
    # Display results
    print_enhanced_results(result, features)

def select_llm_model(use_ollama: bool):
    """Select LLM model"""
    if use_ollama:
        model_name = questionary.select(
            "Select your Ollama model:",
            choices=[questionary.Choice(display, value=value) for display, value, _ in OLLAMA_LLM_ORDER],
            style=questionary.Style([
                ("selected", "fg:green bold"),
                ("pointer", "fg:green bold"),
                ("highlighted", "fg:green"),
                ("answer", "fg:green bold"),
            ])
        ).ask()
        
        if not model_name:
            sys.exit(0)
        
        if not ensure_ollama_and_model(model_name):
            print(f"{Fore.RED}Cannot proceed without Ollama model.{Style.RESET_ALL}")
            sys.exit(1)
        
        return model_name, ModelProvider.OLLAMA.value
    else:
        model_choice = questionary.select(
            "Select your LLM model:",
            choices=[questionary.Choice(display, value=(name, provider)) for display, name, provider in LLM_ORDER],
            style=questionary.Style([
                ("selected", "fg:green bold"),
                ("pointer", "fg:green bold"),
                ("highlighted", "fg:green"),
                ("answer", "fg:green bold"),
            ])
        ).ask()
        
        if not model_choice:
            sys.exit(0)
        
        return model_choice

def create_initial_portfolio(tickers: list, initial_cash: float, margin_requirement: float):
    """Create initial portfolio structure"""
    return {
        "cash": initial_cash,
        "margin_requirement": margin_requirement,
        "margin_used": 0.0,
        "positions": {
            ticker: {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
            for ticker in tickers
        },
        "realized_gains": {
            ticker: {"long": 0.0, "short": 0.0}
            for ticker in tickers
        },
    }

def print_enhanced_results(result: dict, features: dict):
    """Print enhanced analysis results"""
    
    print(f"\n{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}🎯 ENHANCED TRADING ANALYSIS RESULTS{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    
    # Portfolio-level analysis
    if "portfolio_analysis" in result.get("decisions", {}):
        analysis = result["decisions"]["portfolio_analysis"]
        print(f"\n{Fore.CYAN}📊 Portfolio-Level Analysis:{Style.RESET_ALL}")
        print(f"   🌡️  Market Sentiment: {analysis.get('market_sentiment', 0):.2f}")
        print(f"   🏥 Economic Health: {analysis.get('economic_health', 50):.1f}/100")
        print(f"   🏛️  Political Stability: {analysis.get('political_stability', 50):.1f}/100")
        print(f"   📈 Market Regime: {analysis.get('market_regime', 'Unknown')}")
        print(f"   ⚠️  Risk Level: {analysis.get('risk_level', 'Medium')}")
    
    # Enhanced analysis details
    if "enhanced_analysis" in result:
        enhanced = result["enhanced_analysis"]
        
        if features["economic_indicators"] and "economic" in enhanced:
            econ = enhanced["economic"]
            print(f"\n{Fore.YELLOW}📈 Economic Indicators:{Style.RESET_ALL}")
            print(f"   📊 Health Score: {econ.get('health_score', 50):.1f}/100")
            print(f"   📝 Summary: {econ.get('summary', 'N/A')}")
        
        if features["political_signals"] and "political" in enhanced:
            pol = enhanced["political"]
            print(f"\n{Fore.RED}🏛️ Political Signals:{Style.RESET_ALL}")
            print(f"   ⚡ High Impact Events: {pol.get('high_impact_events', 0)}")
            print(f"   📰 Total Events: {pol.get('total_events', 0)}")
        
        if features["social_sentiment"] and "sentiment" in enhanced:
            print(f"\n{Fore.MAGENTA}💬 Social Sentiment:{Style.RESET_ALL}")
            sentiment = enhanced["sentiment"]
            for ticker, data in sentiment.items():
                print(f"   {ticker}: {data.get('social_sentiment', 0):.2f} ({data.get('mentions', 0)} mentions)")
    
    # Trading decisions
    if "decisions" in result.get("decisions", {}):
        decisions = result["decisions"]["decisions"]
        print(f"\n{Fore.BLUE}🎯 Trading Decisions:{Style.RESET_ALL}")
        
        for ticker, decision in decisions.items():
            action = decision.get("action", "hold")
            quantity = decision.get("quantity", 0)
            confidence = decision.get("confidence", 0)
            
            action_color = {
                "buy": Fore.GREEN,
                "sell": Fore.RED,
                "short": Fore.YELLOW,
                "cover": Fore.CYAN,
                "hold": Fore.WHITE
            }.get(action, Fore.WHITE)
            
            print(f"   {ticker}: {action_color}{action.upper()}{Style.RESET_ALL} "
                  f"{quantity} shares (Confidence: {confidence:.1f}%)")
            
            # Show enhanced metrics if available
            if "sentiment_score" in decision:
                print(f"     📊 Sentiment: {decision['sentiment_score']:.2f}")
            if "economic_impact" in decision:
                print(f"     🏛️ Economic Impact: {decision['economic_impact']:.2f}")
            if "political_risk" in decision:
                print(f"     ⚠️ Political Risk: {decision['political_risk']:.2f}")
    
    print(f"\n{Fore.GREEN}✅ Enhanced Analysis Complete!{Style.RESET_ALL}")

if __name__ == "__main__":
    main()