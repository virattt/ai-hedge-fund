import datetime
import os
import pandas as pd
import requests
import time
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

from src.data.cache import get_cache
from src.data.providers import DataProvider
from src.data.models import (
    CompanyNews,
    CompanyNewsResponse,
    FinancialMetrics,
    FinancialMetricsResponse,
    Price,
    PriceResponse,
    LineItem,
    LineItemResponse,
    InsiderTrade,
    InsiderTradeResponse,
    CompanyFactsResponse,
)

# Global cache instance
_cache = get_cache()


def _make_api_request(url: str, headers: dict, method: str = "GET", json_data: dict = None, max_retries: int = 3) -> requests.Response:
    """
    Make an API request with rate limiting handling and moderate backoff.
    
    Args:
        url: The URL to request
        headers: Headers to include in the request
        method: HTTP method (GET or POST)
        json_data: JSON data for POST requests
        max_retries: Maximum number of retries (default: 3)
    
    Returns:
        requests.Response: The response object
    
    Raises:
        Exception: If the request fails with a non-429 error
    """
    for attempt in range(max_retries + 1):  # +1 for initial attempt
        if method.upper() == "POST":
            response = requests.post(url, headers=headers, json=json_data)
        else:
            response = requests.get(url, headers=headers)
        
        if response.status_code == 429 and attempt < max_retries:
            # Linear backoff: 60s, 90s, 120s, 150s...
            delay = 60 + (30 * attempt)
            print(f"Rate limited (429). Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s before retrying...")
            time.sleep(delay)
            continue
        
        # Return the response (whether success, other errors, or final 429)
        return response


