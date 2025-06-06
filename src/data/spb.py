"""
Module for working with Saint Petersburg Exchange (SPB) data.
Provides functionality to fetch and analyze stock data from SPB Exchange.
"""

import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging
from tinkoff.invest import (
    Client,
    CandleInterval,
    RequestError,
    MarketDataRequest,
    GetCandlesRequest,
    HistoricCandle
)
from tinkoff.invest.utils import now

logger = logging.getLogger(__name__)

class SPBClient:
    """Client for interacting with SPB Exchange API"""
    
    BASE_URL = "https://spbexchange.ru/ru/market-data/default.aspx"
    
    def __init__(self):
        self.session = requests.Session()
        
    def get_securities_list(self) -> pd.DataFrame:
        """Get list of all traded securities on SPB Exchange"""
        # Note: SPB Exchange doesn't provide a direct API, so we need to parse their website
        # This is a placeholder for actual implementation
        raise NotImplementedError("Direct API access to SPB Exchange is not available. "
                                "Consider using data providers like Tinkoff, Finam, or Interactive Brokers.")

class SPBDataProvider:
    """
    Data provider for SPB Exchange securities.
    Supports multiple data sources (currently only Tinkoff).
    """
    
    def __init__(self, provider: str = 'tinkoff', **kwargs):
        """
        Initialize the data provider.
        
        Args:
            provider: Data provider name ('tinkoff', 'finam', 'ibkr')
            **kwargs: Provider-specific arguments (e.g. API tokens)
        """
        self.provider = provider.lower()
        
        if self.provider == 'tinkoff':
            if 'token' not in kwargs:
                raise ValueError("Tinkoff API token is required")
            self.token = kwargs['token']
            self._init_tinkoff()
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def _init_tinkoff(self):
        """Initialize Tinkoff API client."""
        try:
            self.client = Client(self.token)
            logger.info("Successfully connected to Tinkoff Investments API")
        except Exception as e:
            logger.error(f"Failed to initialize Tinkoff client: {e}")
            raise
    
    def _get_tinkoff_figi(self, ticker: str) -> str:
        """Get FIGI identifier for a ticker."""
        try:
            instruments = self.client.instruments
            for method in [
                instruments.shares,
                instruments.bonds,
                instruments.etfs,
                instruments.currencies
            ]:
                for item in method().instruments:
                    if item.ticker == ticker:
                        return item.figi
            raise ValueError(f"Ticker {ticker} not found")
        except Exception as e:
            logger.error(f"Error getting FIGI for {ticker}: {e}")
            raise
    
    def get_historical_data(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = '1d'
    ) -> pd.DataFrame:
        """
        Get historical OHLCV data.
        
        Args:
            ticker: Security ticker
            start_date: Start date
            end_date: End date
            interval: Candle interval ('1m', '5m', '15m', '1h', '1d')
        
        Returns:
            DataFrame with columns: DATE, OPEN, HIGH, LOW, CLOSE, VOLUME
        """
        if self.provider == 'tinkoff':
            return self._get_tinkoff_historical_data(ticker, start_date, end_date, interval)
        raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _get_tinkoff_historical_data(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = '1d'
    ) -> pd.DataFrame:
        """Get historical data from Tinkoff API."""
        try:
            # Map interval string to Tinkoff enum
            interval_map = {
                '1m': CandleInterval.CANDLE_INTERVAL_1_MIN,
                '5m': CandleInterval.CANDLE_INTERVAL_5_MIN,
                '15m': CandleInterval.CANDLE_INTERVAL_15_MIN,
                '1h': CandleInterval.CANDLE_INTERVAL_HOUR,
                '1d': CandleInterval.CANDLE_INTERVAL_DAY,
            }
            
            if interval not in interval_map:
                raise ValueError(f"Unsupported interval: {interval}")
            
            figi = self._get_tinkoff_figi(ticker)
            
            # Get candles
            with Client(self.token) as client:
                candles = client.market_data.get_candles(
                    figi=figi,
                    from_=start_date,
                    to=end_date,
                    interval=interval_map[interval]
                )
            
            # Convert to DataFrame
            data = []
            for candle in candles.candles:
                data.append({
                    'DATE': candle.time.replace(tzinfo=None),
                    'OPEN': float(candle.open.units) + float(candle.open.nano) / 1e9,
                    'HIGH': float(candle.high.units) + float(candle.high.nano) / 1e9,
                    'LOW': float(candle.low.units) + float(candle.low.nano) / 1e9,
                    'CLOSE': float(candle.close.units) + float(candle.close.nano) / 1e9,
                    'VOLUME': candle.volume
                })
            
            df = pd.DataFrame(data)
            if not df.empty:
                df.set_index('DATE', inplace=True)
            return df
            
        except Exception as e:
            logger.error(f"Error getting historical data for {ticker}: {e}")
            return pd.DataFrame()
    
    def get_market_data(self, ticker: str) -> Dict[str, Any]:
        """Get current market data."""
        if self.provider == 'tinkoff':
            return self._get_tinkoff_market_data(ticker)
        raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _get_tinkoff_market_data(self, ticker: str) -> Dict[str, Any]:
        """Get current market data from Tinkoff API."""
        try:
            figi = self._get_tinkoff_figi(ticker)
            
            with Client(self.token) as client:
                response = client.market_data.get_last_prices(figi=[figi])
                
                if not response.last_prices:
                    return {}
                
                last_price = response.last_prices[0]
                price = float(last_price.price.units) + float(last_price.price.nano) / 1e9
                
                return {
                    'last_price': price,
                    'time': last_price.time.replace(tzinfo=None)
                }
                
        except Exception as e:
            logger.error(f"Error getting market data for {ticker}: {e}")
            return {}

def get_spb_data(
    ticker: str,
    provider: str = 'tinkoff',
    **credentials
) -> Dict[str, Any]:
    """
    Get data for a stock traded on SPB Exchange
    
    Args:
        ticker: Stock ticker symbol
        provider: Data provider to use
        **credentials: Provider-specific credentials
        
    Returns:
        Dictionary containing stock data and metadata
    """
    try:
        data_provider = SPBDataProvider(provider, **credentials)
        historical_data = data_provider.get_historical_data(ticker)
        
        return {
            'ticker': ticker,
            'provider': provider,
            'data': historical_data
        }
        
    except Exception as e:
        logger.error(f"Error fetching SPB data for {ticker}: {str(e)}")
        raise 