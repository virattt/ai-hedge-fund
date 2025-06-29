"""
Real-time data pipeline for market data, options Greeks, and implied volatility.
Supports multiple data providers and WebSocket streaming.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Protocol
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
import websockets
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from threading import Lock

from .models import Price, OptionsInfo, Greeks, SecurityInfo
from .cache import Cache

logger = logging.getLogger(__name__)

@dataclass
class RealTimeQuote:
    """Real-time market quote"""
    ticker: str
    bid: float
    ask: float
    last: float
    volume: int
    timestamp: datetime
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None

@dataclass
class RealTimeOptionsQuote:
    """Real-time options quote with Greeks"""
    ticker: str
    underlying_ticker: str
    strike: float
    expiration: str
    option_type: str  # 'call' or 'put'
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    implied_volatility: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    timestamp: datetime

@dataclass
class MarketEvent:
    """Market event for event-driven processing"""
    event_type: str  # 'quote', 'trade', 'options_quote', 'market_status'
    data: Dict[str, Any]
    timestamp: datetime

class DataProvider(ABC):
    """Abstract base class for data providers"""
    
    @abstractmethod
    async def connect(self) -> None:
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        pass
    
    @abstractmethod
    async def subscribe_quotes(self, symbols: List[str]) -> None:
        pass
    
    @abstractmethod
    async def subscribe_options(self, symbols: List[str]) -> None:
        pass
    
    @abstractmethod
    async def get_options_chain(self, symbol: str) -> List[OptionsInfo]:
        pass

class AlphaVantageProvider(DataProvider):
    """Alpha Vantage real-time data provider"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.base_url = "https://www.alphavantage.co/query"
        
    async def connect(self) -> None:
        self.session = aiohttp.ClientSession()
        logger.info("Connected to Alpha Vantage")
    
    async def disconnect(self) -> None:
        if self.session:
            await self.session.close()
        logger.info("Disconnected from Alpha Vantage")
    
    async def subscribe_quotes(self, symbols: List[str]) -> None:
        # Alpha Vantage doesn't have real-time WebSocket, so we'll poll
        logger.info(f"Subscribing to quotes for {symbols}")
    
    async def subscribe_options(self, symbols: List[str]) -> None:
        logger.info(f"Subscribing to options for {symbols}")
    
    async def get_quote(self, symbol: str) -> RealTimeQuote:
        """Get real-time quote"""
        if not self.session:
            raise ValueError("Not connected")
        
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol,
            'apikey': self.api_key
        }
        
        async with self.session.get(self.base_url, params=params) as response:
            data = await response.json()
            quote_data = data.get('Global Quote', {})
            
            return RealTimeQuote(
                ticker=symbol,
                bid=0.0,  # Not available in Global Quote
                ask=0.0,  # Not available in Global Quote  
                last=float(quote_data.get('05. price', 0)),
                volume=int(quote_data.get('06. volume', 0)),
                timestamp=datetime.now(),
                change=float(quote_data.get('09. change', 0)),
                change_percent=float(quote_data.get('10. change percent', '0%').rstrip('%'))
            )
    
    async def get_options_chain(self, symbol: str) -> List[OptionsInfo]:
        """Get options chain (simulated for Alpha Vantage)"""
        # Alpha Vantage doesn't provide options data, so we'll return empty
        logger.warning(f"Options data not available for {symbol} via Alpha Vantage")
        return []

