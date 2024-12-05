import os
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import requests

# Load environment variables
load_dotenv()

def get_prices(ticker, start_date, end_date):
    """Fetch price data from the API."""
    api_key = os.getenv("FINANCIAL_DATASETS_API_KEY")
    if not api_key:
        raise ValueError("FINANCIAL_DATASETS_API_KEY not found in environment variables")
        
    headers = {"X-API-KEY": api_key}
    url = (
        f"https://api.financialdatasets.ai/prices/"
        f"?ticker={ticker}"
        f"&interval=day"
        f"&interval_multiplier=1"
        f"&start_date={start_date}"
        f"&end_date={end_date}"
    )
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        prices = data.get("prices")
        if not prices:
            raise ValueError("No price data returned")
            
        return prices
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {str(e)}")
        # Return some sample data for testing
        return generate_sample_data(ticker, start_date, end_date)

def generate_sample_data(ticker, start_date, end_date):
    """Generate sample price data for testing."""
    dates = pd.date_range(start=start_date, end=end_date, freq='B')
    import numpy as np
    
    # Generate random walk prices
    np.random.seed(42)  # For reproducibility
    price = 100  # Starting price
    prices = []
    for date in dates:
        change = np.random.normal(0, 2)  # Random daily change
        price *= (1 + change/100)  # Apply percentage change
        volume = np.random.randint(1000000, 5000000)  # Random volume
        
        prices.append({
            "time": date.strftime("%Y-%m-%d"),
            "open": price * (1 + np.random.normal(0, 0.001)),
            "high": price * (1 + abs(np.random.normal(0, 0.002))),
            "low": price * (1 - abs(np.random.normal(0, 0.002))),
            "close": price,
            "volume": volume
        })
    
    return prices

def prices_to_df(prices):
    """Convert prices to a DataFrame."""
    df = pd.DataFrame(prices)
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df

# Update the get_price_data function to use the new functions
def get_price_data(ticker, start_date, end_date):
    prices = get_prices(ticker, start_date, end_date)
    return prices_to_df(prices)

def calculate_confidence_level(signals):
    """Calculate confidence level based on the difference between SMAs."""
    sma_diff_prev = abs(signals['sma_5_prev'] - signals['sma_20_prev'])
    sma_diff_curr = abs(signals['sma_5_curr'] - signals['sma_20_curr'])
    diff_change = sma_diff_curr - sma_diff_prev
    # Normalize confidence between 0 and 1
    confidence = min(max(diff_change / signals['current_price'], 0), 1)
    return confidence

def calculate_macd(prices_df):
    ema_12 = prices_df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = prices_df['close'].ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    return macd_line, signal_line

def calculate_rsi(prices_df, period=14):
    delta = prices_df['close'].diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_bollinger_bands(prices_df, window=20):
    sma = prices_df['close'].rolling(window).mean()
    std_dev = prices_df['close'].rolling(window).std()
    upper_band = sma + (std_dev * 2)
    lower_band = sma - (std_dev * 2)
    return upper_band, lower_band


def calculate_obv(prices_df):
    obv = [0]
    for i in range(1, len(prices_df)):
        if prices_df['close'].iloc[i] > prices_df['close'].iloc[i - 1]:
            obv.append(obv[-1] + prices_df['volume'].iloc[i])
        elif prices_df['close'].iloc[i] < prices_df['close'].iloc[i - 1]:
            obv.append(obv[-1] - prices_df['volume'].iloc[i])
        else:
            obv.append(obv[-1])
    prices_df['OBV'] = obv
    return prices_df['OBV']

def get_technical_indicators(ticker, start_date, end_date):
    """Fetch technical indicators from the API."""
    api_key = os.getenv("FINANCIAL_DATASETS_API_KEY")
    if not api_key:
        raise ValueError("FINANCIAL_DATASETS_API_KEY not found in environment variables")
        
    headers = {"X-API-KEY": api_key}
    url = (
        f"https://api.financialdatasets.ai/technicals/"
        f"?ticker={ticker}"
        f"&start_date={start_date}"
        f"&end_date={end_date}"
    )
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("technicals", {})
    except requests.exceptions.RequestException as e:
        print(f"Error fetching technical indicators: {str(e)}")
        return generate_sample_technicals()

def generate_sample_technicals():
    """Generate sample technical indicators for testing."""
    return {
        "ADX": 25.5,        # Average Directional Index
        "ATR": 2.3,         # Average True Range
        "CMF": 0.15,        # Chaikin Money Flow
        "MFI": 55.0,        # Money Flow Index
        "STOCH": 65.0,      # Stochastic Oscillator
        "STOCHRSI": 45.0,   # Stochastic RSI
        "ULTOSC": 50.0,     # Ultimate Oscillator
        "WILLR": -35.0      # Williams %R
    }

