"""Alpha Vantage provider - free tier (25 req/day), fundamentals and earnings."""

import os
import time

import requests

from src.data.models import CompanyNews, FinancialMetrics, InsiderTrade, Price

from .base import DataProvider


class AlphaVantageProvider(DataProvider):
    """Alpha Vantage API. Free tier: 25 requests/day. Good for fundamentals fallback."""

    BASE = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("ALPHA_VANTAGE_API_KEY", "")

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        **kwargs: object,
    ) -> list[Price]:
        if not self._api_key:
            return []
        try:
            resp = requests.get(
                self.BASE,
                params={
                    "function": "TIME_SERIES_DAILY",
                    "symbol": ticker,
                    "apikey": self._api_key,
                    "outputsize": "full",
                },
                timeout=10,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            series = data.get("Time Series (Daily)") or {}
            out: list[Price] = []
            for date_str, ohlcv in series.items():
                if date_str < start_date or date_str > end_date:
                    continue
                try:
                    out.append(
                        Price(
                            open=float(ohlcv["1. open"]),
                            high=float(ohlcv["2. high"]),
                            low=float(ohlcv["3. low"]),
                            close=float(ohlcv["4. close"]),
                            volume=int(float(ohlcv["5. volume"])),
                            time=date_str + "T00:00:00Z",
                        )
                    )
                except (KeyError, TypeError, ValueError):
                    continue
            out.sort(key=lambda p: p.time)
            return out
        except Exception:
            return []

    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
        **kwargs: object,
    ) -> list[FinancialMetrics]:
        if not self._api_key:
            return []
        try:
            resp = requests.get(
                self.BASE,
                params={
                    "function": "OVERVIEW",
                    "symbol": ticker,
                    "apikey": self._api_key,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                return []
            d = resp.json()
            if not d or "Symbol" not in d:
                return []
            mcap = d.get("MarketCapitalization")
            try:
                mcap_f = float(mcap) if mcap else None
            except (TypeError, ValueError):
                mcap_f = None
            pe = d.get("PERatio")
            pb = d.get("PriceToBookRatio")
            eps = d.get("EPS")
            roe = d.get("ReturnOnEquityTTM")
            rev_growth = d.get("QuarterlyRevenueGrowthYOY")
            earn_growth = d.get("QuarterlyEarningsGrowthYOY")
            oper_margin = d.get("OperatingMarginTTM")
            net_margin = d.get("ProfitMargin")

            def _f(x: str | None) -> float | None:
                if x is None:
                    return None
                try:
                    return float(x)
                except (TypeError, ValueError):
                    return None

            m = FinancialMetrics(
                ticker=ticker,
                report_period=end_date,
                period=period,
                currency="USD",
                market_cap=mcap_f,
                enterprise_value=None,
                price_to_earnings_ratio=_f(pe),
                price_to_book_ratio=_f(pb),
                price_to_sales_ratio=None,
                enterprise_value_to_ebitda_ratio=None,
                enterprise_value_to_revenue_ratio=None,
                free_cash_flow_yield=None,
                peg_ratio=None,
                gross_margin=None,
                operating_margin=_f(oper_margin),
                net_margin=_f(net_margin),
                return_on_equity=_f(roe),
                return_on_assets=None,
                return_on_invested_capital=None,
                asset_turnover=None,
                inventory_turnover=None,
                receivables_turnover=None,
                days_sales_outstanding=None,
                operating_cycle=None,
                working_capital_turnover=None,
                current_ratio=None,
                quick_ratio=None,
                cash_ratio=None,
                operating_cash_flow_ratio=None,
                debt_to_equity=None,
                debt_to_assets=None,
                interest_coverage=None,
                revenue_growth=_f(rev_growth),
                earnings_growth=_f(earn_growth),
                book_value_growth=None,
                earnings_per_share_growth=None,
                free_cash_flow_growth=None,
                operating_income_growth=None,
                ebitda_growth=None,
                payout_ratio=None,
                earnings_per_share=_f(eps),
                book_value_per_share=None,
                free_cash_flow_per_share=None,
            )
            return [m]
        except Exception:
            return []

    def get_company_news(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
        **kwargs: object,
    ) -> list[CompanyNews]:
        return []

    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
        **kwargs: object,
    ) -> list[InsiderTrade]:
        return []
