"""
商品期货市场适配器

使用yfinance库获取商品期货数据，使用Google News RSS获取相关新闻
"""
from typing import List, Dict, Optional
import yfinance as yf
import feedparser
from dateutil import parser as date_parser

from src.markets.base import MarketAdapter
from src.data.validation import DataValidator


class CommodityAdapter(MarketAdapter):
    """
    商品期货市场数据适配器

    使用yfinance库获取期货价格数据（如黄金GC=F、原油CL=F等）
    使用Google News RSS获取商品相关新闻
    """

    def __init__(self, validator: Optional[DataValidator] = None):
        """
        Initialize Commodity adapter.

        Args:
            validator: Data validator instance (optional, not used for commodities)
        """
        # Commodity adapter uses yfinance directly, no data sources needed
        # Pass empty list to satisfy base class requirements
        super().__init__(
            market="COMMODITY",
            data_sources=[],
            validator=validator,
        )

    # 常见期货代码到商品名称的映射
    COMMODITY_NAMES = {
        "GC": "Gold",           # 黄金
        "SI": "Silver",         # 白银
        "CL": "Crude Oil",      # 原油
        "NG": "Natural Gas",    # 天然气
        "HG": "Copper",         # 铜
        "ZC": "Corn",           # 玉米
        "ZW": "Wheat",          # 小麦
        "ZS": "Soybean",        # 大豆
        "CT": "Cotton",         # 棉花
        "KC": "Coffee",         # 咖啡
        "SB": "Sugar",          # 糖
        "CC": "Cocoa",          # 可可
        "PL": "Platinum",       # 铂金
        "PA": "Palladium",      # 钯金
    }

    def normalize_ticker(self, ticker: str) -> str:
        """
        标准化期货ticker为统一格式

        Args:
            ticker: 原始期货代码（如 GC=F, gc=f）

        Returns:
            str: 标准化后的期货代码（如 GC=F）
        """
        ticker = ticker.upper().strip()

        # 期货代码必须以=F结尾
        if not ticker.endswith("=F"):
            self.logger.warning(f"Invalid commodity ticker format: {ticker}, expected format: XX=F")

        return ticker

    def supports_ticker(self, ticker: str) -> bool:
        """
        检查是否支持该ticker（期货格式：XX=F）

        Args:
            ticker: 期货代码

        Returns:
            bool: True表示支持期货格式，False表示不支持
        """
        ticker = ticker.upper().strip()

        # 必须以=F结尾才支持
        # 不支持其他格式，以避免与美股混淆
        return ticker.endswith("=F") and len(ticker) > 2

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Dict]:
        """
        获取商品期货历史价格数据

        使用yfinance库获取期货价格数据。

        Args:
            ticker: 期货代码（如 GC=F）
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）

        Returns:
            List[Dict]: 价格数据列表，包含 date, open, high, low, close, volume

        Raises:
            Exception: 数据获取失败
        """
        # 标准化ticker格式
        ticker = self.normalize_ticker(ticker)

        try:
            commodity = yf.Ticker(ticker)
            df = commodity.history(start=start_date, end=end_date)

            if df.empty:
                return []

            result = []
            for date_idx, row in df.iterrows():
                result.append(
                    {
                        "date": date_idx.strftime("%Y-%m-%d"),
                        "open": float(row["Open"]),
                        "close": float(row["Close"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "volume": int(row["Volume"]),
                    }
                )

            return result
        except Exception as e:
            raise Exception(f"获取{ticker}价格数据失败: {str(e)}")

    def _extract_commodity_name(self, ticker: str) -> str:
        """
        从ticker中提取商品名称（用于新闻搜索）

        Args:
            ticker: 期货代码（如 GC=F）

        Returns:
            str: 商品名称（如 Gold）
        """
        # 标准化并移除=F后缀
        ticker = self.normalize_ticker(ticker)
        code = ticker.replace("=F", "")

        # 查找映射表
        return self.COMMODITY_NAMES.get(code, code)

    def get_company_news(self, ticker: str, end_date: str, limit: int) -> List[Dict]:
        """
        获取商品相关新闻

        商品没有公司新闻，使用Google News RSS搜索商品名称相关新闻。

        Args:
            ticker: 期货代码（如 GC=F）
            end_date: 截止日期（YYYY-MM-DD）
            limit: 返回新闻条数限制

        Returns:
            List[Dict]: 新闻列表，包含 title, published, source, link, sentiment

        Raises:
            ValueError: ticker格式不支持
        """
        if not self.supports_ticker(ticker):
            raise ValueError(f"不支持的ticker格式: {ticker}")

        try:
            # 提取商品名称用于搜索
            commodity_name = self._extract_commodity_name(ticker)

            # 使用Google News RSS搜索商品新闻
            rss_url = f"https://news.google.com/rss/search?q={commodity_name}+commodity&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(rss_url)

            result = []
            for entry in feed.entries[:limit]:
                # 转换发布时间为ISO格式
                published = ""
                if hasattr(entry, "published"):
                    try:
                        dt = date_parser.parse(entry.published)
                        published = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    except Exception:
                        published = ""

                result.append(
                    {
                        "title": entry.get("title", ""),
                        "published": published,
                        "source": "google",
                        "link": entry.get("link", ""),
                        "sentiment": None,
                    }
                )

            return result
        except Exception:
            # 新闻获取失败时返回空列表（不阻断主流程）
            return []

    def get_financial_metrics(self, ticker: str, end_date: str) -> Dict:
        """
        获取财务指标

        商品期货没有财务指标，返回空字典。

        Args:
            ticker: 期货代码（如 GC=F）
            end_date: 截止日期（YYYY-MM-DD）

        Returns:
            Dict: 空字典（商品没有财务指标）

        Raises:
            ValueError: ticker格式不支持
        """
        if not self.supports_ticker(ticker):
            raise ValueError(f"不支持的ticker格式: {ticker}")

        # 商品期货没有财务指标
        return {}
