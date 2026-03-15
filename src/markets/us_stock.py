"""
美股市场适配器

复用现有 src.tools.api 中的美股数据获取逻辑
"""
import logging
from typing import List, Dict, Optional
from src.markets.base import MarketAdapter
from src.tools import api
from src.data.validation import DataValidator
from src.markets.sources.newsnow_source import NewsNowSource

logger = logging.getLogger(__name__)


class USStockAdapter(MarketAdapter):
    """
    美股市场数据适配器

    复用现有的 src.tools.api 中的美股数据获取逻辑，
    将其包装为统一的 MarketAdapter 接口。
    """

    def __init__(self, validator: Optional[DataValidator] = None):
        """
        Initialize US stock adapter.

        Args:
            validator: Data validator instance (optional, not used for US stocks)
        """
        # US stock adapter uses legacy API, no data sources needed
        # Pass empty list to satisfy base class requirements
        super().__init__(
            market="US",
            data_sources=[],
            validator=validator,
        )

        # Initialize news sources with fallback chain
        self.news_sources = [
            NewsNowSource(),  # Free, primary source
            # Financial Datasets API handled by api.py as fallback
        ]

    def normalize_ticker(self, ticker: str) -> str:
        """
        Normalize ticker for US market.

        Args:
            ticker: Raw ticker (e.g., 'AAPL', 'aapl')

        Returns:
            Normalized ticker (uppercase)
        """
        return ticker.upper().strip()

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

        使用多源fallback策略：
        1. NewsNow (免费，无速率限制)
        2. Financial Datasets API (付费，有速率限制)

        Args:
            ticker: 股票代码（如 AAPL）
            end_date: 截止日期（YYYY-MM-DD）
            limit: 返回新闻条数限制

        Returns:
            List[Dict]: 新闻列表，包含 title, published, source, link, sentiment
        """
        # Try free sources first
        for source in self.news_sources:
            try:
                news = source.get_company_news(ticker, end_date, limit=limit)
                if news:
                    logger.info(f"[USStock] ✓ Got {len(news)} news from {source.name}")
                    # Convert to expected format
                    result = []
                    for n in news:
                        result.append({
                            "title": n.get("title", ""),
                            "published": n.get("date", ""),
                            "source": n.get("source", ""),
                            "link": n.get("url", ""),
                            "sentiment": n.get("sentiment")
                        })
                    return result
                else:
                    logger.info(f"[USStock] ⚠ {source.name} returned no data")
            except Exception as e:
                logger.warning(f"[USStock] ✗ {source.name} failed: {e}")
                continue

        # All free sources failed, fallback to Financial API via api.py
        logger.warning(f"[USStock] All free news sources failed, using Financial API fallback")
        try:
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
                    "published": news.date,  # CompanyNews的date字段映射到published
                    "source": news.source,
                    "link": news.url,  # CompanyNews的url字段映射到link
                    "sentiment": news.sentiment
                })

            return result
        except Exception as e:
            logger.error(f"[USStock] Financial API also failed: {e}")
            return []

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
