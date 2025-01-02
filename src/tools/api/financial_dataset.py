from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Union

import pandas as pd
import requests

from .base import BaseAPIClient
from .config import FinancialDatasetAPIConfig


class Period(str, Enum):
    """Enumeration of valid reporting periods."""

    TTM = "ttm"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class FinancialDatasetAPI(BaseAPIClient):
    """Client for accessing financial dataset API endpoints."""

    def __init__(self, config: FinancialDatasetAPIConfig = None):
        """Initialize API client with optional custom config."""
        self.config = config if config else FinancialDatasetAPIConfig.from_env()
        super().__init__(self.config)

    def _get_headers(self) -> Dict[str, str]:
        return {"X-API-KEY": self.config.api_key}

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        response.raise_for_status()
        return response.json()

    @staticmethod
    def prices_to_df(prices: List[Dict[str, Any]]) -> pd.DataFrame:
        df = pd.DataFrame(prices)
        df["Date"] = pd.to_datetime(df["time"])
        df.set_index("Date", inplace=True)

        numeric_cols = ["open", "close", "high", "low", "volume"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df.sort_index()

    def get_financial_metrics(
        self,
        ticker: str,
        report_period: Union[str, datetime],
        period: Period = Period.TTM,
        limit: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Fetch financial metrics for a given ticker.

        Args:
            ticker: Stock ticker symbol
            report_period: End date for the report period
            period: Reporting period type (TTM, quarterly, annual)
            limit: Maximum number of records to return

        Returns:
            List of financial metrics dictionaries
        """
        params = {
            "ticker": ticker,
            "report_period_lte": report_period,
            "limit": limit,
            "period": period,
        }

        response = self._make_request(endpoint="/financial-metrics/", params=params)

        return self._get_data_or_raise(
            response, "financial_metrics", "No financial metrics found"
        )

    def search_line_items(
        self,
        ticker: str,
        line_items: List[str],
        period: Period = Period.TTM,
        limit: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Search for specific line items in financial statements.

        Args:
            ticker: Stock ticker symbol
            line_items: List of line items to search for
            period: Reporting period type
            limit: Maximum number of records to return
        Returns:
            List of line items dictionaries
        """
        payload = {
            "tickers": [ticker],
            "line_items": line_items,
            "period": period,
            "limit": limit,
        }

        response = self._make_request(
            endpoint="/financials/search/line-items", method="POST", json_data=payload
        )

        return self._get_data_or_raise(
            response, "search_results", "No line items found"
        )

    def get_insider_trades(
        self, ticker: str, end_date: Union[str, datetime], limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Fetch insider trading data.

        Args:
            ticker: Stock ticker symbol
            end_date: End date for the search period
            limit: Maximum number of trades to return
        Returns:
            List of insider trades dictionaries
        """
        params = {"ticker": ticker, "filing_date_lte": end_date, "limit": limit}

        response = self._make_request(endpoint="/insider-trades/", params=params)

        return self._get_data_or_raise(
            response, "insider_trades", "No insider trades found"
        )

    def get_market_cap(self, ticker: str) -> float:
        """
        Fetch market capitalization for a company.

        Args:
            ticker: Stock ticker symbol
        Returns:
            Market capitalization as a float
        """
        response = self._make_request(
            endpoint="/company/facts", params={"ticker": ticker}
        )

        company_facts = self._get_data_or_raise(
            response, "company_facts", "No company facts found"
        )

        market_cap = company_facts.get("market_cap")
        if not market_cap:
            raise Exception("Market cap not available")

        return market_cap

    def get_prices(
        self,
        ticker: str,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
    ) -> pd.DataFrame:
        """
        Fetch and format price data as a DataFrame.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date for price data
            end_date: End date for price data

        Returns:
            DataFrame with price data indexed by date
        """
        params = {
            "ticker": ticker,
            "interval": "day",
            "interval_multiplier": 1,
            "start_date": start_date,
            "end_date": end_date,
        }

        response = self._make_request(endpoint="/prices/", params=params)

        prices = self._get_data_or_raise(response, "prices", "No price data found")

        return FinancialDatasetAPI.prices_to_df(prices)
