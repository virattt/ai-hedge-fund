"""Data sources for different markets."""

from src.markets.sources.akshare_source import AKShareSource
from src.markets.sources.akshare_news_source import AKShareNewsSource
from src.markets.sources.yfinance_source import YFinanceSource
from src.markets.sources.newsnow_source import NewsNowSource
from src.markets.sources.sina_finance_source import SinaFinanceSource
from src.markets.sources.xueqiu_source import XueqiuSource

__all__ = [
    "AKShareSource",
    "AKShareNewsSource",
    "YFinanceSource",
    "NewsNowSource",
    "SinaFinanceSource",
    "XueqiuSource",
]