def calculate_adx(prices_df, period=14):
    """Calculate Average Directional Index"""
    high = prices_df['high']
    low = prices_df['low']
    close = prices_df['close']
    
    # Calculate True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    # Calculate Plus Directional Movement (+DM)
    plus_dm = high.diff()
    plus_dm = plus_dm.where(plus_dm > 0, 0)
    plus_dm = plus_dm.where(plus_dm > -low.diff(), 0)
    
    # Calculate Minus Directional Movement (-DM)
    minus_dm = -low.diff()
    minus_dm = minus_dm.where(minus_dm > 0, 0)
    minus_dm = minus_dm.where(minus_dm > high.diff(), 0)
    
    # Calculate Smoothed +DM and -DM
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
    
    # Calculate ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()
    
    return adx

def calculate_mfi(prices_df, period=14):
    """Calculate Money Flow Index"""
    typical_price = (prices_df['high'] + prices_df['low'] + prices_df['close']) / 3
    money_flow = typical_price * prices_df['volume']
    
    # Get positive and negative money flow
    positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0).rolling(window=period).sum()
    negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0).rolling(window=period).sum()
    
    # Calculate money flow ratio and index
    money_ratio = positive_flow / negative_flow
    mfi = 100 - (100 / (1 + money_ratio))
    
    return mfi

def calculate_stoch(prices_df, k_period=14, d_period=3):
    """Calculate Stochastic Oscillator"""
    low_min = prices_df['low'].rolling(window=k_period).min()
    high_max = prices_df['high'].rolling(window=k_period).max()
    
    # Calculate %K
    k = 100 * (prices_df['close'] - low_min) / (high_max - low_min)
    
    # Calculate %D (3-period moving average of %K)
    d = k.rolling(window=d_period).mean()
    
    return k, d

def calculate_willr(prices_df, period=14):
    """Calculate Williams %R"""
    highest_high = prices_df['high'].rolling(window=period).max()
    lowest_low = prices_df['low'].rolling(window=period).min()
    
    willr = -100 * (highest_high - prices_df['close']) / (highest_high - lowest_low)
    return willr

def analyze_technicals(prices_df):
    """Analyze all technical indicators and return signals"""
    # Calculate existing indicators
    macd_line, signal_line = calculate_macd(prices_df)
    rsi = calculate_rsi(prices_df)
    upper_band, lower_band = calculate_bollinger_bands(prices_df)
    obv = calculate_obv(prices_df)
    
    # Calculate new indicators
    adx = calculate_adx(prices_df)
    mfi = calculate_mfi(prices_df)
    stoch_k, stoch_d = calculate_stoch(prices_df)
    willr = calculate_willr(prices_df)
    
    # Generate signals
    signals = {
        "MACD": {
            "value": macd_line.iloc[-1],
            "signal": "bullish" if macd_line.iloc[-1] > signal_line.iloc[-1] else "bearish",
            "strength": abs(macd_line.iloc[-1] - signal_line.iloc[-1])
        },
        "RSI": {
            "value": rsi.iloc[-1],
            "signal": "bullish" if rsi.iloc[-1] < 30 else "bearish" if rsi.iloc[-1] > 70 else "neutral",
            "strength": abs(50 - rsi.iloc[-1]) / 50
        },
        "ADX": {
            "value": adx.iloc[-1],
            "signal": "strong_trend" if adx.iloc[-1] > 25 else "weak_trend",
            "strength": adx.iloc[-1] / 100
        },
        "MFI": {
            "value": mfi.iloc[-1],
            "signal": "bullish" if mfi.iloc[-1] < 20 else "bearish" if mfi.iloc[-1] > 80 else "neutral",
            "strength": abs(50 - mfi.iloc[-1]) / 50
        },
        "Stochastic": {
            "value": stoch_k.iloc[-1],
            "signal": "bullish" if stoch_k.iloc[-1] < 20 else "bearish" if stoch_k.iloc[-1] > 80 else "neutral",
            "strength": abs(50 - stoch_k.iloc[-1]) / 50
        },
        "Williams%R": {
            "value": willr.iloc[-1],
            "signal": "bullish" if willr.iloc[-1] < -80 else "bearish" if willr.iloc[-1] > -20 else "neutral",
            "strength": abs(-50 - willr.iloc[-1]) / 50
        }
    }
    
    return signals