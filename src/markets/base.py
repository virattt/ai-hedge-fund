"""
市场数据适配器基类

定义所有市场适配器必须实现的统一接口
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class MarketAdapter(ABC):
    """
    市场数据适配器抽象基类

    所有市场适配器（美股、A股、港股、商品）都必须继承此类
    并实现所有抽象方法，以提供统一的数据访问接口
    """

    @abstractmethod
    def supports_ticker(self, ticker: str) -> bool:
        """
        检查此适配器是否支持给定的ticker格式

        Args:
            ticker: 股票/商品代码，如 "AAPL", "600000.SH", "0700.HK", "GC=F"

        Returns:
            bool: True表示支持，False表示不支持

        Examples:
            >>> adapter.supports_ticker("600000.SH")
            True
            >>> adapter.supports_ticker("AAPL")
            False
        """
        pass

    @abstractmethod
    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """
        获取历史价格数据

        Args:
            ticker: 股票/商品代码
            start_date: 开始日期，格式 "YYYY-MM-DD"
            end_date: 结束日期，格式 "YYYY-MM-DD"

        Returns:
            List[Dict]: 价格数据列表，每个字典包含:
                - date: str, 日期 "YYYY-MM-DD"
                - open: float, 开盘价
                - high: float, 最高价
                - low: float, 最低价
                - close: float, 收盘价
                - volume: int, 成交量

        Raises:
            ValueError: ticker格式不支持
            Exception: 数据获取失败
        """
        pass

    @abstractmethod
    def get_company_news(
        self,
        ticker: str,
        end_date: str,
        limit: int
    ) -> List[Dict]:
        """
        获取公司/商品相关新闻

        Args:
            ticker: 股票/商品代码
            end_date: 截止日期，格式 "YYYY-MM-DD"
            limit: 最大新闻数量

        Returns:
            List[Dict]: 新闻列表，每个字典包含:
                - title: str, 新闻标题
                - published: str, 发布时间 ISO格式
                - source: str, 新闻来源
                - link: str, 新闻链接（可选）
                - sentiment: Optional[str], 情绪 (None表示未分析)

        Raises:
            ValueError: ticker格式不支持
            Exception: 数据获取失败
        """
        pass

    @abstractmethod
    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str
    ) -> Dict:
        """
        获取财务指标

        Args:
            ticker: 股票代码
            end_date: 截止日期，格式 "YYYY-MM-DD"

        Returns:
            Dict: 财务指标字典，可能包含:
                - pe_ratio: float, 市盈率
                - pb_ratio: float, 市净率
                - market_cap: float, 市值
                - revenue: float, 营收
                - net_profit: float, 净利润
                注意：商品期货返回空字典{}

        Raises:
            ValueError: ticker格式不支持
            Exception: 数据获取失败
        """
        pass