def get_prices_yfinance(ticker: str, start_date: str, end_date: str) -> list[Price]:
    """Fetch price data from Yahoo Finance using yfinance."""
    if not YFINANCE_AVAILABLE:
        raise Exception("yfinance is not installed. Please install it with: pip install yfinance")
    
    try:
        # Download data from yfinance
        data = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=False)
        
        if data.empty:
            return []
        
        # Convert to our Price model format
        prices = []
        for date_idx, row in data.iterrows():
            price = Price(
                open=row['Open'],
                high=row['High'],
                low=row['Low'],
                close=row['Close'],
                volume=row['Volume'],
                time=date_idx.strftime('%Y-%m-%d')
            )
            prices.append(price)
        
        return prices
        
    except Exception as e:
        raise Exception(f"Error fetching data from Yahoo Finance for {ticker}: {str(e)}")


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None, data_provider: str = "financial_datasets") -> list[Price]:
    """Fetch price data from cache or API."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date}_{end_date}_{data_provider}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**price) for price in cached_data]

    # Route to appropriate data provider
    if data_provider == "yfinance":
        prices = get_prices_yfinance(ticker, start_date, end_date)
    else:
        # Default to Financial Datasets API
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        url = f"https://api.financialdatasets.ai/prices/?ticker={ticker}&interval=day&interval_multiplier=1&start_date={start_date}&end_date={end_date}"
        response = _make_api_request(url, headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

        # Parse response with Pydantic model
        price_response = PriceResponse(**response.json())
        prices = price_response.prices

    if not prices:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_prices(cache_key, [p.model_dump() for p in prices])
    return prices


def get_financial_metrics_yfinance(ticker: str, end_date: str = None) -> list[FinancialMetrics]:
    """Fetch financial metrics from Yahoo Finance using yfinance."""
    if not YFINANCE_AVAILABLE:
        raise Exception("yfinance is not installed. Please install it with: pip install yfinance")
    
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        
        # Defensive check: ensure info is a dict and not None
        if not info or not isinstance(info, dict):
            raise Exception(f"No valid info data returned for ticker {ticker}")
        
        # Helper function to safely get numeric values
        def safe_get_numeric(key: str, default=None):
            """Safely get numeric values from info dict, handling None cases."""
            value = info.get(key, default)
            # Ensure we don't pass None where a number is expected for calculations
            if value is None:
                return None
            try:
                # Ensure it's a valid number
                return float(value) if value is not None else None
            except (ValueError, TypeError):
                return None
        
        # Helper function to safely get string values  
        def safe_get_string(key: str, default='USD'):
            """Safely get string values from info dict."""
            value = info.get(key, default)
            if value is None:
                return default
            try:
                str_value = str(value)
                # Ensure the string is not empty and contains valid characters
                return str_value if str_value and str_value.strip() else default
            except (ValueError, TypeError):
                return default
        
        # Create a single FinancialMetrics object with available data
        metric = FinancialMetrics(
            ticker=ticker,
            report_period="ttm",
            period="ttm",
            currency=safe_get_string('currency', 'USD'),
            
            # Valuation metrics
            market_cap=safe_get_numeric('marketCap'),
            enterprise_value=safe_get_numeric('enterpriseValue'),
            price_to_earnings_ratio=safe_get_numeric('trailingPE'),
            price_to_book_ratio=safe_get_numeric('priceToBook'),
            price_to_sales_ratio=safe_get_numeric('priceToSalesTrailing12Months'),
            enterprise_value_to_ebitda_ratio=safe_get_numeric('enterpriseToEbitda'),
            enterprise_value_to_revenue_ratio=safe_get_numeric('enterpriseToRevenue'),
            
            # Set unavailable fields to None
            free_cash_flow_yield=None,
            peg_ratio=safe_get_numeric('pegRatio'),
            
            # Profitability metrics
            gross_margin=safe_get_numeric('grossMargins'),
            operating_margin=safe_get_numeric('operatingMargins'),
            net_margin=safe_get_numeric('profitMargins'),  # profit_margin is same as net_margin
            
            # Returns
            return_on_equity=safe_get_numeric('returnOnEquity'),
            return_on_assets=safe_get_numeric('returnOnAssets'),
            return_on_invested_capital=None,  # Not available in yfinance
            
            # Efficiency metrics (not available in yfinance info)
            asset_turnover=None,
            inventory_turnover=None,
            receivables_turnover=None,
            days_sales_outstanding=None,
            operating_cycle=None,
            working_capital_turnover=None,
            
            # Liquidity metrics
            current_ratio=safe_get_numeric('currentRatio'),
            quick_ratio=safe_get_numeric('quickRatio'),
            cash_ratio=None,  # Not available in yfinance
            operating_cash_flow_ratio=None,  # Not available in yfinance
            
            # Leverage metrics
            debt_to_equity=safe_get_numeric('debtToEquity'),
            debt_to_assets=None,  # Not available in yfinance
            interest_coverage=None,  # Not available in yfinance
            
            # Growth metrics
            revenue_growth=safe_get_numeric('revenueGrowth'),
            earnings_growth=safe_get_numeric('earningsGrowth'),
            book_value_growth=None,  # Not available in yfinance
            earnings_per_share_growth=None,  # Not available in yfinance
            free_cash_flow_growth=None,  # Not available in yfinance
            operating_income_growth=None,  # Not available in yfinance
            ebitda_growth=None,  # Not available in yfinance
            
            # Other metrics
            payout_ratio=safe_get_numeric('payoutRatio'),
            earnings_per_share=safe_get_numeric('trailingEps'),
            book_value_per_share=safe_get_numeric('bookValue'),
            free_cash_flow_per_share=None,  # Not available in yfinance
        )
        
        return [metric] if metric else []
        
    except Exception as e:
        raise Exception(f"Error fetching financial metrics from Yahoo Finance for {ticker}: {str(e)}")


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
    data_provider: str = "financial_datasets",
) -> list[FinancialMetrics]:
    """Fetch financial metrics from cache or API."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{period}_{end_date}_{limit}_{data_provider}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**metric) for metric in cached_data]

    # Route to appropriate data provider
    if data_provider == "yfinance":
        financial_metrics = get_financial_metrics_yfinance(ticker, end_date)
    else:
        # Default to Financial Datasets API
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}&report_period_lte={end_date}&limit={limit}&period={period}"
        response = _make_api_request(url, headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

        # Parse response with Pydantic model
        metrics_response = FinancialMetricsResponse(**response.json())
        financial_metrics = metrics_response.financial_metrics

    if not financial_metrics:
        return []

    # Cache the results as dicts using the comprehensive cache key
    _cache.set_financial_metrics(cache_key, [m.model_dump() for m in financial_metrics])
    return financial_metrics


def search_line_items_yfinance(
    ticker: str,
    line_items: list[str],
    end_date: str = None,
    period: str = "ttm",
    limit: int = 10,
) -> list[LineItem]:
    """Fetch line items from Yahoo Finance using yfinance."""
    if not YFINANCE_AVAILABLE:
        raise Exception("yfinance is not installed. Please install it with: pip install yfinance")
    
    try:
        ticker_obj = yf.Ticker(ticker)
        
        # Get financial statements based on period
        if period == "ttm" or period == "annual":
            income_stmt = ticker_obj.income_stmt
            balance_sheet = ticker_obj.balance_sheet
            cashflow = ticker_obj.cashflow
        else:
            income_stmt = ticker_obj.quarterly_income_stmt
            balance_sheet = ticker_obj.quarterly_balance_sheet
            cashflow = ticker_obj.quarterly_cashflow
        
        # Mapping of common line items to yfinance field names
        line_item_mapping = {
            # Revenue & Income
            "revenue": "Total Revenue",
            "total_revenue": "Total Revenue", 
            "net_income": "Net Income",
            "operating_income": "Operating Income",
            "ebit": "EBIT",
            "ebitda": "EBITDA",
            "gross_margin": "Gross Profit",
            "operating_margin": "Operating Income",
            
            # Per Share Metrics
            "earnings_per_share": "Diluted EPS",
            "book_value_per_share": "Stockholders Equity",
            "outstanding_shares": "Share Issued",
            
            # Balance Sheet Items
            "total_assets": "Total Assets",
            "total_liabilities": "Total Liabilities Net Minority Interest",
            "current_assets": "Current Assets",
            "current_liabilities": "Current Liabilities",
            "cash_and_equivalents": "Cash And Cash Equivalents",
            "total_debt": "Total Debt",
            "goodwill_and_intangible_assets": "Goodwill And Other Intangible Assets",
            "intangible_assets": "Other Intangible Assets",
            "shareholders_equity": "Stockholders Equity",
            
            # Cash Flow Items
            "free_cash_flow": "Free Cash Flow",
            "capital_expenditure": "Capital Expenditure",
            "depreciation_and_amortization": "Depreciation And Amortization",
            "dividends_and_other_cash_distributions": "Cash Dividends Paid",
            "issuance_or_purchase_of_equity_shares": "Common Stock Issuance",
            
            # Expense Items
            "operating_expense": "Total Expenses",
            "research_and_development": "Research And Development",
            "interest_expense": "Interest Expense",
            
            # Financial Ratios & Metrics (these come from financial metrics API, not line items)
            "debt_to_equity": "Total Debt",  # Will need calculation
            "asset_turnover": None,  # Not available in line items
            "beta": None,  # Not available in line items
            "ev_to_ebit": None,  # Not available in line items
            "return_on_invested_capital": None,  # Not available in line items
        }
        
        # Get all unique periods from the data
        all_periods = set()
        if income_stmt is not None and not income_stmt.empty:
            all_periods.update(income_stmt.columns)
        if balance_sheet is not None and not balance_sheet.empty:
            all_periods.update(balance_sheet.columns)
        if cashflow is not None and not cashflow.empty:
            all_periods.update(cashflow.columns)
        
        # Sort periods (most recent first)
        sorted_periods = sorted(all_periods, reverse=True)[:limit]
        
        results = []
        
        for period_date in sorted_periods:
            line_item_data = {
                "ticker": ticker,
                "report_period": str(period_date.date()) if hasattr(period_date, 'date') else str(period_date),
                "period": period,
                "currency": 'USD',  # Default currency
            }
            
            # Collect all requested line items for this period
            for item in line_items:
                yfinance_name = line_item_mapping.get(item, item)
                value = None
                
                # Skip if yfinance_name is None (not available in yfinance)
                if yfinance_name is None:
                    continue
                
                # Search in income statement first
                if income_stmt is not None and yfinance_name in income_stmt.index and period_date in income_stmt.columns:
                    value = income_stmt.loc[yfinance_name, period_date]
                
                # Then balance sheet
                elif balance_sheet is not None and yfinance_name in balance_sheet.index and period_date in balance_sheet.columns:
                    value = balance_sheet.loc[yfinance_name, period_date]
                
                # Then cash flow
                elif cashflow is not None and yfinance_name in cashflow.index and period_date in cashflow.columns:
                    value = cashflow.loc[yfinance_name, period_date]
                
                # Add to line_item_data if value is valid
                if value is not None and not pd.isna(value):
                    line_item_data[item] = float(value)
            
            # Only create LineItem if we have at least one valid value
            if len(line_item_data) > 4:  # More than just the base fields
                line_item = LineItem(**line_item_data)
                results.append(line_item)
        
        return results
        
    except Exception as e:
        raise Exception(f"Error fetching line items from Yahoo Finance for {ticker}: {str(e)}")


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
    data_provider: str = "financial_datasets",
) -> list[LineItem]:
    """Fetch line items from cache or API."""
    # Route to appropriate data provider
    if data_provider == "yfinance":
        return search_line_items_yfinance(ticker, line_items, end_date, period, limit)
    else:
        # Default to Financial Datasets API
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        url = "https://api.financialdatasets.ai/financials/search/line-items"

        body = {
            "tickers": [ticker],
            "line_items": line_items,
            "end_date": end_date,
            "period": period,
            "limit": limit,
        }
        response = _make_api_request(url, headers, method="POST", json_data=body)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")
        data = response.json()
        response_model = LineItemResponse(**data)
        search_results = response_model.search_results
        if not search_results:
            return []

        # Cache the results
        return search_results[:limit]


