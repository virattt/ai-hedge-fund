import os
import requests
import base64
from datetime import datetime

from data.cache import get_cache
from data.models import TradingChart, TradingChartResponse

# Global cache instance
_cache = get_cache()


def get_trading_chart(
    ticker: str,
    end_date: str = None,
    timeframe: str = "1D",
    indicators: list[str] = None,
) -> TradingChart:
    """Fetch trading chart from chart-img.com API or cache.
    
    Args:
        ticker: The stock ticker symbol
        end_date: The end date for the chart (defaults to current date)
        timeframe: Chart timeframe (e.g., "1D", "4H", "1W")
        indicators: List of technical indicators to include
        
    Returns:
        TradingChart object with chart data and image
    """
    # Check cache first
    if cached_data := _cache.get_trading_chart(ticker, timeframe):
        return TradingChart(**cached_data)

    # If not in cache, fetch from API
    api_key = os.environ.get("CHART_IMG_API_KEY")
    if not api_key:
        raise ValueError("CHART_IMG_API_KEY environment variable not set")
    
    # Set default indicators if none provided
    if indicators is None:
        indicators = ["ema(20)", "ema(50)", "volume"]
    
    # Format current date if end_date not provided
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    # Prepare request to chart-img.com API
    url = "https://api.chart-img.com/v1/tradingview/advanced-chart"
    
    # Configure chart parameters
    params = {
        "symbol": f"NASDAQ:{ticker}",
        "interval": timeframe,
        "studies": indicators,
        "key": api_key,
        "height": 600,
        "width": 800,
        "theme": "light",
    }
    
    # Make the API request
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        raise Exception(f"Error fetching chart: {response.status_code} - {response.text}")
    
    # Get the image data and encode as base64
    image_data = base64.b64encode(response.content).decode('utf-8')
    
    # Create chart URL (for reference)
    chart_url = response.url
    
    # Create the trading chart object
    trading_chart = TradingChart(
        ticker=ticker,
        chart_url=chart_url,
        image_data=image_data,
        timestamp=datetime.now().isoformat(),
        timeframe=timeframe,
        indicators=indicators
    )
    
    # Cache the results
    _cache.set_trading_chart(ticker, timeframe, trading_chart.model_dump())
    
    return trading_chart