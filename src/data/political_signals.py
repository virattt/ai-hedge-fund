"""
Political signals monitoring system for election cycles, sanctions, fiscal policy shifts.
Tracks political events that may impact markets.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
import re
from pathlib import Path

from .cache import Cache
from .models import CompanyNews

logger = logging.getLogger(__name__)

class PoliticalEventType(str, Enum):
    """Types of political events"""
    ELECTION = "election"
    POLICY_ANNOUNCEMENT = "policy_announcement"
    SANCTIONS = "sanctions"
    TRADE_POLICY = "trade_policy"
    FISCAL_POLICY = "fiscal_policy"
    REGULATORY_CHANGE = "regulatory_change"
    GEOPOLITICAL_TENSION = "geopolitical_tension"
    GOVERNMENT_SHUTDOWN = "government_shutdown"
    DEBT_CEILING = "debt_ceiling"
    TAX_POLICY = "tax_policy"

class PoliticalImpact(str, Enum):
    """Impact levels for political events"""
    HIGH = "high"
    MEDIUM = "medium"  
    LOW = "low"

class MarketSector(str, Enum):
    """Market sectors affected by political events"""
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    ENERGY = "energy"
    FINANCIALS = "financials"
    DEFENSE = "defense"
    INFRASTRUCTURE = "infrastructure"
    TRADE = "trade"
    COMMODITIES = "commodities"
    BROAD_MARKET = "broad_market"

@dataclass
class PoliticalEvent:
    """Political event data structure"""
    title: str
    description: str
    event_type: PoliticalEventType
    date: datetime
    impact_level: PoliticalImpact
    affected_sectors: List[MarketSector]
    country: str
    source: str
    sentiment_score: float  # -1 (very negative) to 1 (very positive)
    market_impact_score: float  # 0-10 scale
    keywords: List[str]
    url: Optional[str] = None
    
    @property
    def is_recent(self) -> bool:
        """Check if event is within last 30 days"""
        return (datetime.now() - self.date).days <= 30
    
    @property
    def urgency_score(self) -> float:
        """Calculate urgency based on impact and recency"""
        impact_weight = {"high": 1.0, "medium": 0.6, "low": 0.3}[self.impact_level]
        days_old = (datetime.now() - self.date).days
        recency_weight = max(0, 1 - (days_old / 30))  # Decay over 30 days
        return impact_weight * recency_weight

@dataclass 
class ElectionData:
    """Election tracking data"""
    election_type: str  # "presidential", "congressional", "gubernatorial"
    date: datetime
    candidates: List[str]
    polls: Dict[str, float]  # candidate -> poll percentage
    betting_odds: Dict[str, float]  # candidate -> implied probability
    key_issues: List[str]
    market_implications: Dict[MarketSector, str]  # sector -> implication
    
@dataclass
class PolicyTracker:
    """Track specific policy developments"""
    policy_area: str
    current_status: str
    probability_of_passage: float  # 0-1
    expected_timeline: str
    market_impact_analysis: str
    affected_stocks: List[str]
    last_updated: datetime

class PoliticalNewsProvider:
    """Aggregates political news from multiple sources"""
    
    def __init__(self, api_keys: Dict[str, str]):
        self.api_keys = api_keys
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache = Cache()
        
        # Political keywords for filtering
        self.political_keywords = {
            "election": ["election", "vote", "campaign", "candidate", "polls"],
            "policy": ["policy", "bill", "legislation", "congress", "senate"],
            "sanctions": ["sanctions", "embargo", "trade war", "tariffs"],
            "regulation": ["regulation", "regulatory", "SEC", "FDA", "EPA"],
            "fiscal": ["budget", "spending", "deficit", "stimulus", "bailout"],
            "geopolitical": ["war", "conflict", "tension", "diplomatic", "military"]
        }
    
    async def connect(self) -> None:
        """Initialize connection"""
        self.session = aiohttp.ClientSession()
    
    async def disconnect(self) -> None:
        """Close connection"""
        if self.session:
            await self.session.close()
    
    async def fetch_political_news(self, hours_back: int = 24) -> List[CompanyNews]:
        """Fetch political news from various sources"""
        if not self.session:
            await self.connect()
        
        all_news = []
        
        # NewsAPI
        if "newsapi" in self.api_keys:
            news_api_articles = await self._fetch_from_newsapi(hours_back)
            all_news.extend(news_api_articles)
        
        # Reuters/Bloomberg via RSS or API
        rss_articles = await self._fetch_from_rss_feeds()
        all_news.extend(rss_articles)
        
        # Filter and deduplicate
        political_news = self._filter_political_content(all_news)
        return self._deduplicate_news(political_news)
    
    async def _fetch_from_newsapi(self, hours_back: int) -> List[CompanyNews]:
        """Fetch from NewsAPI"""
        if not self.session:
            return []
        
        api_key = self.api_keys.get("newsapi")
        if not api_key:
            return []
        
        from_date = (datetime.now() - timedelta(hours=hours_back)).isoformat()
        
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": "politics OR election OR congress OR president OR policy",
            "language": "en",
            "sortBy": "publishedAt",
            "from": from_date,
            "apiKey": api_key
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                data = await response.json()
                articles = data.get("articles", [])
                
                news_list = []
                for article in articles:
                    news_list.append(CompanyNews(
                        ticker="POLITICAL",  # Special ticker for political news
                        title=article.get("title", ""),
                        author=article.get("author", ""),
                        source=article.get("source", {}).get("name", ""),
                        date=article.get("publishedAt", ""),
                        url=article.get("url", ""),
                        sentiment=None
                    ))
                
                return news_list
        except Exception as e:
            logger.error(f"Error fetching from NewsAPI: {e}")
            return []
    
    async def _fetch_from_rss_feeds(self) -> List[CompanyNews]:
        """Fetch from RSS feeds"""
        # Mock RSS feed data for demonstration
        return [
            CompanyNews(
                ticker="POLITICAL",
                title="Congress Debates Infrastructure Spending Bill", 
                author="Political Reporter",
                source="Reuters",
                date=datetime.now().isoformat(),
                url="https://example.com/news",
                sentiment=None
            )
        ]
    
    def _filter_political_content(self, news_list: List[CompanyNews]) -> List[CompanyNews]:
        """Filter news for political content"""
        filtered_news = []
        
        for news in news_list:
            title_lower = news.title.lower()
            
            # Check if any political keywords are present
            is_political = any(
                keyword in title_lower 
                for keyword_list in self.political_keywords.values()
                for keyword in keyword_list
            )
            
            if is_political:
                filtered_news.append(news)
        
        return filtered_news
    
    def _deduplicate_news(self, news_list: List[CompanyNews]) -> List[CompanyNews]:
        """Remove duplicate news articles"""
        seen_titles = set()
        deduplicated = []
        
        for news in news_list:
            # Simple deduplication based on title similarity
            title_key = re.sub(r'[^\w\s]', '', news.title.lower())[:50]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                deduplicated.append(news)
        
        return deduplicated

class PoliticalEventAnalyzer:
    """Analyzes political events for market impact"""
    
    def __init__(self):
        self.sector_keywords = {
            MarketSector.TECHNOLOGY: ["tech", "data privacy", "antitrust", "regulation"],
            MarketSector.HEALTHCARE: ["healthcare", "medicare", "drug prices", "pharma"],
            MarketSector.ENERGY: ["energy", "oil", "gas", "renewable", "climate"],
            MarketSector.FINANCIALS: ["banking", "financial", "interest rates", "fed"],
            MarketSector.DEFENSE: ["defense", "military", "weapons", "aerospace"],
            MarketSector.INFRASTRUCTURE: ["infrastructure", "roads", "bridges", "construction"],
        }
    
    def analyze_news_for_events(self, news_list: List[CompanyNews]) -> List[PoliticalEvent]:
        """Analyze news articles to extract political events"""
        events = []
        
        for news in news_list:
            event = self._extract_event_from_news(news)
            if event:
                events.append(event)
        
        return events
    
    def _extract_event_from_news(self, news: CompanyNews) -> Optional[PoliticalEvent]:
        """Extract political event from news article"""
        title_lower = news.title.lower()
        
        # Determine event type
        event_type = self._classify_event_type(title_lower)
        if not event_type:
            return None
        
        # Determine impact level
        impact_level = self._assess_impact_level(title_lower, event_type)
        
        # Identify affected sectors
        affected_sectors = self._identify_affected_sectors(title_lower)
        
        # Calculate sentiment score
        sentiment_score = self._calculate_sentiment(title_lower)
        
        # Calculate market impact score
        market_impact_score = self._calculate_market_impact(event_type, impact_level, affected_sectors)
        
        return PoliticalEvent(
            title=news.title,
            description=news.title,  # Could be expanded with article content
            event_type=event_type,
            date=datetime.fromisoformat(news.date.replace('Z', '+00:00')),
            impact_level=impact_level,
            affected_sectors=affected_sectors,
            country="US",  # Could be determined from content
            source=news.source,
            sentiment_score=sentiment_score,
            market_impact_score=market_impact_score,
            keywords=self._extract_keywords(title_lower),
            url=news.url
        )
    
    def _classify_event_type(self, text: str) -> Optional[PoliticalEventType]:
        """Classify the type of political event"""
        classifiers = {
            PoliticalEventType.ELECTION: ["election", "vote", "campaign", "polls"],
            PoliticalEventType.SANCTIONS: ["sanctions", "embargo", "trade war"],
            PoliticalEventType.FISCAL_POLICY: ["budget", "spending", "stimulus", "deficit"],
            PoliticalEventType.TRADE_POLICY: ["trade", "tariffs", "import", "export"],
            PoliticalEventType.REGULATORY_CHANGE: ["regulation", "regulatory", "SEC", "FDA"],
            PoliticalEventType.GEOPOLITICAL_TENSION: ["war", "conflict", "tension", "military"],
            PoliticalEventType.DEBT_CEILING: ["debt ceiling", "debt limit"],
            PoliticalEventType.TAX_POLICY: ["tax", "taxation", "IRS"]
        }
        
        for event_type, keywords in classifiers.items():
            if any(keyword in text for keyword in keywords):
                return event_type
        
        return PoliticalEventType.POLICY_ANNOUNCEMENT  # Default
    
    def _assess_impact_level(self, text: str, event_type: PoliticalEventType) -> PoliticalImpact:
        """Assess the impact level of the event"""
        high_impact_events = {
            PoliticalEventType.ELECTION,
            PoliticalEventType.SANCTIONS,
            PoliticalEventType.DEBT_CEILING,
            PoliticalEventType.GEOPOLITICAL_TENSION
        }
        
        high_impact_keywords = ["major", "significant", "unprecedented", "crisis", "emergency"]
        
        if event_type in high_impact_events:
            return PoliticalImpact.HIGH
        
        if any(keyword in text for keyword in high_impact_keywords):
            return PoliticalImpact.HIGH
        
        return PoliticalImpact.MEDIUM  # Default
    
    def _identify_affected_sectors(self, text: str) -> List[MarketSector]:
        """Identify which market sectors are affected"""
        affected_sectors = []
        
        for sector, keywords in self.sector_keywords.items():
            if any(keyword in text for keyword in keywords):
                affected_sectors.append(sector)
        
        # If no specific sectors identified, assume broad market impact
        if not affected_sectors:
            affected_sectors.append(MarketSector.BROAD_MARKET)
        
        return affected_sectors
    
    def _calculate_sentiment(self, text: str) -> float:
        """Calculate sentiment score for the event"""
        positive_words = ["growth", "improvement", "positive", "boost", "strong", "agreement"]
        negative_words = ["crisis", "decline", "tension", "conflict", "concern", "risk", "shutdown"]
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        total_words = positive_count + negative_count
        if total_words == 0:
            return 0.0
        
        return (positive_count - negative_count) / total_words
    
    def _calculate_market_impact(self, event_type: PoliticalEventType, 
                                impact_level: PoliticalImpact, 
                                affected_sectors: List[MarketSector]) -> float:
        """Calculate market impact score (0-10)"""
        base_scores = {
            PoliticalEventType.ELECTION: 8.0,
            PoliticalEventType.SANCTIONS: 7.0,
            PoliticalEventType.DEBT_CEILING: 9.0,
            PoliticalEventType.FISCAL_POLICY: 6.0,
            PoliticalEventType.GEOPOLITICAL_TENSION: 8.0,
            PoliticalEventType.TRADE_POLICY: 6.0,
            PoliticalEventType.REGULATORY_CHANGE: 5.0
        }
        
        base_score = base_scores.get(event_type, 4.0)
        
        # Adjust for impact level
        impact_multipliers = {
            PoliticalImpact.HIGH: 1.2,
            PoliticalImpact.MEDIUM: 1.0,
            PoliticalImpact.LOW: 0.8
        }
        
        score = base_score * impact_multipliers[impact_level]
        
        # Adjust for number of affected sectors
        if MarketSector.BROAD_MARKET in affected_sectors:
            score *= 1.1
        
        return min(10.0, score)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from text"""
        # Simple keyword extraction (could be enhanced with NLP)
        common_words = {"the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "is", "are", "was", "were"}
        words = re.findall(r'\b\w+\b', text.lower())
        keywords = [word for word in words if len(word) > 3 and word not in common_words]
        return list(set(keywords))[:10]  # Return top 10 unique keywords

class PoliticalSignalsManager:
    """Manages political signals monitoring"""
    
    def __init__(self, api_keys: Dict[str, str]):
        self.news_provider = PoliticalNewsProvider(api_keys)
        self.event_analyzer = PoliticalEventAnalyzer()
        self.cache = Cache()
        self.active_events: List[PoliticalEvent] = []
    
    async def start(self) -> None:
        """Start the political signals manager"""
        await self.news_provider.connect()
        logger.info("Political signals manager started")
    
    async def stop(self) -> None:
        """Stop the political signals manager"""
        await self.news_provider.disconnect()
        logger.info("Political signals manager stopped")
    
    async def update_political_events(self) -> List[PoliticalEvent]:
        """Update political events from news sources"""
        # Fetch recent news
        news_articles = await self.news_provider.fetch_political_news(hours_back=24)
        
        # Analyze for political events
        new_events = self.event_analyzer.analyze_news_for_events(news_articles)
        
        # Update active events
        self.active_events = self._merge_events(self.active_events, new_events)
        
        # Cache the events
        self.cache.set("political_events", self.active_events, ttl=3600)
        
        return self.active_events
    
    def get_high_impact_events(self, days_back: int = 7) -> List[PoliticalEvent]:
        """Get high impact political events from recent period"""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        high_impact_events = [
            event for event in self.active_events
            if event.impact_level == PoliticalImpact.HIGH and event.date >= cutoff_date
        ]
        
        # Sort by urgency score
        high_impact_events.sort(key=lambda x: x.urgency_score, reverse=True)
        
        return high_impact_events
    
    def get_sector_specific_events(self, sector: MarketSector, days_back: int = 30) -> List[PoliticalEvent]:
        """Get events affecting a specific sector"""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        sector_events = [
            event for event in self.active_events
            if sector in event.affected_sectors and event.date >= cutoff_date
        ]
        
        return sorted(sector_events, key=lambda x: x.date, reverse=True)
    
    def _merge_events(self, existing_events: List[PoliticalEvent], 
                     new_events: List[PoliticalEvent]) -> List[PoliticalEvent]:
        """Merge new events with existing ones, avoiding duplicates"""
        merged_events = existing_events.copy()
        
        for new_event in new_events:
            # Simple duplicate detection based on title similarity
            is_duplicate = any(
                self._events_similar(new_event, existing_event)
                for existing_event in existing_events
            )
            
            if not is_duplicate:
                merged_events.append(new_event)
        
        # Remove old events (older than 90 days)
        cutoff_date = datetime.now() - timedelta(days=90)
        merged_events = [event for event in merged_events if event.date >= cutoff_date]
        
        return merged_events
    
    def _events_similar(self, event1: PoliticalEvent, event2: PoliticalEvent) -> bool:
        """Check if two events are similar (likely duplicates)"""
        # Simple similarity check based on title and date
        title_similarity = len(set(event1.title.lower().split()) & set(event2.title.lower().split()))
        date_diff = abs((event1.date - event2.date).days)
        
        return title_similarity >= 3 and date_diff <= 1

# Example usage
async def example_usage():
    """Example of how to use the political signals system"""
    
    # Initialize with your API keys
    api_keys = {
        "newsapi": "your_newsapi_key",
        # Add other API keys as needed
    }
    
    manager = PoliticalSignalsManager(api_keys)
    
    await manager.start()
    
    # Update political events
    events = await manager.update_political_events()
    print(f"Found {len(events)} political events")
    
    # Get high impact events
    high_impact = manager.get_high_impact_events()
    print(f"High impact events: {len(high_impact)}")
    
    for event in high_impact[:3]:  # Show top 3
        print(f"- {event.title} (Impact: {event.market_impact_score:.1f}/10)")
    
    # Get sector-specific events
    tech_events = manager.get_sector_specific_events(MarketSector.TECHNOLOGY)
    print(f"Technology sector events: {len(tech_events)}")
    
    await manager.stop()

if __name__ == "__main__":
    asyncio.run(example_usage())