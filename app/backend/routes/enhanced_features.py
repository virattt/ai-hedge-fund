"""
Enhanced features API endpoints for the web UI.
Provides access to trading universes, sentiment analysis, economic indicators, and political signals.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv

from src.data.trading_universes import TRADING_UNIVERSES, get_trading_universe, list_trading_universes
from src.data.economic_indicators import EconomicDataManager
from src.data.political_signals import PoliticalSignalsManager
from src.agents.enhanced_sentiment import AdvancedSentimentAnalyzer, SocialMediaAnalyzer
from src.agents.enhanced_portfolio_manager import enhanced_portfolio_management_agent, MacroAnalysisEngine

load_dotenv()

router = APIRouter(prefix="/api/v1/enhanced", tags=["enhanced-features"])

# Global instances (will be initialized when needed)
economic_manager = None
political_manager = None
sentiment_analyzer = None
social_analyzer = None

# Request/Response Models
class UniverseInfo(BaseModel):
    name: str
    description: str
    asset_classes: List[str]
    max_positions: Optional[int]
    included_tickers: List[str]
    sector_focus: Optional[List[str]] = None

class EconomicIndicatorData(BaseModel):
    name: str
    value: float
    previous_value: Optional[float]
    change: Optional[float]
    change_percent: Optional[float]
    timestamp: datetime
    importance: str

class PoliticalEventData(BaseModel):
    title: str
    event_type: str
    date: datetime
    impact_level: str
    market_impact_score: float
    sentiment_score: float
    affected_sectors: List[str]

class SentimentData(BaseModel):
    ticker: str
    social_sentiment: float
    mentions: int
    trending_topics: List[str]
    confidence: float

class PortfolioAnalysisRequest(BaseModel):
    tickers: List[str]
    universe: str = "sp500"
    portfolio: Dict[str, Any]
    analyst_signals: Dict[str, Any] = Field(default_factory=dict)

class PortfolioAnalysisResponse(BaseModel):
    decisions: Dict[str, Any]
    market_sentiment: float
    economic_health: float
    political_stability: float
    market_regime: str
    risk_level: str
    sector_allocation: Dict[str, float]

def get_api_keys() -> Dict[str, str]:
    """Get API keys from environment"""
    return {
        "fred_api_key": os.getenv("FRED_API_KEY", ""),
        "newsapi_key": os.getenv("NEWSAPI_KEY", ""),
        "reddit_key": os.getenv("REDDIT_API_KEY", ""),
        "twitter_key": os.getenv("TWITTER_API_KEY", ""),
        "financial_datasets_api_key": os.getenv("FINANCIAL_DATASETS_API_KEY", "")
    }

async def get_managers():
    """Initialize and return global managers"""
    global economic_manager, political_manager, sentiment_analyzer, social_analyzer
    
    api_keys = get_api_keys()
    
    if economic_manager is None:
        economic_manager = EconomicDataManager(api_keys["fred_api_key"])
        if api_keys["fred_api_key"]:
            try:
                await economic_manager.start()
            except Exception:
                pass  # Continue without FRED if API key is invalid
    
    if political_manager is None:
        political_manager = PoliticalSignalsManager({
            "newsapi": api_keys["newsapi_key"],
            "reddit": api_keys["reddit_key"],
            "twitter": api_keys["twitter_key"]
        })
        try:
            await political_manager.start()
        except Exception:
            pass  # Continue without political signals if APIs unavailable
    
    if sentiment_analyzer is None:
        sentiment_analyzer = AdvancedSentimentAnalyzer()
    
    if social_analyzer is None:
        social_analyzer = SocialMediaAnalyzer(api_keys)
        try:
            await social_analyzer.connect()
        except Exception:
            pass  # Continue without social analysis if APIs unavailable
    
    return economic_manager, political_manager, sentiment_analyzer, social_analyzer

@router.get("/status")
async def get_feature_status():
    """Get status of enhanced features based on available API keys"""
    api_keys = get_api_keys()
    
    return {
        "basic_features": True,
        "economic_indicators": bool(api_keys["fred_api_key"]),
        "political_signals": bool(api_keys["newsapi_key"]),
        "social_sentiment": bool(api_keys["reddit_key"] or api_keys["twitter_key"]),
        "financial_data": bool(api_keys["financial_datasets_api_key"]),
        "api_keys_configured": {
            "fred": bool(api_keys["fred_api_key"]),
            "newsapi": bool(api_keys["newsapi_key"]),
            "reddit": bool(api_keys["reddit_key"]),
            "twitter": bool(api_keys["twitter_key"]),
            "financial_datasets": bool(api_keys["financial_datasets_api_key"])
        }
    }

@router.get("/universes", response_model=List[UniverseInfo])
async def get_trading_universes():
    """Get all available trading universes"""
    universes = []
    
    for name, universe in TRADING_UNIVERSES.items():
        universes.append(UniverseInfo(
            name=name,
            description=universe.description,
            asset_classes=[str(ac) for ac in universe.asset_classes],
            max_positions=universe.max_positions,
            included_tickers=universe.included_tickers,
            sector_focus=[str(s) for s in universe.sectors] if universe.sectors else None
        ))
    
    return universes

@router.get("/universes/{universe_name}")
async def get_universe_details(universe_name: str):
    """Get detailed information about a specific trading universe"""
    try:
        universe = get_trading_universe(universe_name)
        return UniverseInfo(
            name=universe_name,
            description=universe.description,
            asset_classes=[str(ac) for ac in universe.asset_classes],
            max_positions=universe.max_positions,
            included_tickers=universe.included_tickers,
            sector_focus=[str(s) for s in universe.sectors] if universe.sectors else None
        )
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Universe '{universe_name}' not found")

@router.get("/economic-indicators", response_model=List[EconomicIndicatorData])
async def get_economic_indicators():
    """Get current economic indicators"""
    try:
        econ_manager, _, _, _ = await get_managers()
        
        if not econ_manager or not get_api_keys()["fred_api_key"]:
            return []
        
        indicators_dict = await econ_manager.get_all_indicators()
        indicators = []
        
        for name, indicator in indicators_dict.items():
            indicators.append(EconomicIndicatorData(
                name=name,
                value=indicator.value,
                previous_value=indicator.previous_value,
                change=indicator.change,
                change_percent=indicator.change_percent,
                timestamp=indicator.timestamp,
                importance=indicator.importance.value
            ))
        
        return indicators
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching economic indicators: {str(e)}")

@router.get("/economic-summary")
async def get_economic_summary():
    """Get comprehensive economic summary"""
    try:
        econ_manager, _, _, _ = await get_managers()
        
        if not econ_manager or not get_api_keys()["fred_api_key"]:
            return {
                "health_score": 50.0,
                "summary": "Economic data unavailable - FRED API key not configured",
                "indicators": {},
                "upcoming_events": []
            }
        
        summary = await econ_manager.get_economic_summary()
        return {
            "health_score": summary["health_score"],
            "summary": summary["summary"],
            "indicators": {k: v.value for k, v in summary["indicators"].items()},
            "upcoming_events": len(summary["upcoming_events"]),
            "last_updated": summary["last_updated"]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching economic summary: {str(e)}")

@router.get("/political-events", response_model=List[PoliticalEventData])
async def get_political_events(days_back: int = 7, high_impact_only: bool = False):
    """Get recent political events"""
    try:
        _, pol_manager, _, _ = await get_managers()
        
        if not pol_manager or not get_api_keys()["newsapi_key"]:
            return []
        
        await pol_manager.update_political_events()
        
        if high_impact_only:
            events = pol_manager.get_high_impact_events(days_back)
        else:
            # Get all events from the last N days
            cutoff_date = datetime.now() - timedelta(days=days_back)
            events = [e for e in pol_manager.active_events if e.date >= cutoff_date]
        
        return [
            PoliticalEventData(
                title=event.title,
                event_type=event.event_type.value,
                date=event.date,
                impact_level=event.impact_level.value,
                market_impact_score=event.market_impact_score,
                sentiment_score=event.sentiment_score,
                affected_sectors=[str(s) for s in event.affected_sectors]
            )
            for event in events[:50]  # Limit to 50 events
        ]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching political events: {str(e)}")

@router.get("/sentiment/{ticker}", response_model=SentimentData)
async def get_ticker_sentiment(ticker: str):
    """Get sentiment analysis for a specific ticker"""
    try:
        _, _, _, social_analyzer = await get_managers()
        
        if not social_analyzer:
            return SentimentData(
                ticker=ticker,
                social_sentiment=0.0,
                mentions=0,
                trending_topics=[],
                confidence=0.0
            )
        
        sentiment = await social_analyzer.analyze_social_sentiment(ticker.upper())
        
        return SentimentData(
            ticker=ticker.upper(),
            social_sentiment=sentiment.average_sentiment,
            mentions=sentiment.total_mentions,
            trending_topics=sentiment.trending_topics[:5],
            confidence=sentiment.influence_score / max(sentiment.total_mentions, 1)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching sentiment for {ticker}: {str(e)}")

@router.post("/sentiment/batch")
async def get_batch_sentiment(tickers: List[str]):
    """Get sentiment analysis for multiple tickers"""
    try:
        results = {}
        
        for ticker in tickers[:10]:  # Limit to 10 tickers
            try:
                sentiment_data = await get_ticker_sentiment(ticker)
                results[ticker.upper()] = sentiment_data.dict()
            except Exception:
                results[ticker.upper()] = {
                    "ticker": ticker.upper(),
                    "social_sentiment": 0.0,
                    "mentions": 0,
                    "trending_topics": [],
                    "confidence": 0.0
                }
        
        return results
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching batch sentiment: {str(e)}")

@router.post("/portfolio-analysis", response_model=PortfolioAnalysisResponse)
async def analyze_portfolio(request: PortfolioAnalysisRequest):
    """Run enhanced portfolio analysis"""
    try:
        api_keys = get_api_keys()
        
        # Create a mock state for the enhanced portfolio manager
        state = {
            "messages": [],
            "data": {
                "tickers": request.tickers,
                "portfolio": request.portfolio,
                "analyst_signals": request.analyst_signals,
                "start_date": (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d"),
                "end_date": datetime.now().strftime("%Y-%m-%d")
            },
            "metadata": {"show_reasoning": False}
        }
        
        # Run enhanced portfolio analysis
        result = await enhanced_portfolio_management_agent(
            state, 
            request.universe, 
            api_keys
        )
        
        # Parse the result from the message content
        if result["messages"]:
            content = json.loads(result["messages"][-1].content)
            decisions = content.get("decisions", {})
            portfolio_analysis = content.get("portfolio_analysis", {})
            
            return PortfolioAnalysisResponse(
                decisions=decisions,
                market_sentiment=portfolio_analysis.get("market_sentiment", 0.0),
                economic_health=portfolio_analysis.get("economic_health", 50.0),
                political_stability=portfolio_analysis.get("political_stability", 50.0),
                market_regime=portfolio_analysis.get("market_regime", "Unknown"),
                risk_level=portfolio_analysis.get("risk_level", "Medium"),
                sector_allocation={}  # Could be calculated from decisions
            )
        
        else:
            raise HTTPException(status_code=500, detail="No analysis results generated")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing portfolio: {str(e)}")

@router.get("/market-overview")
async def get_market_overview():
    """Get comprehensive market overview combining all data sources"""
    try:
        # Get all data in parallel
        tasks = [
            get_economic_summary(),
            get_political_events(days_back=7, high_impact_only=True),
            get_batch_sentiment(["SPY", "QQQ", "AAPL", "MSFT", "GOOGL"])
        ]
        
        economic_data, political_data, sentiment_data = await asyncio.gather(
            *tasks, return_exceptions=True
        )
        
        # Handle exceptions gracefully
        if isinstance(economic_data, Exception):
            economic_data = {"health_score": 50.0, "summary": "Economic data unavailable"}
        
        if isinstance(political_data, Exception):
            political_data = []
        
        if isinstance(sentiment_data, Exception):
            sentiment_data = {}
        
        # Calculate overall market sentiment
        sentiment_scores = [data.get("social_sentiment", 0) for data in sentiment_data.values()]
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
        
        # Determine market regime
        economic_health = economic_data.get("health_score", 50)
        high_impact_events = len(political_data)
        
        if economic_health > 70 and avg_sentiment > 0.2 and high_impact_events < 2:
            market_regime = "Bull Market"
        elif economic_health < 40 or avg_sentiment < -0.3 or high_impact_events > 3:
            market_regime = "Bear Market"
        elif abs(avg_sentiment) < 0.1 and 40 <= economic_health <= 70:
            market_regime = "Sideways Market"
        else:
            market_regime = "Volatile Market"
        
        return {
            "market_regime": market_regime,
            "economic_health": economic_health,
            "average_sentiment": avg_sentiment,
            "high_impact_political_events": high_impact_events,
            "economic_summary": economic_data.get("summary", ""),
            "top_political_events": political_data[:3],
            "sentiment_by_ticker": sentiment_data,
            "last_updated": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching market overview: {str(e)}")

@router.websocket("/ws/live-data")
async def websocket_live_data(websocket):
    """WebSocket endpoint for live data streaming"""
    await websocket.accept()
    
    try:
        while True:
            # Send market overview every 30 seconds
            try:
                market_data = await get_market_overview()
                await websocket.send_json({
                    "type": "market_overview",
                    "data": market_data,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat()
                })
            
            await asyncio.sleep(30)  # Update every 30 seconds
    
    except Exception:
        await websocket.close()

# Cleanup function for graceful shutdown
async def cleanup_managers():
    """Clean up global managers"""
    global economic_manager, political_manager, social_analyzer
    
    try:
        if economic_manager:
            await economic_manager.stop()
        if political_manager:
            await political_manager.stop()
        if social_analyzer:
            await social_analyzer.disconnect()
    except Exception:
        pass