def get_insider_trades_yfinance(
    ticker: str,
    end_date: str = None,
    start_date: str = None,
    limit: int = 1000,
) -> list[InsiderTrade]:
    """Fetch insider trades from Yahoo Finance using yfinance."""
    if not YFINANCE_AVAILABLE:
        raise Exception("yfinance is not installed. Please install it with: pip install yfinance")
    
    try:
        ticker_obj = yf.Ticker(ticker)
        insider_data = ticker_obj.insider_transactions
        
        if insider_data is None or insider_data.empty:
            return []
        
        trades = []
        for _, row in insider_data.iterrows():
            # Basic data mapping - yfinance has limited insider trade details
            trade = InsiderTrade(
                ticker=ticker,
                issuer=None,  # Not available in yfinance
                name=str(row.get('Insider', '')),
                title=str(row.get('Position', '')),
                is_board_director=None,  # Not available in yfinance
                transaction_date=str(row.get('Start Date', '')),
                transaction_shares=int(row.get('Shares', 0)) if pd.notnull(row.get('Shares')) else 0,
                transaction_price_per_share=None,  # Not available in yfinance
                transaction_value=float(row.get('Value', 0)) if pd.notnull(row.get('Value')) else 0.0,
                shares_owned_before_transaction=None,  # Not available in yfinance
                shares_owned_after_transaction=None,  # Not available in yfinance
                security_title=None,  # Not available in yfinance
                filing_date=str(row.get('Start Date', '')),  # Use same date for filing
            )
            trades.append(trade)
        
        return trades[:limit]
        
    except Exception as e:
        # Return empty list instead of raising exception for non-critical data
        print(f"Warning: Could not fetch insider trades from Yahoo Finance for {ticker}: {str(e)}")
        return []


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
    data_provider: str = "financial_datasets",
) -> list[InsiderTrade]:
    """Fetch insider trades from cache or API."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}_{data_provider}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_insider_trades(cache_key):
        return [InsiderTrade(**trade) for trade in cached_data]

    # Route to appropriate data provider
    if data_provider == "yfinance":
        all_trades = get_insider_trades_yfinance(ticker, end_date, start_date, limit)
    else:
        # Default to Financial Datasets API
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        all_trades = []
        current_end_date = end_date

        while True:
            url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}"
            if start_date:
                url += f"&filing_date_gte={start_date}"
            url += f"&limit={limit}"

            response = _make_api_request(url, headers)
            if response.status_code != 200:
                raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

            data = response.json()
            response_model = InsiderTradeResponse(**data)
            insider_trades = response_model.insider_trades

            if not insider_trades:
                break

            all_trades.extend(insider_trades)

            # Only continue pagination if we have a start_date and got a full page
            if not start_date or len(insider_trades) < limit:
                break

            # Update end_date to the oldest filing date from current batch for next iteration
            current_end_date = min(trade.filing_date for trade in insider_trades).split("T")[0]

            # If we've reached or passed the start_date, we can stop
            if current_end_date <= start_date:
                break

    if not all_trades:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_insider_trades(cache_key, [trade.model_dump() for trade in all_trades])
    return all_trades


def get_company_news_yfinance(
    ticker: str,
    end_date: str = None,
    start_date: str = None,
    limit: int = 1000,
) -> list[CompanyNews]:
    """Fetch company news from Yahoo Finance using yfinance."""
    if not YFINANCE_AVAILABLE:
        raise Exception("yfinance is not installed. Please install it with: pip install yfinance")
    
    try:
        ticker_obj = yf.Ticker(ticker)
        news_data = ticker_obj.news
        
        if not news_data:
            return []
        
        news_items = []
        for item in news_data[:limit]:
            content = item.get('content', {})
            if content:
                news = CompanyNews(
                    ticker=ticker,
                    title=content.get('title', ''),
                    author='',  # yfinance doesn't provide author info
                    source=content.get('publisher', {}).get('name', '') if isinstance(content.get('publisher'), dict) else str(content.get('publisher', '')),
                    url=content.get('clickThroughUrl', {}).get('url', '') if isinstance(content.get('clickThroughUrl'), dict) else str(content.get('clickThroughUrl', '')),
                    date=content.get('publishedAt', ''),
                    sentiment='neutral'  # yfinance doesn't provide sentiment
                )
                news_items.append(news)
        
        return news_items
        
    except Exception as e:
        # Return empty list instead of raising exception for non-critical data
        print(f"Warning: Could not fetch company news from Yahoo Finance for {ticker}: {str(e)}")
        return []


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
    data_provider: str = "financial_datasets",
) -> list[CompanyNews]:
    """Fetch company news from cache or API."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}_{data_provider}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_company_news(cache_key):
        return [CompanyNews(**news) for news in cached_data]

    # Route to appropriate data provider
    if data_provider == "yfinance":
        all_news = get_company_news_yfinance(ticker, end_date, start_date, limit)
    else:
        # Default to Financial Datasets API
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        all_news = []
        current_end_date = end_date

        while True:
            url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end_date}"
            if start_date:
                url += f"&start_date={start_date}"
            url += f"&limit={limit}"

            response = _make_api_request(url, headers)
            if response.status_code != 200:
                raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

            data = response.json()
            response_model = CompanyNewsResponse(**data)
            company_news = response_model.news

            if not company_news:
                break

            all_news.extend(company_news)

            # Only continue pagination if we have a start_date and got a full page
            if not start_date or len(company_news) < limit:
                break

            # Update end_date to the oldest date from current batch for next iteration
            current_end_date = min(news.date for news in company_news).split("T")[0]

            # If we've reached or passed the start_date, we can stop
            if current_end_date <= start_date:
                break

        if not all_news:
            return []

    # Cache the results using the comprehensive cache key
    _cache.set_company_news(cache_key, [news.model_dump() for news in all_news])
    return all_news


