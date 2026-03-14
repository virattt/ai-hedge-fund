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

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Dict]:
        """
        获取港股历史价格数据

        使用yfinance库获取历史价格数据。

        Args:
            ticker: 股票代码（如 0700.HK）
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）

        Returns:
            List[Dict]: 价格数据列表，包含 date, open, high, low, close, volume

        Raises:
            Exception: 数据获取失败
        """
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date)

            if df.empty:
                return []

            result = []
            for date_idx, row in df.iterrows():
                result.append({
                    "date": date_idx.strftime("%Y-%m-%d"),
                    "open": float(row['Open']),
                    "close": float(row['Close']),
                    "high": float(row['High']),
                    "low": float(row['Low']),
                    "volume": int(row['Volume'])
                })

            return result
        except Exception as e:
            raise Exception(f"获取{ticker}价格数据失败: {str(e)}")

    def get_company_news(self, ticker: str, end_date: str, limit: int) -> List[Dict]:
        """
        获取港股相关新闻

        使用yfinance的news API获取新闻数据。

        Args:
            ticker: 股票代码（如 0700.HK）
            end_date: 截止日期（YYYY-MM-DD）
            limit: 返回新闻条数限制

        Returns:
            List[Dict]: 新闻列表，包含 title, published, source, link, sentiment
        """
        if not self.supports_ticker(ticker):
            raise ValueError(f"不支持的ticker格式: {ticker}")

        try:
            stock = yf.Ticker(ticker)
            news_list = stock.news if hasattr(stock, 'news') else []

            result = []
            for news_item in news_list[:limit]:
                # 转换时间戳为ISO格式
                published = ""
                if 'providerPublishTime' in news_item:
                    dt = datetime.fromtimestamp(news_item['providerPublishTime'])
                    published = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

                result.append({
                    "title": news_item.get('title', ''),
                    "published": published,
                    "source": news_item.get('publisher', 'yfinance'),
                    "link": news_item.get('link', ''),
                    "sentiment": None
                })

            return result
        except Exception:
            return []

    def get_financial_metrics(self, ticker: str, end_date: str):
        return {}
