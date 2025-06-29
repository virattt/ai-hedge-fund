"""
Economic indicators data feed for Fed statements, unemployment, CPI, interest rates, etc.
Integrates with various economic data sources for macro analysis.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import aiohttp
import pandas as pd
from pathlib import Path

from .cache import Cache

logger = logging.getLogger(__name__)

class IndicatorType(str, Enum):
    """Types of economic indicators"""
    INTEREST_RATES = "interest_rates"
    INFLATION = "inflation" 
    EMPLOYMENT = "employment"
    GDP = "gdp"
    CONSUMER_CONFIDENCE = "consumer_confidence"
    MANUFACTURING = "manufacturing"
    HOUSING = "housing"
    MONETARY_POLICY = "monetary_policy"
    TRADE = "trade"
    MARKET_SENTIMENT = "market_sentiment"

class IndicatorImportance(str, Enum):
    """Importance levels for indicators"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class EconomicIndicator:
    """Economic indicator data point"""
    name: str
    value: float
    previous_value: Optional[float]
    forecast: Optional[float]
    timestamp: datetime
    indicator_type: IndicatorType
    importance: IndicatorImportance
    source: str
    unit: str
    frequency: str  # daily, weekly, monthly, quarterly, annual
    country: str = "US"
    description: Optional[str] = None
    
    @property
    def change(self) -> Optional[float]:
        """Calculate change from previous value"""
        if self.previous_value is not None:
            return self.value - self.previous_value
        return None
    
    @property
    def change_percent(self) -> Optional[float]:
        """Calculate percentage change from previous value"""
        if self.previous_value is not None and self.previous_value != 0:
            return ((self.value - self.previous_value) / self.previous_value) * 100
        return None
    
    @property
    def vs_forecast(self) -> Optional[float]:
        """Calculate difference from forecast"""
        if self.forecast is not None:
            return self.value - self.forecast
        return None

@dataclass
class FedStatement:
    """Federal Reserve statement data"""
    date: datetime
    title: str
    content: str
    decision: str  # "hold", "raise", "cut"
    rate_change: float  # Basis points
    current_rate: float
    tone: str  # "hawkish", "dovish", "neutral"
    key_themes: List[str]
    market_impact_score: float  # 0-10 scale
    
@dataclass
class EconomicEvent:
    """Scheduled economic event"""
    name: str
    date: datetime
    importance: IndicatorImportance
    forecast: Optional[float]
    previous: Optional[float]
    actual: Optional[float]
    currency: str
    country: str
    description: str

