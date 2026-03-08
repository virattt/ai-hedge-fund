"""YFinance provider - free OHLCV and basic fundamentals for US equities."""

from datetime import datetime

from src.data.models import CompanyNews, FinancialMetrics, InsiderTrade, Price

from .base import DataProvider


class YFinanceProvider(DataProvider):
    """Uses yfinance for prices and basic fundamentals. No line items or insider trades."""

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        **kwargs: object,
    ) -> list[Price]:
        try:
            import yfinance as yf

            t = yf.Ticker(ticker)
            df = t.history(start=start_date, end=end_date, auto_adjust=False)
            if df is None or df.empty:
                return []
            out: list[Price] = []
            for ts, row in df.iterrows():
                out.append(
                    Price(
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
                        time=ts.strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(ts, "strftime") else str(ts),
                    )
                )
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
        try:
            import yfinance as yf

            t = yf.Ticker(ticker)
            info = t.info
            if not info:
                return []
            mcap = info.get("marketCap")
            if mcap is None:
                return []
            pe = info.get("trailingPE")
            pb = info.get("priceToBook")
            ps = info.get("priceToSales")
            gross = info.get("grossMargins")
            oper = info.get("operatingMargins")
            net = info.get("profitMargins")
            roe = info.get("returnOnEquity")
            roa = info.get("returnOnAssets")
            cr = info.get("currentRatio")
            de = info.get("debtToEquity")
            rev_growth = info.get("revenueGrowth")
            earn_growth = info.get("earningsGrowth")

            m = FinancialMetrics(
                ticker=ticker,
                report_period=end_date,
                period=period,
                currency=info.get("currency", "USD"),
                market_cap=float(mcap) if mcap is not None else None,
                enterprise_value=info.get("enterpriseValue"),
                price_to_earnings_ratio=float(pe) if pe is not None else None,
                price_to_book_ratio=float(pb) if pb is not None else None,
                price_to_sales_ratio=float(ps) if ps is not None else None,
                enterprise_value_to_ebitda_ratio=None,
                enterprise_value_to_revenue_ratio=None,
                free_cash_flow_yield=None,
                peg_ratio=None,
                gross_margin=float(gross) if gross is not None else None,
                operating_margin=float(oper) if oper is not None else None,
                net_margin=float(net) if net is not None else None,
                return_on_equity=float(roe) if roe is not None else None,
                return_on_assets=float(roa) if roa is not None else None,
                return_on_invested_capital=None,
                asset_turnover=None,
                inventory_turnover=None,
                receivables_turnover=None,
                days_sales_outstanding=None,
                operating_cycle=None,
                working_capital_turnover=None,
                current_ratio=float(cr) if cr is not None else None,
                quick_ratio=info.get("quickRatio"),
                cash_ratio=None,
                operating_cash_flow_ratio=None,
                debt_to_equity=float(de) if de is not None else None,
                debt_to_assets=None,
                interest_coverage=None,
                revenue_growth=float(rev_growth) if rev_growth is not None else None,
                earnings_growth=float(earn_growth) if earn_growth is not None else None,
                book_value_growth=None,
                earnings_per_share_growth=None,
                free_cash_flow_growth=None,
                operating_income_growth=None,
                ebitda_growth=None,
                payout_ratio=info.get("payoutRatio"),
                earnings_per_share=info.get("trailingEps"),
                book_value_per_share=info.get("bookValue"),
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
        try:
            import yfinance as yf

            t = yf.Ticker(ticker)
            raw = t.news
            if not raw:
                return []
            out: list[CompanyNews] = []
            for n in raw[:limit]:
                pub_ts = n.get("providerPublishTime") or 0
                try:
                    dt = datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%dT%H:%M:%SZ")
                except Exception:
                    dt = ""
                out.append(
                    CompanyNews(
                        ticker=ticker,
                        title=n.get("title") or "",
                        author=n.get("publisher", ""),
                        source=n.get("publisher", ""),
                        date=dt,
                        url=n.get("link") or "",
                        sentiment=None,
                    )
                )
            return out
        except Exception:
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
