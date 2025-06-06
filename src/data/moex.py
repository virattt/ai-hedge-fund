"""
Module for working with Moscow Exchange (MOEX) data.
Provides functionality to fetch and analyze stock data from MOEX.
"""

import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class MOEXClient:
    """
    Client for interacting with the MOEX ISS API.
    Documentation: https://iss.moex.com/iss/reference/
    """
    
    def __init__(self):
        self.base_url = "https://iss.moex.com/iss"
        self.session = requests.Session()
    
    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """Make a request to the MOEX API."""
        if params is None:
            params = {}
        
        # Always request JSON format
        params['iss.json'] = 'extended'
        params['iss.meta'] = 'off'
        
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to {url}: {e}")
            raise
    
    def get_security_info(self, ticker: str) -> Dict[str, Any]:
        """Get detailed information about a security."""
        endpoint = f"securities/{ticker}.json"
        response = self._make_request(endpoint)
        data = response.json()
        
        # Extract description block
        description = {}
        if 'description' in data and len(data['description']) > 0:
            description = {
                item[0]: item[2]
                for item in data['description'][0]
                if len(item) >= 3
            }
        
        return description
    
    def get_market_data(self, ticker: str) -> pd.DataFrame:
        """Get current market data for a security."""
        endpoint = f"engines/stock/markets/shares/securities/{ticker}.json"
        response = self._make_request(endpoint)
        data = response.json()
        
        # Convert marketdata block to DataFrame
        if 'marketdata' in data and len(data['marketdata']) > 0:
            df = pd.DataFrame(data['marketdata'])
            return df
        return pd.DataFrame()
    
    def get_historical_data(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        interval: int = 24
    ) -> pd.DataFrame:
        """
        Get historical OHLCV data for a security.
        
        Args:
            ticker: Security ticker
            start_date: Start date
            end_date: End date
            interval: Candle interval in hours (24 for daily)
        
        Returns:
            DataFrame with columns: DATE, OPEN, HIGH, LOW, CLOSE, VOLUME
        """
        # Format dates
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        endpoint = f"history/engines/stock/markets/shares/securities/{ticker}/candels.json"
        params = {
            'from': start_str,
            'till': end_str,
            'interval': interval
        }
        
        response = self._make_request(endpoint, params)
        data = response.json()
        
        # Convert candles to DataFrame
        if 'candles' in data and len(data['candles']) > 0:
            df = pd.DataFrame(data['candles'])
            
            # Rename columns to standard format
            df = df.rename(columns={
                'begin': 'DATE',
                'open': 'OPEN',
                'high': 'HIGH',
                'low': 'LOW',
                'close': 'CLOSE',
                'volume': 'VOLUME'
            })
            
            # Convert date column
            df['DATE'] = pd.to_datetime(df['DATE'])
            
            return df
        
        return pd.DataFrame()
    
    def get_all_securities(self) -> pd.DataFrame:
        """Get a list of all available securities."""
        endpoint = "securities.json"
        params = {
            'group_by': 'group',
            'group_by_filter': 'stock_shares',
            'limit': 100
        }
        
        response = self._make_request(endpoint, params)
        data = response.json()
        
        if 'securities' in data and len(data['securities']) > 0:
            df = pd.DataFrame(data['securities'])
            return df
        
        return pd.DataFrame()

class TradingRecommendation:
    """Class for generating trading recommendations based on technical analysis"""
    
    def __init__(self, data: pd.DataFrame):
        self.data = data
        
    def calculate_sma(self, period: int = 20) -> pd.Series:
        """Calculate Simple Moving Average"""
        return self.data['CLOSE'].rolling(window=period).mean()
        
    def calculate_ema(self, period: int = 20) -> pd.Series:
        """Calculate Exponential Moving Average"""
        return self.data['CLOSE'].ewm(span=period, adjust=False).mean()
        
    def calculate_rsi(self, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = self.data['CLOSE'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def get_recommendation(self) -> Dict[str, Any]:
        """Generate trading recommendation based on technical indicators"""
        sma_20 = self.calculate_sma(20)
        sma_50 = self.calculate_sma(50)
        rsi = self.calculate_rsi()
        
        last_close = self.data['CLOSE'].iloc[-1]
        last_sma_20 = sma_20.iloc[-1]
        last_sma_50 = sma_50.iloc[-1]
        last_rsi = rsi.iloc[-1]
        
        # Basic trading signals
        signals = []
        if last_close > last_sma_20 and last_sma_20 > last_sma_50:
            signals.append("Восходящий тренд")
        elif last_close < last_sma_20 and last_sma_20 < last_sma_50:
            signals.append("Нисходящий тренд")
            
        if last_rsi > 70:
            signals.append("Возможна перекупленность")
        elif last_rsi < 30:
            signals.append("Возможна перепроданность")
            
        recommendation = "ДЕРЖАТЬ"
        if len(signals) >= 2:
            if "Восходящий тренд" in signals and "Возможна перепроданность" in signals:
                recommendation = "ПОКУПАТЬ"
            elif "Нисходящий тренд" in signals and "Возможна перекупленность" in signals:
                recommendation = "ПРОДАВАТЬ"
                
        return {
            'recommendation': recommendation,
            'signals': signals,
            'metrics': {
                'close': last_close,
                'sma_20': last_sma_20,
                'sma_50': last_sma_50,
                'rsi': last_rsi
            }
        }

def analyze_stock(ticker: str) -> Dict[str, Any]:
    """
    Analyze a stock and generate trading recommendations
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Dictionary containing analysis results and recommendations
    """
    client = MOEXClient()
    
    try:
        # Get security info
        security_info = client.get_security_info(ticker)
        
        # Get historical data for technical analysis
        historical_data = client.get_historical_data(ticker)
        
        # Get current market data
        market_data = client.get_market_data(ticker)
        
        # Generate trading recommendation
        recommendation = TradingRecommendation(historical_data)
        analysis = recommendation.get_recommendation()
        
        return {
            'security_info': security_info,
            'current_price': market_data['LAST'].iloc[0] if not market_data.empty else None,
            'analysis': analysis
        }
        
    except Exception as e:
        logger.error(f"Error analyzing stock {ticker}: {str(e)}")
        raise 