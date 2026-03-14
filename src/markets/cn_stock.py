"""
A股市场适配器

使用AkShare获取中国A股市场数据
"""
from typing import List, Dict
from src.markets.base import MarketAdapter


class CNStockAdapter(MarketAdapter):
    """
    A股市场数据适配器

    支持上海证券交易所（.SH）和深圳证券交易所（.SZ）的股票数据获取
    使用AkShare作为主要数据源，Google News RSS作为新闻来源
    """

    def supports_ticker(self, ticker: str) -> bool:
        """
        检查是否支持该ticker（A股格式：XXXXXX.SH 或 XXXXXX.SZ）

        Args:
            ticker: 股票代码，如 "600000.SH" 或 "000001.SZ"

        Returns:
            bool: True表示支持A股格式，False表示不支持
        """
        return ticker.endswith('.SH') or ticker.endswith('.SZ')

    def get_prices(self, ticker: str, start_date: str, end_date: str):
        return []

    def get_company_news(self, ticker: str, end_date: str, limit: int):
        return []

    def get_financial_metrics(self, ticker: str, end_date: str):
        return {}