class EconomicDataProvider:
    """Base class for economic data providers"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache = Cache()
    
    async def connect(self) -> None:
        """Initialize connection"""
        self.session = aiohttp.ClientSession()
    
    async def disconnect(self) -> None:
        """Close connection"""
        if self.session:
            await self.session.close()

class FREDProvider(EconomicDataProvider):
    """Federal Reserve Economic Data (FRED) provider"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://api.stlouisfed.org/fred"
        
        # Key FRED series IDs
        self.series_mapping = {
            "fed_funds_rate": "FEDFUNDS",
            "unemployment_rate": "UNRATE", 
            "cpi_all_items": "CPIAUCSL",
            "core_cpi": "CPILFESL",
            "gdp": "GDP",
            "real_gdp": "GDPC1",
            "consumer_confidence": "UMCSENT",
            "manufacturing_pmi": "NAPM",
            "housing_starts": "HOUST",
            "industrial_production": "INDPRO",
            "retail_sales": "RSAFS",
            "nonfarm_payrolls": "PAYEMS",
            "initial_claims": "ICSA",
            "10_year_treasury": "GS10",
            "2_year_treasury": "GS2",
            "yield_curve_spread": "T10Y2Y"
        }
    
    async def get_series_data(self, series_id: str, limit: int = 100) -> List[Dict]:
        """Get data for a specific FRED series"""
        if not self.session:
            await self.connect()
        
        cache_key = f"fred_{series_id}_{limit}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        url = f"{self.base_url}/series/observations"
        params = {
            'series_id': series_id,
            'api_key': self.api_key,
            'file_type': 'json',
            'limit': limit,
            'sort_order': 'desc'
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                data = await response.json()
                observations = data.get('observations', [])
                
                # Cache for 1 hour
                self.cache.set(cache_key, observations, ttl=3600)
                return observations
        except Exception as e:
            logger.error(f"Error fetching FRED data for {series_id}: {e}")
            return []
    
    async def get_indicator(self, indicator_name: str) -> Optional[EconomicIndicator]:
        """Get latest value for an economic indicator"""
        if indicator_name not in self.series_mapping:
            logger.warning(f"Unknown indicator: {indicator_name}")
            return None
        
        series_id = self.series_mapping[indicator_name]
        data = await self.get_series_data(series_id, limit=2)
        
        if not data:
            return None
        
        # Get latest and previous values
        latest = data[0]
        previous = data[1] if len(data) > 1 else None
        
        # Map to indicator type
        indicator_type = self._map_to_indicator_type(indicator_name)
        importance = self._get_indicator_importance(indicator_name)
        
        try:
            return EconomicIndicator(
                name=indicator_name,
                value=float(latest['value']),
                previous_value=float(previous['value']) if previous and previous['value'] != '.' else None,
                forecast=None,  # FRED doesn't provide forecasts
                timestamp=datetime.strptime(latest['date'], '%Y-%m-%d'),
                indicator_type=indicator_type,
                importance=importance,
                source="FRED",
                unit=self._get_unit(indicator_name),
                frequency=self._get_frequency(indicator_name),
                description=self._get_description(indicator_name)
            )
        except (ValueError, KeyError) as e:
            logger.error(f"Error parsing FRED data for {indicator_name}: {e}")
            return None
    
    def _map_to_indicator_type(self, indicator_name: str) -> IndicatorType:
        """Map indicator name to type"""
        mapping = {
            "fed_funds_rate": IndicatorType.INTEREST_RATES,
            "unemployment_rate": IndicatorType.EMPLOYMENT,
            "cpi_all_items": IndicatorType.INFLATION,
            "core_cpi": IndicatorType.INFLATION,
            "gdp": IndicatorType.GDP,
            "real_gdp": IndicatorType.GDP,
            "consumer_confidence": IndicatorType.CONSUMER_CONFIDENCE,
            "manufacturing_pmi": IndicatorType.MANUFACTURING,
            "housing_starts": IndicatorType.HOUSING,
            "10_year_treasury": IndicatorType.INTEREST_RATES,
            "2_year_treasury": IndicatorType.INTEREST_RATES,
            "yield_curve_spread": IndicatorType.INTEREST_RATES
        }
        return mapping.get(indicator_name, IndicatorType.MARKET_SENTIMENT)
    
    def _get_indicator_importance(self, indicator_name: str) -> IndicatorImportance:
        """Get importance level for indicator"""
        high_importance = {
            "fed_funds_rate", "unemployment_rate", "cpi_all_items", "core_cpi", 
            "gdp", "nonfarm_payrolls", "10_year_treasury"
        }
        medium_importance = {
            "consumer_confidence", "manufacturing_pmi", "housing_starts", 
            "initial_claims", "2_year_treasury"
        }
        
        if indicator_name in high_importance:
            return IndicatorImportance.HIGH
        elif indicator_name in medium_importance:
            return IndicatorImportance.MEDIUM
        else:
            return IndicatorImportance.LOW
    
    def _get_unit(self, indicator_name: str) -> str:
        """Get unit for indicator"""
        units = {
            "fed_funds_rate": "Percent",
            "unemployment_rate": "Percent", 
            "cpi_all_items": "Index",
            "core_cpi": "Index",
            "gdp": "Billions of Dollars",
            "consumer_confidence": "Index",
            "housing_starts": "Thousands of Units",
            "nonfarm_payrolls": "Thousands of Persons",
            "initial_claims": "Number",
            "10_year_treasury": "Percent",
            "2_year_treasury": "Percent"
        }
        return units.get(indicator_name, "")
    
    def _get_frequency(self, indicator_name: str) -> str:
        """Get frequency for indicator"""
        frequencies = {
            "fed_funds_rate": "monthly",
            "unemployment_rate": "monthly",
            "cpi_all_items": "monthly", 
            "core_cpi": "monthly",
            "gdp": "quarterly",
            "consumer_confidence": "monthly",
            "housing_starts": "monthly",
            "nonfarm_payrolls": "monthly",
            "initial_claims": "weekly",
            "10_year_treasury": "daily",
            "2_year_treasury": "daily"
        }
        return frequencies.get(indicator_name, "monthly")
    
    def _get_description(self, indicator_name: str) -> str:
        """Get description for indicator"""
        descriptions = {
            "fed_funds_rate": "Federal Funds Effective Rate",
            "unemployment_rate": "Unemployment Rate",
            "cpi_all_items": "Consumer Price Index for All Urban Consumers: All Items",
            "core_cpi": "Consumer Price Index for All Urban Consumers: All Items Less Food and Energy",
            "gdp": "Gross Domestic Product",
            "consumer_confidence": "University of Michigan Consumer Sentiment",
            "housing_starts": "Housing Starts: Total: New Privately Owned Housing Units Started",
            "nonfarm_payrolls": "All Employees, Total Nonfarm",
            "initial_claims": "Initial Claims for Unemployment Insurance",
            "10_year_treasury": "10-Year Treasury Constant Maturity Rate",
            "2_year_treasury": "2-Year Treasury Constant Maturity Rate"
        }
        return descriptions.get(indicator_name, "")

class EconomicCalendarProvider(EconomicDataProvider):
    """Economic calendar provider for scheduled events"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.base_url = "https://financialdata.io/api/v1/economic-calendar"  # Example API
    
    async def get_upcoming_events(self, days_ahead: int = 7) -> List[EconomicEvent]:
        """Get upcoming economic events"""
        if not self.session:
            await self.connect()
        
        cache_key = f"economic_calendar_{days_ahead}"
        cached_events = self.cache.get(cache_key)
        if cached_events:
            return cached_events
        
        # Mock data for demonstration (replace with actual API call)
        upcoming_events = [
            EconomicEvent(
                name="Non-Farm Payrolls",
                date=datetime.now() + timedelta(days=2),
                importance=IndicatorImportance.HIGH,
                forecast=180000,
                previous=150000,
                actual=None,
                currency="USD",
                country="US",
                description="Change in the number of employed people during the previous month"
            ),
            EconomicEvent(
                name="Consumer Price Index",
                date=datetime.now() + timedelta(days=5),
                importance=IndicatorImportance.HIGH,
                forecast=3.2,
                previous=3.1,
                actual=None,
                currency="USD",
                country="US", 
                description="Change in the price of goods and services"
            )
        ]
        
        # Cache for 4 hours
        self.cache.set(cache_key, upcoming_events, ttl=14400)
        return upcoming_events

class FedWatchProvider(EconomicDataProvider):
    """Federal Reserve communications and policy tracking"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.federalreserve.gov"
    
    async def get_recent_statements(self, limit: int = 10) -> List[FedStatement]:
        """Get recent Fed statements and decisions"""
        # Mock data for demonstration
        statements = [
            FedStatement(
                date=datetime.now() - timedelta(days=45),
                title="Federal Reserve maintains target range for federal funds rate at 5.25 to 5.5 percent",
                content="The Federal Reserve decided to maintain the target range...",
                decision="hold",
                rate_change=0,
                current_rate=5.375,
                tone="neutral",
                key_themes=["inflation", "employment", "economic outlook"],
                market_impact_score=7.5
            )
        ]
        return statements
    
    async def analyze_fed_tone(self, statement_text: str) -> Dict[str, Any]:
        """Analyze Fed statement tone using NLP"""
        # Placeholder for NLP analysis
        # In production, you'd use a proper NLP model
        
        hawkish_words = ["inflation", "tighten", "raise", "aggressive", "concern"]
        dovish_words = ["support", "accommodate", "lower", "stimulus", "gradual"]
        
        hawkish_score = sum(1 for word in hawkish_words if word in statement_text.lower())
        dovish_score = sum(1 for word in dovish_words if word in statement_text.lower())
        
        if hawkish_score > dovish_score:
            tone = "hawkish"
            confidence = hawkish_score / (hawkish_score + dovish_score)
        elif dovish_score > hawkish_score:
            tone = "dovish"
            confidence = dovish_score / (hawkish_score + dovish_score)
        else:
            tone = "neutral"
            confidence = 0.5
        
        return {
            "tone": tone,
            "confidence": confidence,
            "hawkish_score": hawkish_score,
            "dovish_score": dovish_score
        }

class EconomicDataManager:
    """Manages economic data from multiple sources"""
    
    def __init__(self, fred_api_key: str):
        self.fred_provider = FREDProvider(fred_api_key)
        self.calendar_provider = EconomicCalendarProvider()
        self.fed_provider = FedWatchProvider()
        self.cache = Cache()
        
        # Key indicators to track
        self.key_indicators = [
            "fed_funds_rate", "unemployment_rate", "cpi_all_items", "core_cpi",
            "gdp", "consumer_confidence", "manufacturing_pmi", "housing_starts",
            "nonfarm_payrolls", "initial_claims", "10_year_treasury", "2_year_treasury"
        ]
    
    async def start(self) -> None:
        """Start all providers"""
        await self.fred_provider.connect()
        await self.calendar_provider.connect()
        await self.fed_provider.connect()
        logger.info("Economic data manager started")
    
    async def stop(self) -> None:
        """Stop all providers"""
        await self.fred_provider.disconnect()
        await self.calendar_provider.disconnect()
        await self.fed_provider.disconnect()
        logger.info("Economic data manager stopped")
    
    async def get_all_indicators(self) -> Dict[str, EconomicIndicator]:
        """Get all key economic indicators"""
        indicators = {}
        
        for indicator_name in self.key_indicators:
            try:
                indicator = await self.fred_provider.get_indicator(indicator_name)
                if indicator:
                    indicators[indicator_name] = indicator
            except Exception as e:
                logger.error(f"Error fetching {indicator_name}: {e}")
        
        return indicators
    
    async def get_economic_summary(self) -> Dict[str, Any]:
        """Get comprehensive economic summary"""
        indicators = await self.get_all_indicators()
        upcoming_events = await self.calendar_provider.get_upcoming_events()
        fed_statements = await self.fed_provider.get_recent_statements()
        
        # Calculate economic health score
        health_score = self._calculate_economic_health_score(indicators)
        
        return {
            "indicators": indicators,
            "upcoming_events": upcoming_events,
            "fed_statements": fed_statements,
            "health_score": health_score,
            "last_updated": datetime.now(),
            "summary": self._generate_summary(indicators, health_score)
        }
    
    def _calculate_economic_health_score(self, indicators: Dict[str, EconomicIndicator]) -> float:
        """Calculate overall economic health score (0-100)"""
        score = 50  # Start with neutral
        
        # Unemployment rate (lower is better)
        if "unemployment_rate" in indicators:
            unemployment = indicators["unemployment_rate"]
            if unemployment.value < 4.0:
                score += 10
            elif unemployment.value > 6.0:
                score -= 10
        
        # GDP growth (positive is better)
        if "gdp" in indicators:
            gdp = indicators["gdp"]
            if gdp.change_percent and gdp.change_percent > 2.0:
                score += 10
            elif gdp.change_percent and gdp.change_percent < 0:
                score -= 15
        
        # Inflation (target around 2%)
        if "core_cpi" in indicators:
            cpi = indicators["core_cpi"]
            if cpi.change_percent:
                if 1.5 <= cpi.change_percent <= 2.5:
                    score += 10
                elif cpi.change_percent > 4.0:
                    score -= 15
        
        # Consumer confidence
        if "consumer_confidence" in indicators:
            confidence = indicators["consumer_confidence"]
            if confidence.value > 100:
                score += 5
            elif confidence.value < 80:
                score -= 5
        
        return max(0, min(100, score))
    
    def _generate_summary(self, indicators: Dict[str, EconomicIndicator], health_score: float) -> str:
        """Generate text summary of economic conditions"""
        if health_score >= 70:
            outlook = "positive"
        elif health_score >= 50:
            outlook = "neutral"
        else:
            outlook = "concerning"
        
        summary = f"Economic outlook appears {outlook} (score: {health_score:.1f}/100). "
        
        # Add key highlights
        if "unemployment_rate" in indicators:
            unemployment = indicators["unemployment_rate"]
            summary += f"Unemployment at {unemployment.value}%. "
        
        if "core_cpi" in indicators:
            cpi = indicators["core_cpi"]
            if cpi.change_percent:
                summary += f"Core inflation running at {cpi.change_percent:.1f}% annually. "
        
        if "fed_funds_rate" in indicators:
            fed_rate = indicators["fed_funds_rate"]
            summary += f"Fed funds rate at {fed_rate.value}%. "
        
        return summary

# Example usage
async def example_usage():
    """Example of how to use the economic data system"""
    
    # Initialize with your FRED API key
    manager = EconomicDataManager(fred_api_key="your_fred_api_key")
    
    await manager.start()
    
    # Get economic summary
    summary = await manager.get_economic_summary()
    print("Economic Summary:")
    print(summary["summary"])
    print(f"Health Score: {summary['health_score']:.1f}/100")
    
    # Get specific indicator
    unemployment = await manager.fred_provider.get_indicator("unemployment_rate")
    if unemployment:
        print(f"Unemployment Rate: {unemployment.value}% (prev: {unemployment.previous_value}%)")
    
    await manager.stop()

if __name__ == "__main__":
    asyncio.run(example_usage())