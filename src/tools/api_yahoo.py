"""
Yahoo Finance API Wrapper

Provides free alternative to Financial Datasets API using yfinance.
Implements the same interfaces as api.py for drop-in replacement.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import warnings

from src.data.cache import get_cache
from src.data.models import (
    Price,
    PriceResponse,
    FinancialMetrics,
    FinancialMetricsResponse,
    LineItem,
    LineItemResponse,
    InsiderTrade,
    InsiderTradeResponse,
    CompanyNews,
    CompanyNewsResponse,
)

# Suppress yfinance warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# Global cache instance
_cache = get_cache()


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    """
    Fetch price data from Yahoo Finance.

    Args:
        ticker: Stock ticker symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        api_key: Not used (kept for compatibility)

    Returns:
        List of Price objects with OHLCV data
    """
    # Create cache key
    cache_key = f"{ticker}_{start_date}_{end_date}"

    # Check cache first
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**price) for price in cached_data]

    try:
        # Fetch data from Yahoo Finance
        stock = yf.Ticker(ticker)
        df = stock.history(start=start_date, end=end_date)

        if df.empty:
            return []

        # Convert to Price objects
        prices = []
        for date, row in df.iterrows():
            prices.append(Price(
                open=float(row['Open']),
                close=float(row['Close']),
                high=float(row['High']),
                low=float(row['Low']),
                volume=int(row['Volume']),
                time=date.strftime('%Y-%m-%dT%H:%M:%S')
            ))

        # Cache the results
        _cache.set_prices(cache_key, [p.model_dump() for p in prices])
        return prices

    except Exception as e:
        print(f"Error fetching price data for {ticker}: {str(e)}")
        return []


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
    """
    Fetch financial metrics from Yahoo Finance.

    Args:
        ticker: Stock ticker symbol
        end_date: End date (YYYY-MM-DD)
        period: Period type (ttm, quarterly, annual) - ttm uses info, others use financials
        limit: Number of periods to return
        api_key: Not used (kept for compatibility)

    Returns:
        List of FinancialMetrics objects
    """
    # Create cache key
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"

    # Check cache first
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**metric) for metric in cached_data]

    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Get financial statements for historical data
        if period == "quarterly":
            financials = stock.quarterly_financials
            balance_sheet = stock.quarterly_balance_sheet
            cash_flow = stock.quarterly_cashflow
        else:
            financials = stock.financials
            balance_sheet = stock.balance_sheet
            cash_flow = stock.cashflow

        metrics_list = []

        # For TTM, use the info dict which has current metrics
        if period == "ttm":
            metrics = _build_financial_metrics_from_info(ticker, info, end_date, period)
            if metrics:
                metrics_list.append(metrics)
        else:
            # For historical periods, build metrics from financial statements
            dates = financials.columns[:limit] if not financials.empty else []

            for date in dates:
                metrics = _build_financial_metrics_from_statements(
                    ticker, date, period, financials, balance_sheet, cash_flow, info
                )
                if metrics:
                    metrics_list.append(metrics)

        # Cache the results
        if metrics_list:
            _cache.set_financial_metrics(cache_key, [m.model_dump() for m in metrics_list])

        return metrics_list

    except Exception as e:
        print(f"Error fetching financial metrics for {ticker}: {str(e)}")
        return []


def _build_financial_metrics_from_info(
    ticker: str,
    info: dict,
    end_date: str,
    period: str
) -> Optional[FinancialMetrics]:
    """Build FinancialMetrics from yfinance info dict (for TTM data)."""
    try:
        return FinancialMetrics(
            ticker=ticker,
            report_period=end_date,
            period=period,
            currency=info.get('currency', 'USD'),
            market_cap=info.get('marketCap'),
            enterprise_value=info.get('enterpriseValue'),
            price_to_earnings_ratio=info.get('trailingPE'),
            price_to_book_ratio=info.get('priceToBook'),
            price_to_sales_ratio=info.get('priceToSalesTrailing12Months'),
            enterprise_value_to_ebitda_ratio=info.get('enterpriseToEbitda'),
            enterprise_value_to_revenue_ratio=info.get('enterpriseToRevenue'),
            free_cash_flow_yield=None,  # Calculate if needed
            peg_ratio=info.get('pegRatio'),
            gross_margin=info.get('grossMargins'),
            operating_margin=info.get('operatingMargins'),
            net_margin=info.get('profitMargins'),
            return_on_equity=info.get('returnOnEquity'),
            return_on_assets=info.get('returnOnAssets'),
            return_on_invested_capital=None,  # Not directly available
            asset_turnover=None,  # Calculate if needed
            inventory_turnover=None,  # Not directly available
            receivables_turnover=None,  # Not directly available
            days_sales_outstanding=None,  # Not directly available
            operating_cycle=None,  # Not directly available
            working_capital_turnover=None,  # Not directly available
            current_ratio=info.get('currentRatio'),
            quick_ratio=info.get('quickRatio'),
            cash_ratio=None,  # Calculate if needed
            operating_cash_flow_ratio=None,  # Calculate if needed
            debt_to_equity=info.get('debtToEquity'),
            debt_to_assets=None,  # Calculate if needed
            interest_coverage=None,  # Not directly available
            revenue_growth=info.get('revenueGrowth'),
            earnings_growth=info.get('earningsGrowth'),
            book_value_growth=None,  # Not directly available
            earnings_per_share_growth=info.get('earningsQuarterlyGrowth'),
            free_cash_flow_growth=None,  # Not directly available
            operating_income_growth=None,  # Not directly available
            ebitda_growth=None,  # Not directly available
            payout_ratio=info.get('payoutRatio'),
            earnings_per_share=info.get('trailingEps'),
            book_value_per_share=info.get('bookValue'),
            free_cash_flow_per_share=None,  # Calculate if needed
        )
    except Exception as e:
        print(f"Error building metrics from info: {str(e)}")
        return None


def _build_financial_metrics_from_statements(
    ticker: str,
    date: pd.Timestamp,
    period: str,
    financials: pd.DataFrame,
    balance_sheet: pd.DataFrame,
    cash_flow: pd.DataFrame,
    info: dict
) -> Optional[FinancialMetrics]:
    """Build FinancialMetrics from financial statements for a specific date."""
    try:
        # Helper function to safely get values
        def get_value(df: pd.DataFrame, key: str, date: pd.Timestamp) -> Optional[float]:
            try:
                if key in df.index and date in df.columns:
                    val = df.loc[key, date]
                    return float(val) if pd.notna(val) else None
            except:
                pass
            return None

        # Get key values from statements
        revenue = get_value(financials, 'Total Revenue', date)
        net_income = get_value(financials, 'Net Income', date)
        total_assets = get_value(balance_sheet, 'Total Assets', date)
        total_liabilities = get_value(balance_sheet, 'Total Liabilities Net Minority Interest', date)
        shareholders_equity = get_value(balance_sheet, 'Stockholders Equity', date)
        current_assets = get_value(balance_sheet, 'Current Assets', date)
        current_liabilities = get_value(balance_sheet, 'Current Liabilities', date)
        total_debt = get_value(balance_sheet, 'Total Debt', date)
        free_cash_flow = get_value(cash_flow, 'Free Cash Flow', date)

        # Calculate ratios
        current_ratio = None
        if current_assets and current_liabilities and current_liabilities != 0:
            current_ratio = current_assets / current_liabilities

        debt_to_equity = None
        if total_debt and shareholders_equity and shareholders_equity != 0:
            debt_to_equity = total_debt / shareholders_equity

        return FinancialMetrics(
            ticker=ticker,
            report_period=date.strftime('%Y-%m-%d'),
            period=period,
            currency=info.get('currency', 'USD'),
            market_cap=None,  # Historical market cap not easily available
            enterprise_value=None,
            price_to_earnings_ratio=None,
            price_to_book_ratio=None,
            price_to_sales_ratio=None,
            enterprise_value_to_ebitda_ratio=None,
            enterprise_value_to_revenue_ratio=None,
            free_cash_flow_yield=None,
            peg_ratio=None,
            gross_margin=None,  # Would need to calculate
            operating_margin=None,  # Would need to calculate
            net_margin=None,  # Would need to calculate
            return_on_equity=None,  # Would need to calculate
            return_on_assets=None,  # Would need to calculate
            return_on_invested_capital=None,
            asset_turnover=None,
            inventory_turnover=None,
            receivables_turnover=None,
            days_sales_outstanding=None,
            operating_cycle=None,
            working_capital_turnover=None,
            current_ratio=current_ratio,
            quick_ratio=None,
            cash_ratio=None,
            operating_cash_flow_ratio=None,
            debt_to_equity=debt_to_equity,
            debt_to_assets=None,
            interest_coverage=None,
            revenue_growth=None,
            earnings_growth=None,
            book_value_growth=None,
            earnings_per_share_growth=None,
            free_cash_flow_growth=None,
            operating_income_growth=None,
            ebitda_growth=None,
            payout_ratio=None,
            earnings_per_share=None,
            book_value_per_share=None,
            free_cash_flow_per_share=None,
        )
    except Exception as e:
        print(f"Error building metrics from statements: {str(e)}")
        return None


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    """
    Search for specific line items in financial statements.

    Args:
        ticker: Stock ticker symbol
        line_items: List of line item names to search for
        end_date: End date (YYYY-MM-DD)
        period: Period type (ttm, quarterly, annual)
        limit: Number of periods to return
        api_key: Not used (kept for compatibility)

    Returns:
        List of LineItem objects with requested data
    """
    try:
        stock = yf.Ticker(ticker)

        # Get appropriate financial statements based on period
        if period == "quarterly":
            income_stmt = stock.quarterly_financials
            balance_sheet = stock.quarterly_balance_sheet
            cash_flow = stock.quarterly_cashflow
        else:
            income_stmt = stock.financials
            balance_sheet = stock.balance_sheet
            cash_flow = stock.cashflow

        # Mapping of common line item names to yfinance keys
        line_item_mapping = {
            "revenue": ("Total Revenue", income_stmt),
            "net_income": ("Net Income", income_stmt),
            "operating_income": ("Operating Income", income_stmt),
            "gross_profit": ("Gross Profit", income_stmt),
            "ebitda": ("EBITDA", income_stmt),
            "earnings_per_share": ("Basic EPS", income_stmt),
            "free_cash_flow": ("Free Cash Flow", cash_flow),
            "operating_cash_flow": ("Operating Cash Flow", cash_flow),
            "capital_expenditure": ("Capital Expenditure", cash_flow),
            "depreciation_and_amortization": ("Depreciation And Amortization", cash_flow),
            "total_assets": ("Total Assets", balance_sheet),
            "total_liabilities": ("Total Liabilities Net Minority Interest", balance_sheet),
            "shareholders_equity": ("Stockholders Equity", balance_sheet),
            "total_debt": ("Total Debt", balance_sheet),
            "cash_and_equivalents": ("Cash And Cash Equivalents", balance_sheet),
            "current_assets": ("Current Assets", balance_sheet),
            "current_liabilities": ("Current Liabilities", balance_sheet),
            "outstanding_shares": ("Ordinary Shares Number", balance_sheet),
            "dividends_and_other_cash_distributions": ("Cash Dividends Paid", cash_flow),
            "issuance_or_purchase_of_equity_shares": ("Repurchase Of Capital Stock", cash_flow),
        }

        results = []

        # Get the dates we want to return (limit number of periods)
        all_dates = set()
        for df in [income_stmt, balance_sheet, cash_flow]:
            if not df.empty:
                all_dates.update(df.columns[:limit])

        sorted_dates = sorted(all_dates, reverse=True)[:limit]

        for date in sorted_dates:
            line_item_dict = {
                "ticker": ticker,
                "report_period": date.strftime('%Y-%m-%d'),
                "period": period,
                "currency": "USD",  # Default, could be extracted from info
            }

            # Add requested line items
            for item_name in line_items:
                if item_name in line_item_mapping:
                    key, df = line_item_mapping[item_name]
                    try:
                        if key in df.index and date in df.columns:
                            value = df.loc[key, date]
                            if pd.notna(value):
                                line_item_dict[item_name] = float(value)
                            else:
                                line_item_dict[item_name] = None
                        else:
                            line_item_dict[item_name] = None
                    except:
                        line_item_dict[item_name] = None
                else:
                    line_item_dict[item_name] = None

            results.append(LineItem(**line_item_dict))

        return results

    except Exception as e:
        print(f"Error searching line items for {ticker}: {str(e)}")
        return []


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
    """
    Stub function for insider trades (not available in Yahoo Finance).

    Returns empty list. Agents should handle this gracefully by skipping
    insider analysis or using alternative data sources.

    Args:
        ticker: Stock ticker symbol
        end_date: End date (YYYY-MM-DD)
        start_date: Start date (YYYY-MM-DD, optional)
        limit: Max number of trades
        api_key: Not used

    Returns:
        Empty list (insider trades not available)
    """
    # Note: Insider trading data is not available through yfinance
    # Agents using this should handle empty list gracefully
    return []


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
    """
    Fetch company news from Yahoo Finance.

    Note: Yahoo Finance provides basic news without sentiment analysis.
    Sentiment field will be None.

    Args:
        ticker: Stock ticker symbol
        end_date: End date (YYYY-MM-DD)
        start_date: Start date (YYYY-MM-DD, optional)
        limit: Max number of articles
        api_key: Not used

    Returns:
        List of CompanyNews objects (without sentiment)
    """
    # Create cache key
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"

    # Check cache first
    if cached_data := _cache.get_company_news(cache_key):
        return [CompanyNews(**news) for news in cached_data]

    try:
        stock = yf.Ticker(ticker)
        news_items = stock.news

        if not news_items:
            return []

        # Convert to CompanyNews objects
        news_list = []
        for item in news_items[:limit]:
            # Convert Unix timestamp to ISO format
            news_date = datetime.fromtimestamp(item.get('providerPublishTime', 0))

            # Filter by date range if provided
            if start_date:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                if news_date < start_dt:
                    continue

            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            if news_date > end_dt:
                continue

            news_list.append(CompanyNews(
                ticker=ticker,
                title=item.get('title', ''),
                author=item.get('publisher', 'Unknown'),
                source=item.get('publisher', 'Yahoo Finance'),
                date=news_date.strftime('%Y-%m-%dT%H:%M:%S'),
                url=item.get('link', ''),
                sentiment=None,  # Yahoo Finance doesn't provide sentiment
            ))

        # Cache the results
        if news_list:
            _cache.set_company_news(cache_key, [n.model_dump() for n in news_list])

        return news_list

    except Exception as e:
        print(f"Error fetching company news for {ticker}: {str(e)}")
        return []


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
) -> float | None:
    """
    Fetch current market cap from Yahoo Finance.

    Args:
        ticker: Stock ticker symbol
        end_date: End date (not used for current data)
        api_key: Not used

    Returns:
        Market cap as float, or None if not available
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return info.get('marketCap')
    except Exception as e:
        print(f"Error fetching market cap for {ticker}: {str(e)}")
        return None


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


def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    """
    Get price data as a pandas DataFrame.

    Args:
        ticker: Stock ticker symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        api_key: Not used

    Returns:
        DataFrame with OHLCV data
    """
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)
