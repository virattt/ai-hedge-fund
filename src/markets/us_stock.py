"""
美股市场适配器

复用现有 src.tools.api 中的美股数据获取逻辑
"""
from typing import List, Dict
from src.markets.base import MarketAdapter
from src.tools import api


class USStockAdapter(MarketAdapter):
    """
    美股市场数据适配器

    复用现有的 src.tools.api 中的美股数据获取逻辑，
    将其包装为统一的 MarketAdapter 接口。
    """

    def supports_ticker(self, ticker: str) -> bool:
        """
        检查是否支持该ticker（美股格式）

        美股ticker特征：
        - 不包含点号后缀（如 .SH, .SZ, .HK）
        - 不是期货格式（不以 =F 结尾）
        - 通常是纯大写字母（1-5个字符）

        Args:
            ticker: 股票代码

        Returns:
            bool: True表示支持美股格式，False表示不支持
        """
        # 排除其他市场格式
        if '.' in ticker:
            return False
        if ticker.endswith('=F'):
            return False

        # 美股ticker必须是纯大写字母
        return ticker.isupper() and ticker.isalpha()

    def get_prices(self, ticker: str, start_date: str, end_date: str):
        return []

    def get_company_news(self, ticker: str, end_date: str, limit: int):
        return []

    def get_financial_metrics(self, ticker: str, end_date: str):
        return {}
