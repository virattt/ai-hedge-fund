import os
import requests
import base64
from datetime import datetime
from pathlib import Path

from data.cache import get_cache
from data.models import TradingChart, TradingChartResponse

# Global cache instance
_cache = get_cache()

# Define charts directory
CHARTS_DIR = Path("output/charts")

def get_trading_chart(
    ticker: str,
    end_date: str = None,
    timeframe: str = "1D",
    indicators: list[str] = None,
) -> TradingChart:
    """Fetch trading chart from chart-img.com API or cache."""
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
    
    # Ensure charts directory exists and is empty
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    for file in CHARTS_DIR.glob("*"):
        file.unlink()
    
    # Prepare request to chart-img.com API
    url = "https://api.chart-img.com/v2/tradingview/layout-chart/TT6qAg8k"
    
    # Configure headers and payload
    headers = {
        "x-api-key": api_key,
        "content-type": "application/json"
    }
    
    payload = {
        "symbol": f"NASDAQ:{ticker}",
        "interval": timeframe,
        "studies": indicators,
        "height": 600,
        "width": 800,
        "theme": "light"
    }
    
    # Make the API request
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        raise Exception(f"Error fetching chart: {response.status_code} - {response.text}")
    
    # Save the image file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = CHARTS_DIR / f"{ticker}_{timeframe}_{timestamp}.png"
    image_path.write_bytes(response.content)
    
    # Get the image data and encode as base64
    # image_data = base64.b64encode(response.content).decode('utf-8')
    
    # Create the trading chart object
    trading_chart = TradingChart(
        ticker=ticker,
        timestamp=datetime.now().isoformat(),
        timeframe=timeframe,
        indicators=indicators,
        image_path=str(image_path)
    )
    
    # Cache the results
    _cache.set_trading_chart(ticker, timeframe, trading_chart.model_dump())
    
    return trading_chart
