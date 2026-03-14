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

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Dict]:
        """
        获取美股历史价格数据

        直接调用现有的 api.get_prices() 函数，并将 Pydantic 模型转换为字典。

        Args:
            ticker: 股票代码（如 AAPL）
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）

        Returns:
            List[Dict]: 价格数据列表，包含 date, open, high, low, close, volume
        """
        # 调用现有API获取Price对象列表
        prices = api.get_prices(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date
        )

        # 转换为MarketAdapter期望的字典格式
        result = []
        for price in prices:
            result.append({
                "date": price.time,  # Price模型使用time字段存储日期
                "open": price.open,
                "high": price.high,
                "low": price.low,
                "close": price.close,
                "volume": price.volume
            })

        return result

    def get_company_news(self, ticker: str, end_date: str, limit: int) -> List[Dict]:
        """
        获取美股相关新闻

        直接调用现有的 api.get_company_news() 函数，并将 Pydantic 模型转换为字典。

        Args:
            ticker: 股票代码（如 AAPL）
            end_date: 截止日期（YYYY-MM-DD）
            limit: 返回新闻条数限制

        Returns:
            List[Dict]: 新闻列表，包含 title, url, published_date, summary, source, sentiment
        """
        # 调用现有API获取CompanyNews对象列表
        news_list = api.get_company_news(
            ticker=ticker,
            end_date=end_date,
            limit=limit
        )

        # 转换为MarketAdapter期望的字典格式
        result = []
        for news in news_list:
            result.append({
                "title": news.title,
                "url": news.url,
                "published_date": news.date,  # CompanyNews使用date字段
                "summary": "",  # CompanyNews模型没有summary字段
                "source": news.source,
                "sentiment": news.sentiment
            })

        return result

    def get_financial_metrics(self, ticker: str, end_date: str) -> Dict:
        """
        获取美股财务指标

        直接调用现有的 api.get_financial_metrics() 函数，并将 Pydantic 模型转换为字典。

        注意：API返回的字段与MarketAdapter期望的字段有差异，需要映射：
        - price_to_earnings_ratio -> pe_ratio
        - price_to_book_ratio -> pb_ratio
        - market_cap -> market_cap
        - revenue和net_profit需要通过search_line_items单独获取（此处暂不实现）

        Args:
            ticker: 股票代码（如 AAPL）
            end_date: 截止日期（YYYY-MM-DD）

        Returns:
            Dict: 财务指标字典
        """
        # 调用现有API获取FinancialMetrics对象列表
        metrics_list = api.get_financial_metrics(
            ticker=ticker,
            end_date=end_date
        )

        # 如果没有数据，返回空字典
        if not metrics_list:
            return {}

        # 取第一个（最新的）指标
        metrics = metrics_list[0]

        # 转换为MarketAdapter期望的字典格式
        return {
            "pe_ratio": metrics.price_to_earnings_ratio or 0,
            "pb_ratio": metrics.price_to_book_ratio or 0,
            "market_cap": metrics.market_cap or 0,
            "revenue": 0,  # API中的FinancialMetrics没有revenue字段，需要单独查询
            "net_profit": 0  # API中的FinancialMetrics没有net_profit字段，需要单独查询
        }
