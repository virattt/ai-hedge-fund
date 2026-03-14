"""美股市场适配器（占位）"""
from src.markets.base import MarketAdapter


class USStockAdapter(MarketAdapter):
    def supports_ticker(self, ticker: str) -> bool:
        # 美股作为默认，支持所有不带特殊后缀的ticker
        return not any(suffix in ticker for suffix in ['.SH', '.SZ', '.HK', '=F'])

    def get_prices(self, ticker: str, start_date: str, end_date: str):
        return []

    def get_company_news(self, ticker: str, end_date: str, limit: int):
        return []

    def get_financial_metrics(self, ticker: str, end_date: str):
        return {}
