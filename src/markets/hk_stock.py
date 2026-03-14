"""港股市场适配器（占位）"""
from src.markets.base import MarketAdapter


class HKStockAdapter(MarketAdapter):
    def supports_ticker(self, ticker: str) -> bool:
        return ticker.endswith('.HK')

    def get_prices(self, ticker: str, start_date: str, end_date: str):
        return []

    def get_company_news(self, ticker: str, end_date: str, limit: int):
        return []

    def get_financial_metrics(self, ticker: str, end_date: str):
        return {}