class PolygonProvider(DataProvider):
    """Polygon.io real-time data provider"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.base_url = "https://api.polygon.io"
        self.ws_url = f"wss://socket.polygon.io/stocks"
        
    async def connect(self) -> None:
        self.session = aiohttp.ClientSession()
        # Connect to WebSocket
        try:
            self.websocket = await websockets.connect(self.ws_url)
            # Authenticate
            auth_msg = {"action": "auth", "params": self.api_key}
            await self.websocket.send(json.dumps(auth_msg))
            logger.info("Connected to Polygon WebSocket")
        except Exception as e:
            logger.error(f"Failed to connect to Polygon WebSocket: {e}")
    
    async def disconnect(self) -> None:
        if self.websocket:
            await self.websocket.close()
        if self.session:
            await self.session.close()
        logger.info("Disconnected from Polygon")
    
    async def subscribe_quotes(self, symbols: List[str]) -> None:
        if not self.websocket:
            raise ValueError("WebSocket not connected")
        
        # Subscribe to real-time quotes
        subscribe_msg = {
            "action": "subscribe",
            "params": f"Q.{','.join(symbols)}"
        }
        await self.websocket.send(json.dumps(subscribe_msg))
        logger.info(f"Subscribed to quotes for {symbols}")
    
    async def subscribe_options(self, symbols: List[str]) -> None:
        if not self.websocket:
            raise ValueError("WebSocket not connected")
        
        # Subscribe to options quotes
        subscribe_msg = {
            "action": "subscribe", 
            "params": f"O.{','.join(symbols)}"
        }
        await self.websocket.send(json.dumps(subscribe_msg))
        logger.info(f"Subscribed to options for {symbols}")
    
    async def get_options_chain(self, symbol: str) -> List[OptionsInfo]:
        """Get options chain from Polygon"""
        if not self.session:
            raise ValueError("Not connected")
        
        url = f"{self.base_url}/v3/reference/options/contracts"
        params = {
            'underlying_ticker': symbol,
            'apikey': self.api_key,
            'limit': 1000
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                data = await response.json()
                options_data = data.get('results', [])
                
                options_list = []
                for option in options_data:
                    options_list.append(OptionsInfo(
                        underlying_ticker=symbol,
                        strike=option.get('strike_price', 0),
                        expiration=datetime.strptime(option.get('expiration_date', ''), '%Y-%m-%d').date(),
                        option_type=option.get('contract_type', '').lower(),
                        option_symbol=option.get('ticker', '')
                    ))
                
                return options_list
        except Exception as e:
            logger.error(f"Error fetching options chain for {symbol}: {e}")
            return []

class RealTimeDataManager:
    """Manages real-time data feeds and distribution"""
    
    def __init__(self, provider: DataProvider, cache: Optional[Cache] = None):
        self.provider = provider
        self.cache = cache or Cache()
        self.subscribers: Dict[str, List[Callable]] = {}
        self.is_running = False
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._lock = Lock()
        
    async def start(self) -> None:
        """Start the real-time data manager"""
        await self.provider.connect()
        self.is_running = True
        logger.info("Real-time data manager started")
    
    async def stop(self) -> None:
        """Stop the real-time data manager"""
        self.is_running = False
        await self.provider.disconnect()
        self.executor.shutdown(wait=True)
        logger.info("Real-time data manager stopped")
    
    def subscribe_to_quotes(self, symbols: List[str], callback: Callable[[RealTimeQuote], None]) -> None:
        """Subscribe to real-time quotes"""
        with self._lock:
            for symbol in symbols:
                if symbol not in self.subscribers:
                    self.subscribers[symbol] = []
                self.subscribers[symbol].append(callback)
    
    def unsubscribe_from_quotes(self, symbols: List[str], callback: Callable[[RealTimeQuote], None]) -> None:
        """Unsubscribe from real-time quotes"""
        with self._lock:
            for symbol in symbols:
                if symbol in self.subscribers and callback in self.subscribers[symbol]:
                    self.subscribers[symbol].remove(callback)
    
    async def get_current_quote(self, symbol: str) -> Optional[RealTimeQuote]:
        """Get current quote for a symbol"""
        # Check cache first
        cached_quote = self.cache.get(f"quote_{symbol}")
        if cached_quote and isinstance(cached_quote, RealTimeQuote):
            # Check if quote is recent (within 1 minute)
            if datetime.now() - cached_quote.timestamp < timedelta(minutes=1):
                return cached_quote
        
        # Fetch fresh quote
        try:
            if hasattr(self.provider, 'get_quote'):
                quote = await self.provider.get_quote(symbol)
                self.cache.set(f"quote_{symbol}", quote, ttl=60)  # Cache for 1 minute
                return quote
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
        
        return None
    
    async def get_options_chain(self, symbol: str) -> List[OptionsInfo]:
        """Get options chain for a symbol"""
        # Check cache first
        cache_key = f"options_{symbol}"
        cached_options = self.cache.get(cache_key)
        if cached_options:
            return cached_options
        
        # Fetch fresh options data
        try:
            options = await self.provider.get_options_chain(symbol)
            self.cache.set(cache_key, options, ttl=300)  # Cache for 5 minutes
            return options
        except Exception as e:
            logger.error(f"Error fetching options chain for {symbol}: {e}")
            return []
    
    async def calculate_implied_volatility(self, option: OptionsInfo, underlying_price: float, risk_free_rate: float = 0.05) -> float:
        """Calculate implied volatility using Black-Scholes approximation"""
        try:
            from scipy.optimize import minimize_scalar
            from scipy.stats import norm
            import math
            
            # Black-Scholes calculation
            def black_scholes_call(S, K, T, r, sigma):
                d1 = (math.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*math.sqrt(T))
                d2 = d1 - sigma*math.sqrt(T)
                return S*norm.cdf(d1) - K*math.exp(-r*T)*norm.cdf(d2)
            
            def black_scholes_put(S, K, T, r, sigma):
                d1 = (math.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*math.sqrt(T))
                d2 = d1 - sigma*math.sqrt(T)
                return K*math.exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)
            
            # Calculate time to expiration in years
            T = (option.expiration - datetime.now().date()).days / 365.0
            if T <= 0:
                return 0.0
            
            # Objective function to minimize
            def objective(sigma):
                if option.option_type == 'call':
                    theoretical_price = black_scholes_call(underlying_price, option.strike, T, risk_free_rate, sigma)
                else:
                    theoretical_price = black_scholes_put(underlying_price, option.strike, T, risk_free_rate, sigma)
                return abs(theoretical_price - (option.last_price or 0))
            
            # Find implied volatility
            result = minimize_scalar(objective, bounds=(0.01, 5.0), method='bounded')
            return result.x if result.success else 0.3  # Default to 30% if calculation fails
            
        except ImportError:
            logger.warning("scipy not available for IV calculation, using default")
            return 0.3
        except Exception as e:
            logger.error(f"Error calculating IV: {e}")
            return 0.3
    
    def _notify_subscribers(self, symbol: str, quote: RealTimeQuote) -> None:
        """Notify all subscribers of a quote update"""
        with self._lock:
            if symbol in self.subscribers:
                for callback in self.subscribers[symbol]:
                    try:
                        self.executor.submit(callback, quote)
                    except Exception as e:
                        logger.error(f"Error in callback for {symbol}: {e}")

class MarketDataAggregator:
    """Aggregates data from multiple sources for redundancy"""
    
    def __init__(self, providers: List[DataProvider]):
        self.providers = providers
        self.data_managers = [RealTimeDataManager(provider) for provider in providers]
        self.primary_provider = 0  # Index of primary provider
    
    async def start(self) -> None:
        """Start all data managers"""
        for manager in self.data_managers:
            try:
                await manager.start()
            except Exception as e:
                logger.error(f"Failed to start data manager: {e}")
    
    async def stop(self) -> None:
        """Stop all data managers"""
        for manager in self.data_managers:
            try:
                await manager.stop()
            except Exception as e:
                logger.error(f"Error stopping data manager: {e}")
    
    async def get_best_quote(self, symbol: str) -> Optional[RealTimeQuote]:
        """Get the best quote from all providers"""
        quotes = []
        
        # Try to get quotes from all providers
        for manager in self.data_managers:
            try:
                quote = await manager.get_current_quote(symbol)
                if quote:
                    quotes.append(quote)
            except Exception as e:
                logger.error(f"Error getting quote from provider: {e}")
        
        if not quotes:
            return None
        
        # Return the most recent quote
        return max(quotes, key=lambda q: q.timestamp)
    
    def switch_primary_provider(self, provider_index: int) -> None:
        """Switch to a different primary provider"""
        if 0 <= provider_index < len(self.providers):
            self.primary_provider = provider_index
            logger.info(f"Switched to primary provider {provider_index}")

# Factory function to create data providers
def create_data_provider(provider_name: str, **kwargs) -> DataProvider:
    """Factory function to create data providers"""
    providers = {
        'alphavantage': AlphaVantageProvider,
        'polygon': PolygonProvider,
    }
    
    if provider_name not in providers:
        raise ValueError(f"Unknown provider: {provider_name}")
    
    return providers[provider_name](**kwargs)

# Example usage and testing
async def example_usage():
    """Example of how to use the real-time data system"""
    
    # Create a provider (you would use your actual API key)
    provider = create_data_provider('alphavantage', api_key='demo')
    
    # Create data manager
    manager = RealTimeDataManager(provider)
    
    # Define callback for quote updates
    def on_quote_update(quote: RealTimeQuote):
        print(f"Quote update: {quote.ticker} - ${quote.last} at {quote.timestamp}")
    
    # Start manager and subscribe
    await manager.start()
    manager.subscribe_to_quotes(['AAPL', 'MSFT'], on_quote_update)
    
    # Subscribe to quotes via provider
    await provider.subscribe_quotes(['AAPL', 'MSFT'])
    
    # Get current quote
    quote = await manager.get_current_quote('AAPL')
    if quote:
        print(f"Current AAPL quote: ${quote.last}")
    
    # Get options chain
    options = await manager.get_options_chain('AAPL')
    print(f"Found {len(options)} options contracts for AAPL")
    
    # Stop manager
    await manager.stop()

if __name__ == "__main__":
    asyncio.run(example_usage())