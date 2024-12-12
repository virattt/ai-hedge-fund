import os
import time
import requests
import pandas as pd


class CMCClient:
    def __init__(self):
        self.api_key = os.environ.get("COINMARKETCAP_API_KEY")
        if not self.api_key:
            raise ValueError("COINMARKETCAP_API_KEY environment variable is not set")
        self.base_url = "https://pro-api.coinmarketcap.com/v1"
        self.session = requests.Session()
        self.session.headers.update({
            'X-CMC_PRO_API_KEY': self.api_key,
            'Accept': 'application/json'
        })

    def _handle_rate_limit(self, response: requests.Response) -> bool:
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            time.sleep(retry_after)
            return True
        return False

    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.base_url}/{endpoint}"
        while True:
            response = self.session.get(url, params=params)
            if not self._handle_rate_limit(response):
                break

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error fetching data: {response.status_code} - {response.text}")


def get_prices(symbol: str, start_date: str, end_date: str) -> dict:
    client = CMCClient()
    params = {
        'symbol': symbol,
        'time_start': start_date,
        'time_end': end_date,
        'convert': 'USD'
    }

    return client._make_request(
        'cryptocurrency/quotes/historical',
        params=params
    )


def prices_to_df(prices: dict) -> pd.DataFrame:
    quotes = prices['data'][list(prices['data'].keys())[0]]['quotes']
    df = pd.DataFrame(quotes)
    df['Date'] = pd.to_datetime(df['timestamp'])
    df.set_index('Date', inplace=True)

    for quote in df['quote'].values:
        usd_data = quote['USD']
        for key in ['open', 'high', 'low', 'close', 'volume']:
            df.loc[df.index[df['quote'] == quote], key] = usd_data.get(key, 0)

    df = df.drop('quote', axis=1)
    numeric_cols = ['open', 'close', 'high', 'low', 'volume']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df.sort_index(inplace=True)
    return df


def get_price_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    prices = get_prices(symbol, start_date, end_date)
    return prices_to_df(prices)


def get_market_data(symbol: str) -> dict:
    client = CMCClient()
    params = {
        'symbol': symbol,
        'convert': 'USD'
    }

    return client._make_request(
        'cryptocurrency/quotes/latest',
        params=params
    )


def get_financial_metrics(symbol: str) -> dict:
    client = CMCClient()
    params = {
        'symbol': symbol,
        'convert': 'USD'
    }

    return client._make_request(
        'cryptocurrency/info',
        params=params
    )


def calculate_confidence_level(signals):
    sma_diff_prev = abs(signals["sma_5_prev"] - signals["sma_20_prev"])
    sma_diff_curr = abs(signals["sma_5_curr"] - signals["sma_20_curr"])
    diff_change = sma_diff_curr - sma_diff_prev
    confidence = min(max(diff_change / signals["current_price"], 0), 1)
    return confidence


def calculate_macd(prices_df):
    ema_12 = prices_df["close"].ewm(span=12, adjust=False).mean()
    ema_26 = prices_df["close"].ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    return macd_line, signal_line


def calculate_rsi(prices_df, period=14):
    delta = prices_df["close"].diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_bollinger_bands(prices_df, window=20):
    sma = prices_df["close"].rolling(window).mean()
    std_dev = prices_df["close"].rolling(window).std()
    upper_band = sma + (std_dev * 2)
    lower_band = sma - (std_dev * 2)
    return upper_band, lower_band


def calculate_obv(prices_df):
    obv = [0]
    for i in range(1, len(prices_df)):
        if prices_df["close"].iloc[i] > prices_df["close"].iloc[i - 1]:
            obv.append(obv[-1] + prices_df["volume"].iloc[i])
        elif prices_df["close"].iloc[i] < prices_df["close"].iloc[i - 1]:
            obv.append(obv[-1] - prices_df["volume"].iloc[i])
        else:
            obv.append(obv[-1])
    prices_df["OBV"] = obv
    return prices_df["OBV"]
