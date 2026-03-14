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

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Dict]:
        """
        获取A股历史价格数据（前复权）

        Args:
            ticker: 股票代码，如 "600000.SH" 或 "000001.SZ"
            start_date: 开始日期，格式 "YYYY-MM-DD"
            end_date: 结束日期，格式 "YYYY-MM-DD"

        Returns:
            List[Dict]: 价格数据列表，包含日期、开盘价、最高价、最低价、收盘价、成交量

        Raises:
            ValueError: ticker格式不支持
            Exception: 数据获取失败
        """
        import akshare as ak

        if not self.supports_ticker(ticker):
            raise ValueError(f"不支持的ticker格式: {ticker}")

        # 移除交易所后缀，获取纯股票代码
        symbol = ticker.split('.')[0]

        # 转换日期格式：YYYY-MM-DD -> YYYYMMDD
        start_date_formatted = start_date.replace('-', '')
        end_date_formatted = end_date.replace('-', '')

        try:
            # 使用AkShare获取A股历史数据（前复权）
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                start_date=start_date_formatted,
                end_date=end_date_formatted,
                adjust="qfq"  # 前复权
            )

            # 转换为标准格式
            prices = []
            for _, row in df.iterrows():
                prices.append({
                    "date": row["日期"],
                    "open": float(row["开盘"]),
                    "close": float(row["收盘"]),
                    "high": float(row["最高"]),
                    "low": float(row["最低"]),
                    "volume": int(row["成交量"])
                })

            return prices

        except Exception as e:
            raise Exception(f"获取{ticker}价格数据失败: {str(e)}")

    def get_company_news(self, ticker: str, end_date: str, limit: int) -> List[Dict]:
        """
        获取A股相关新闻（通过Google News RSS）

        Args:
            ticker: 股票代码，如 "600000.SH"
            end_date: 截止日期，格式 "YYYY-MM-DD"
            limit: 最大新闻数量

        Returns:
            List[Dict]: 新闻列表，包含标题、链接、发布时间、来源、情绪

        Raises:
            ValueError: ticker格式不支持
            Exception: 数据获取失败
        """
        import feedparser

        if not self.supports_ticker(ticker):
            raise ValueError(f"不支持的ticker格式: {ticker}")

        # 移除交易所后缀，获取纯股票代码
        symbol = ticker.split('.')[0]

        try:
            # 使用Google News RSS搜索股票代码相关新闻
            rss_url = f"https://news.google.com/rss/search?q={symbol}+股票&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
            feed = feedparser.parse(rss_url)

            # 转换为标准格式
            news = []
            for entry in feed.entries[:limit]:
                news.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.get('published', ''),
                    "source": "Google News",
                    "sentiment": None  # 未分析情绪
                })

            return news

        except Exception as e:
            raise Exception(f"获取{ticker}新闻失败: {str(e)}")

    def get_financial_metrics(self, ticker: str, end_date: str) -> Dict:
        """
        获取A股财务指标

        Args:
            ticker: 股票代码，如 "600000.SH"
            end_date: 截止日期，格式 "YYYY-MM-DD"

        Returns:
            Dict: 财务指标字典，包含 eps、roe、pe_ratio、pb_ratio

        Raises:
            ValueError: ticker格式不支持
        """
        import akshare as ak

        if not self.supports_ticker(ticker):
            raise ValueError(f"不支持的ticker格式: {ticker}")

        # 移除交易所后缀，获取纯股票代码
        symbol = ticker.split('.')[0]

        try:
            # 使用AkShare获取财务摘要数据
            df = ak.stock_financial_abstract(symbol=symbol)

            # 如果没有数据，返回空字典
            if df.empty:
                return {}

            # 获取最新一期数据
            latest = df.iloc[0]

            # 转换为标准格式，使用get方法处理缺失字段
            return {
                "eps": float(latest.get("每股收益", 0)),
                "roe": float(latest.get("净资产收益率", 0)),
                "pe_ratio": float(latest.get("市盈率", 0)),
                "pb_ratio": float(latest.get("市净率", 0))
            }

        except Exception as e:
            # 财务数据获取失败时返回空字典（某些股票可能没有数据）
            return {}