def get_market_cap_yfinance(ticker: str, end_date: str = None) -> float | None:
    """Fetch market cap from Yahoo Finance using yfinance."""
    if not YFINANCE_AVAILABLE:
        raise Exception("yfinance is not installed. Please install it with: pip install yfinance")
    
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        return info.get('marketCap')
        
    except Exception as e:
        print(f"Warning: Could not fetch market cap from Yahoo Finance for {ticker}: {str(e)}")
        return None


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
    data_provider: str = "financial_datasets",
) -> float | None:
    """Fetch market cap from the API."""
    # Route to appropriate data provider
    if data_provider == "yfinance":
        return get_market_cap_yfinance(ticker, end_date)
    else:
        # Default to Financial Datasets API
        # Check if end_date is today
        if end_date == datetime.datetime.now().strftime("%Y-%m-%d"):
            # Get the market cap from company facts API
            headers = {}
            financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
            if financial_api_key:
                headers["X-API-KEY"] = financial_api_key

            url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
            response = _make_api_request(url, headers)
            if response.status_code != 200:
                print(f"Error fetching company facts: {ticker} - {response.status_code}")
                return None

            data = response.json()
            response_model = CompanyFactsResponse(**data)
            return response_model.company_facts.market_cap

        financial_metrics = get_financial_metrics(ticker, end_date, api_key=api_key, data_provider=data_provider)
        if not financial_metrics:
            return None

        market_cap = financial_metrics[0].market_cap

        if not market_cap:
            return None

        return market_cap


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """Convert prices to a DataFrame."""
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


# Update the get_price_data function to use the new functions
def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)
