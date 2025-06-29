"""
Enhanced Portfolio Manager with Trading Universe and Comprehensive Analysis.
Integrates trading universe, enhanced sentiment, economic indicators, and political signals.
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.graph.state import AgentState, show_agent_reasoning
from src.utils.progress import progress
from src.utils.llm import call_llm
from src.data.trading_universes import get_trading_universe, TRADING_UNIVERSES
from src.data.economic_indicators import EconomicDataManager
from src.data.political_signals import PoliticalSignalsManager
from src.agents.enhanced_sentiment import AdvancedSentimentAnalyzer, SocialMediaAnalyzer
from src.data.realtime_data import RealTimeDataManager, create_data_provider


class EnhancedPortfolioDecision(BaseModel):
    """Enhanced portfolio decision with comprehensive analysis"""
    action: str = Field(description="Trading action: buy, sell, short, cover, hold")
    quantity: int = Field(description="Number of shares to trade")
    confidence: float = Field(description="Confidence level 0-100")
    reasoning: str = Field(description="Detailed reasoning for the decision")
    
    # Enhanced analysis components
    sentiment_score: Optional[float] = Field(description="Sentiment analysis score -1 to 1")
    economic_impact: Optional[float] = Field(description="Economic indicators impact -1 to 1")
    political_risk: Optional[float] = Field(description="Political risk assessment -1 to 1")
    market_regime: Optional[str] = Field(description="Current market regime assessment")
    volatility_forecast: Optional[float] = Field(description="Expected volatility 0-1")
    
    # Risk metrics
    max_position_size: Optional[float] = Field(description="Maximum position size allowed")
    sector_exposure: Optional[str] = Field(description="Sector exposure analysis")
    correlation_risk: Optional[float] = Field(description="Portfolio correlation risk")


class EnhancedPortfolioOutput(BaseModel):
    """Enhanced portfolio output with macro analysis"""
    decisions: Dict[str, EnhancedPortfolioDecision] = Field(description="Trading decisions by ticker")
    
    # Portfolio-level insights
    overall_market_sentiment: float = Field(description="Overall market sentiment -1 to 1")
    economic_health_score: float = Field(description="Economic health score 0-100")
    political_stability: float = Field(description="Political stability score 0-100")
    recommended_cash_level: float = Field(description="Recommended cash percentage 0-1")
    market_regime: str = Field(description="Bull, Bear, Sideways, Volatile")
    risk_level: str = Field(description="Low, Medium, High")


class UniverseAnalyzer:
    """Analyzes trading universe and filters securities"""
    
    def __init__(self, universe_name: str = "sp500"):
        self.universe = get_trading_universe(universe_name)
        self.universe_name = universe_name
    
    def filter_tickers(self, candidate_tickers: List[str]) -> List[str]:
        """Filter tickers based on trading universe criteria"""
        if self.universe.included_tickers:
            # If universe has specific tickers, filter to those
            filtered = [t for t in candidate_tickers if t in self.universe.included_tickers]
        else:
            # Otherwise, use all provided tickers (assume they meet criteria)
            filtered = candidate_tickers
        
        # Apply maximum position limits
        if self.universe.max_positions and len(filtered) > self.universe.max_positions:
            # Prioritize by some criteria (for now, just take first N)
            filtered = filtered[:self.universe.max_positions]
        
        return filtered
    
    def get_sector_allocation_targets(self) -> Dict[str, float]:
        """Get target sector allocations based on universe"""
        if self.universe_name == "tech":
            return {
                "technology": 0.6,
                "communication": 0.2,
                "consumer_discretionary": 0.2
            }
        elif self.universe_name == "conservative":
            return {
                "consumer_staples": 0.3,
                "healthcare": 0.3,
                "utilities": 0.2,
                "financials": 0.2
            }
        elif self.universe_name == "sector_etf":
            return {
                "technology": 0.15,
                "healthcare": 0.15,
                "financials": 0.15,
                "industrials": 0.1,
                "energy": 0.1,
                "consumer_discretionary": 0.1,
                "consumer_staples": 0.1,
                "utilities": 0.05,
                "materials": 0.05,
                "real_estate": 0.05
            }
        else:
            # Default balanced allocation
            return {}


class MacroAnalysisEngine:
    """Comprehensive macro analysis engine"""
    
    def __init__(self, api_keys: Dict[str, str]):
        self.economic_manager = EconomicDataManager(api_keys.get("fred_api_key", ""))
        self.political_manager = PoliticalSignalsManager({
            "newsapi": api_keys.get("newsapi_key", ""),
            "reddit": api_keys.get("reddit_key", ""),
            "twitter": api_keys.get("twitter_key", "")
        })
        self.sentiment_analyzer = AdvancedSentimentAnalyzer()
        self.social_analyzer = SocialMediaAnalyzer(api_keys)
        
    async def get_comprehensive_analysis(self, tickers: List[str]) -> Dict[str, Any]:
        """Get comprehensive macro and sentiment analysis"""
        try:
            # Start all data providers
            await self.economic_manager.start()
            await self.political_manager.start()
            await self.social_analyzer.connect()
            
            # Get economic summary
            economic_data = await self.economic_manager.get_economic_summary()
            
            # Get political events
            political_events = await self.political_manager.update_political_events()
            high_impact_events = self.political_manager.get_high_impact_events()
            
            # Get sentiment analysis for each ticker
            sentiment_data = {}
            social_sentiment_data = {}
            
            for ticker in tickers:
                try:
                    # Get social sentiment
                    social_sentiment = await self.social_analyzer.analyze_social_sentiment(ticker)
                    social_sentiment_data[ticker] = social_sentiment
                    
                    # Analyze recent news for sentiment
                    # (This would integrate with news feeds in production)
                    sentiment_data[ticker] = {
                        "social_sentiment": social_sentiment.average_sentiment,
                        "mentions": social_sentiment.total_mentions,
                        "trending_topics": social_sentiment.trending_topics[:3]
                    }
                except Exception as e:
                    sentiment_data[ticker] = {
                        "social_sentiment": 0.0,
                        "mentions": 0,
                        "trending_topics": []
                    }
            
            return {
                "economic": {
                    "health_score": economic_data["health_score"],
                    "summary": economic_data["summary"],
                    "indicators": {k: v.value for k, v in economic_data["indicators"].items()},
                    "upcoming_events": len(economic_data["upcoming_events"])
                },
                "political": {
                    "high_impact_events": len(high_impact_events),
                    "total_events": len(political_events),
                    "recent_events": [
                        {
                            "title": event.title,
                            "impact_score": event.market_impact_score,
                            "sentiment": event.sentiment_score
                        }
                        for event in high_impact_events[:3]
                    ]
                },
                "sentiment": sentiment_data,
                "market_regime": self._assess_market_regime(economic_data, political_events, sentiment_data)
            }
            
        except Exception as e:
            print(f"Error in macro analysis: {e}")
            return self._get_default_analysis(tickers)
        
        finally:
            # Clean up connections
            try:
                await self.economic_manager.stop()
                await self.political_manager.stop()
                await self.social_analyzer.disconnect()
            except:
                pass
    
    def _assess_market_regime(self, economic_data: Dict, political_events: List, 
                            sentiment_data: Dict) -> str:
        """Assess current market regime"""
        
        # Economic factors
        health_score = economic_data.get("health_score", 50)
        
        # Political factors
        high_impact_political = sum(1 for event in political_events 
                                  if hasattr(event, 'impact_level') and 
                                  event.impact_level == "high")
        
        # Sentiment factors
        avg_sentiment = sum(data.get("social_sentiment", 0) 
                          for data in sentiment_data.values()) / max(len(sentiment_data), 1)
        
        # Determine regime
        if health_score > 70 and avg_sentiment > 0.2 and high_impact_political < 2:
            return "Bull Market"
        elif health_score < 40 or avg_sentiment < -0.3 or high_impact_political > 3:
            return "Bear Market"
        elif abs(avg_sentiment) < 0.1 and 40 <= health_score <= 70:
            return "Sideways Market"
        else:
            return "Volatile Market"
    
    def _get_default_analysis(self, tickers: List[str]) -> Dict[str, Any]:
        """Return default analysis when data is unavailable"""
        return {
            "economic": {
                "health_score": 50.0,
                "summary": "Economic data unavailable",
                "indicators": {},
                "upcoming_events": 0
            },
            "political": {
                "high_impact_events": 0,
                "total_events": 0,
                "recent_events": []
            },
            "sentiment": {ticker: {"social_sentiment": 0.0, "mentions": 0, "trending_topics": []} 
                         for ticker in tickers},
            "market_regime": "Neutral Market"
        }


async def enhanced_portfolio_management_agent(state: AgentState, universe_name: str = "sp500", 
                                            api_keys: Dict[str, str] = None):
    """Enhanced portfolio management with comprehensive analysis"""
    
    # Get portfolio and signals
    portfolio = state["data"]["portfolio"]
    analyst_signals = state["data"]["analyst_signals"]
    tickers = state["data"]["tickers"]
    
    if api_keys is None:
        api_keys = {}
    
    progress.update_status("enhanced_portfolio_manager", None, "Initializing analysis engines")
    
    # Initialize analyzers
    universe_analyzer = UniverseAnalyzer(universe_name)
    macro_engine = MacroAnalysisEngine(api_keys)
    
    # Filter tickers based on trading universe
    filtered_tickers = universe_analyzer.filter_tickers(tickers)
    progress.update_status("enhanced_portfolio_manager", None, 
                          f"Filtered to {len(filtered_tickers)} tickers from universe")
    
    # Get comprehensive macro analysis
    progress.update_status("enhanced_portfolio_manager", None, "Running macro analysis")
    try:
        macro_analysis = await macro_engine.get_comprehensive_analysis(filtered_tickers)
    except Exception as e:
        print(f"Macro analysis failed: {e}")
        macro_analysis = macro_engine._get_default_analysis(filtered_tickers)
    
    # Prepare enhanced decision context
    enhanced_context = {
        "tickers": filtered_tickers,
        "universe": universe_name,
        "macro_analysis": macro_analysis,
        "sector_targets": universe_analyzer.get_sector_allocation_targets(),
        "analyst_signals": analyst_signals,
        "portfolio": portfolio
    }
    
    progress.update_status("enhanced_portfolio_manager", None, "Generating enhanced decisions")
    
    # Generate enhanced trading decisions
    result = await generate_enhanced_trading_decision(enhanced_context, state)
    
    # Create message
    message = HumanMessage(
        content=json.dumps({
            "decisions": {ticker: decision.model_dump() for ticker, decision in result.decisions.items()},
            "portfolio_analysis": {
                "market_sentiment": result.overall_market_sentiment,
                "economic_health": result.economic_health_score,
                "political_stability": result.political_stability,
                "market_regime": result.market_regime,
                "risk_level": result.risk_level
            }
        }),
        name="enhanced_portfolio_manager",
    )
    
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(result.model_dump(), "Enhanced Portfolio Manager")
    
    progress.update_status("enhanced_portfolio_manager", None, "Done")
    
    return {
        "messages": state["messages"] + [message],
        "data": {**state["data"], "enhanced_analysis": macro_analysis},
    }


async def generate_enhanced_trading_decision(context: Dict[str, Any], 
                                           state: AgentState) -> EnhancedPortfolioOutput:
    """Generate enhanced trading decisions with comprehensive analysis"""
    
    template = ChatPromptTemplate.from_messages([
        ("system", """You are an advanced portfolio manager using comprehensive market analysis.
        
        Your analysis includes:
        - Economic indicators and health score
        - Political risk assessment
        - Social sentiment analysis
        - Trading universe constraints
        - Sector allocation targets
        - Market regime analysis
        
        Consider all these factors when making trading decisions.
        
        Market Regimes:
        - Bull Market: Favor growth stocks, higher allocations, momentum strategies
        - Bear Market: Defensive positions, higher cash, quality stocks, short opportunities
        - Sideways Market: Range trading, value plays, covered calls
        - Volatile Market: Reduced position sizes, options strategies, frequent rebalancing
        
        Trading Universe: {universe}
        Current Market Regime: {market_regime}
        Economic Health Score: {economic_health}/100
        Overall Market Sentiment: {market_sentiment}
        """),
        
        ("human", """Based on the comprehensive analysis, make enhanced trading decisions.
        
        Trading Universe: {universe}
        Filtered Tickers: {tickers}
        
        Macro Analysis:
        {macro_analysis}
        
        Sector Allocation Targets:
        {sector_targets}
        
        Current Portfolio:
        {portfolio}
        
        Analyst Signals:
        {analyst_signals}
        
        Provide enhanced decisions with detailed reasoning incorporating:
        1. Economic indicators impact
        2. Political risk assessment
        3. Sentiment analysis
        4. Sector allocation
        5. Market regime considerations
        6. Risk management
        
        Output in JSON format matching EnhancedPortfolioOutput schema.
        """)
    ])
    
    prompt = template.invoke({
        "universe": context["universe"],
        "market_regime": context["macro_analysis"]["market_regime"],
        "economic_health": context["macro_analysis"]["economic"]["health_score"],
        "market_sentiment": sum(s["social_sentiment"] for s in context["macro_analysis"]["sentiment"].values()) / max(len(context["macro_analysis"]["sentiment"]), 1),
        "tickers": context["tickers"],
        "macro_analysis": json.dumps(context["macro_analysis"], indent=2),
        "sector_targets": json.dumps(context["sector_targets"], indent=2),
        "portfolio": json.dumps(context["portfolio"], indent=2),
        "analyst_signals": json.dumps(context["analyst_signals"], indent=2)
    })
    
    def create_default_output():
        """Create default output when LLM fails"""
        decisions = {}
        for ticker in context["tickers"]:
            decisions[ticker] = EnhancedPortfolioDecision(
                action="hold",
                quantity=0,
                confidence=50.0,
                reasoning="Default hold due to analysis error",
                sentiment_score=0.0,
                economic_impact=0.0,
                political_risk=0.0,
                market_regime=context["macro_analysis"]["market_regime"],
                volatility_forecast=0.2
            )
        
        return EnhancedPortfolioOutput(
            decisions=decisions,
            overall_market_sentiment=0.0,
            economic_health_score=50.0,
            political_stability=50.0,
            recommended_cash_level=0.2,
            market_regime=context["macro_analysis"]["market_regime"],
            risk_level="Medium"
        )
    
    return call_llm(
        prompt=prompt,
        pydantic_model=EnhancedPortfolioOutput,
        agent_name="enhanced_portfolio_manager",
        state=state,
        default_factory=create_default_output,
    )


# Example usage function
async def demo_enhanced_portfolio_manager():
    """Demonstrate the enhanced portfolio manager"""
    
    # Example API keys (use your actual keys)
    api_keys = {
        "fred_api_key": "your_fred_api_key",
        "newsapi_key": "your_newsapi_key",
        "reddit_key": "your_reddit_key",
        "twitter_key": "your_twitter_key"
    }
    
    # Example state
    state = {
        "messages": [],
        "data": {
            "tickers": ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"],
            "portfolio": {
                "cash": 100000,
                "positions": {
                    "AAPL": {"long": 0, "short": 0},
                    "MSFT": {"long": 0, "short": 0},
                    "GOOGL": {"long": 0, "short": 0},
                    "NVDA": {"long": 0, "short": 0},
                    "TSLA": {"long": 0, "short": 0}
                }
            },
            "analyst_signals": {}
        },
        "metadata": {"show_reasoning": True}
    }
    
    # Run enhanced portfolio manager with tech universe
    result = await enhanced_portfolio_management_agent(
        state, 
        universe_name="tech", 
        api_keys=api_keys
    )
    
    print("Enhanced Portfolio Analysis Complete!")
    return result


if __name__ == "__main__":
    # Run the demo
    asyncio.run(demo_enhanced_portfolio_manager())