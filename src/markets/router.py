"""
市场路由器

根据ticker格式自动路由到对应的市场适配器
"""
from typing import List, Dict
from src.markets.base import MarketAdapter


class MarketRouter:
    """
    市场路由器

    根据ticker的格式特征，自动选择合适的市场适配器
    支持美股、A股、港股、商品期货等多个市场
    """

    def __init__(self):
        """
        初始化路由器

        注意：适配器的顺序很重要！
        - 先检查特定模式（A股、港股、商品）
        - 最后检查默认模式（美股）
        """
        self.adapters: List[MarketAdapter] = []
        self._initialize_adapters()

    def _initialize_adapters(self):
        """
        初始化所有市场适配器

        延迟导入避免循环依赖
        """
        # 延迟导入，避免循环依赖
        from src.markets.cn_stock import CNStockAdapter
        from src.markets.hk_stock import HKStockAdapter
        from src.markets.commodity import CommodityAdapter
        from src.markets.us_stock import USStockAdapter

        # 顺序很重要：先检查特定模式，最后检查默认
        self.adapters = [
            CNStockAdapter(),      # A股: 600000.SH, 000001.SZ
            HKStockAdapter(),      # 港股: 0700.HK
            CommodityAdapter(),    # 商品: GC=F
            USStockAdapter(),      # 美股: AAPL (默认)
        ]

    def route(self, ticker: str) -> MarketAdapter:
        """
        将ticker路由到对应的市场适配器

        Args:
            ticker: 股票/商品代码

        Returns:
            MarketAdapter: 支持该ticker的适配器实例

        Raises:
            ValueError: 如果没有适配器支持该ticker

        Examples:
            >>> router = MarketRouter()
            >>> adapter = router.route("600000.SH")
            >>> isinstance(adapter, CNStockAdapter)
            True
        """
        for adapter in self.adapters:
            if adapter.supports_ticker(ticker):
                return adapter

        raise ValueError(f"未找到支持该ticker的适配器: {ticker}")

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """
        便捷方法：获取价格数据

        自动路由到对应适配器并获取数据

        Args:
            ticker: 股票/商品代码
            start_date: 开始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD"

        Returns:
            List[Dict]: 价格数据列表
        """
        adapter = self.route(ticker)
        return adapter.get_prices(ticker, start_date, end_date)

    def get_company_news(
        self,
        ticker: str,
        end_date: str,
        limit: int
    ) -> List[Dict]:
        """
        便捷方法：获取新闻数据

        自动路由到对应适配器并获取数据

        Args:
            ticker: 股票/商品代码
            end_date: 截止日期 "YYYY-MM-DD"
            limit: 最大新闻数量

        Returns:
            List[Dict]: 新闻列表
        """
        adapter = self.route(ticker)
        return adapter.get_company_news(ticker, end_date, limit)

    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str
    ) -> Dict:
        """
        便捷方法：获取财务指标

        自动路由到对应适配器并获取数据

        Args:
            ticker: 股票代码
            end_date: 截止日期 "YYYY-MM-DD"

        Returns:
            Dict: 财务指标字典
        """
        adapter = self.route(ticker)
        return adapter.get_financial_metrics(ticker, end_date)

    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """
内部交易数据

        自动路由到对应适配器并获取数据

        Args:
            ticker: 股票代码
            end_date: 截止日期 "YYYY-MM-DD"
            start_date: 开始日期 "YYYY-MM-DD" (可选)
            limit: 最大数量

        Returns:
            List[Dict]: 内部交易列表
        """
        adapter = self.route(ticker)
        return adapter.get_insider_trades(ticker, end_date, start_date, limit)
