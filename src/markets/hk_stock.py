"""
港股市场适配器

使用yfinance库获取港股数据
"""
from typing import List, Dict
from datetime import datetime
import yfinance as yf

from src.markets.base import MarketAdapter


class HKStockAdapter(MarketAdapter):
    """
    港股市场数据适配器

    使用yfinance库获取香港交易所股票数据
    """

    def supports_ticker(self, ticker: str) -> bool:
        """
        检查是否支持该ticker（港股格式：XXXX.HK）

        Args:
            ticker: 股票代码

        Returns:
            bool: True表示支持港股格式，False表示不支持
        """
        return ticker.endswith('.HK')

    def get_prices(self, ticker: str, start_date: str, end_date: str):
        return []

    def get_company_news(self, ticker: str, end_date: str, limit: int):
        return []

    def get_financial_metrics(self, ticker: str, end_date: str):
        return {}
