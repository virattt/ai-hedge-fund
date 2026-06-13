import datetime
from typing import Any

import pandas as pd

from src.data.cache import get_cache
from src.data.models import CompanyNews, FinancialMetrics, InsiderTrade, LineItem, Price
from src.data.providers.base import FinancialDataProvider

_cache = get_cache()


LINE_ITEM_ALIASES = {
    "book_value_per_share": ["Book Value Per Share"],
    "capital_expenditure": ["Capital Expenditure", "Capital Expenditures"],
    "cash_and_equivalents": ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
    "current_assets": ["Current Assets", "Total Current Assets"],
    "current_liabilities": ["Current Liabilities", "Total Current Liabilities"],
    "depreciation_and_amortization": ["Depreciation And Amortization", "Depreciation Amortization Depletion"],
    "dividends_and_other_cash_distributions": ["Cash Dividends Paid", "Common Stock Dividend Paid"],
    "earnings_per_share": ["Diluted EPS", "Basic EPS", "Earnings Per Share"],
    "ebit": ["EBIT", "Operating Income"],
    "ebitda": ["EBITDA", "Normalized EBITDA"],
    "free_cash_flow": ["Free Cash Flow"],
    "gross_margin": ["Gross Margin"],
    "gross_profit": ["Gross Profit"],
    "interest_expense": ["Interest Expense", "Interest Expense Non Operating"],
    "net_income": ["Net Income", "Net Income Common Stockholders"],
    "operating_cash_flow": ["Operating Cash Flow", "Total Cash From Operating Activities"],
    "operating_expense": ["Operating Expense", "Total Operating Expenses"],
    "operating_income": ["Operating Income"],
    "operating_margin": ["Operating Margin"],
    "outstanding_shares": ["Ordinary Shares Number", "Share Issued"],
    "research_and_development": ["Research And Development"],
    "revenue": ["Total Revenue", "Operating Revenue"],
    "shareholders_equity": ["Stockholders Equity", "Total Equity Gross Minority Interest"],
    "total_assets": ["Total Assets"],
    "total_debt": ["Total Debt"],
    "total_liabilities": ["Total Liabilities Net Minority Interest", "Total Liab"],
}


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    numeric = _safe_float(value)
    if numeric is None:
        return 0
    return int(numeric)


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _growth(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    if previous == 0:
        return 0.0 if current == 0 else None
    return (current - previous) / abs(previous)


def _first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _normalize_yfinance_ratio(value: Any) -> float | None:
    numeric = _safe_float(value)
    if numeric is None:
        return None
    if abs(numeric) > 10:
        return numeric / 100
    return numeric


def _date_str(value: Any) -> str:
    if isinstance(value, (datetime.datetime, datetime.date, pd.Timestamp)):
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    return str(value)


def _to_datetime(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    try:
        return datetime.datetime.strptime(value[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _date_lte(value: Any, end_date: str) -> bool:
    item_date = _to_datetime(_date_str(value))
    end = _to_datetime(end_date)
    if item_date is None or end is None:
        return True
    return item_date.date() <= end.date()


def _get_fast_info_value(fast_info: Any, key: str) -> Any:
    if fast_info is None:
        return None
    if isinstance(fast_info, dict):
        return fast_info.get(key)
    return getattr(fast_info, key, None)


class YFinanceProvider(FinancialDataProvider):
    name = "yfinance"

    def _yf(self):
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError("The yfinance package is required when FINANCIAL_DATA_PROVIDER=yfinance.") from exc
        return yf

    def _ticker(self, ticker: str):
        return self._yf().Ticker(ticker)

    def get_prices(self, ticker: str, start_date: str, end_date: str, api_key: str | None = None) -> list[Price]:
        cache_key = f"{self.name}:{ticker}_{start_date}_{end_date}"
        if cached_data := _cache.get_prices(cache_key):
            return [Price(**price) for price in cached_data]

        try:
            end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1)
            history = self._ticker(ticker).history(start=start_date, end=end_dt.strftime("%Y-%m-%d"), auto_adjust=False)
        except RuntimeError:
            raise
        except Exception:
            return []

        if history is None or history.empty:
            return []

        prices: list[Price] = []
        for timestamp, row in history.iterrows():
            open_price = _safe_float(row.get("Open"))
            close_price = _safe_float(row.get("Close"))
            high_price = _safe_float(row.get("High"))
            low_price = _safe_float(row.get("Low"))
            if None in (open_price, close_price, high_price, low_price):
                continue
            prices.append(
                Price(
                    open=open_price,
                    close=close_price,
                    high=high_price,
                    low=low_price,
                    volume=_safe_int(row.get("Volume")),
                    time=pd.Timestamp(timestamp).isoformat(),
                )
            )

        if not prices:
            return []

        _cache.set_prices(cache_key, [p.model_dump() for p in prices])
        return prices

    def _statement_frames(self, ticker_obj: Any, period: str) -> dict[str, pd.DataFrame]:
        use_quarterly = period.lower() in {"quarter", "quarterly"}
        frame_attrs = {
            "income": "quarterly_financials" if use_quarterly else "financials",
            "balance": "quarterly_balance_sheet" if use_quarterly else "balance_sheet",
            "cashflow": "quarterly_cashflow" if use_quarterly else "cashflow",
        }
        frames = {}
        for key, attr in frame_attrs.items():
            frame = getattr(ticker_obj, attr, pd.DataFrame())
            if frame is None:
                frame = pd.DataFrame()
            frames[key] = frame
        return frames

    def _statement_periods(self, frames: dict[str, pd.DataFrame], end_date: str, limit: int) -> list[Any]:
        periods: list[Any] = []
        seen = set()
        for frame in frames.values():
            if frame.empty:
                continue
            for column in frame.columns:
                if not _date_lte(column, end_date):
                    continue
                key = _date_str(column)
                if key not in seen:
                    periods.append(column)
                    seen.add(key)
        periods.sort(key=lambda value: pd.Timestamp(value), reverse=True)
        return periods[:limit]

    def _statement_value(self, frames: dict[str, pd.DataFrame], period: Any, line_item: str) -> float | None:
        aliases = LINE_ITEM_ALIASES.get(line_item, [line_item])
        for frame in frames.values():
            if frame.empty or period not in frame.columns:
                continue
            for alias in aliases:
                if alias in frame.index:
                    return _safe_float(frame.loc[alias, period])
        return None

    def _line_item_records(self, ticker: str, end_date: str, period: str, limit: int, requested_items: list[str] | None = None) -> list[dict[str, Any]]:
        ticker_obj = self._ticker(ticker)
        frames = self._statement_frames(ticker_obj, period)
        periods = self._statement_periods(frames, end_date, limit)
        info = self._info(ticker_obj)

        if not periods:
            return []

        requested = requested_items or list(LINE_ITEM_ALIASES.keys())
        records = []
        for report_period in periods:
            row = {
                "ticker": ticker.upper(),
                "report_period": _date_str(report_period),
                "period": period,
                "currency": info.get("currency") or info.get("financialCurrency") or "USD",
            }
            for item in requested:
                value = self._statement_value(frames, report_period, item)
                if value is None and item == "gross_margin":
                    value = _ratio(self._statement_value(frames, report_period, "gross_profit"), self._statement_value(frames, report_period, "revenue"))
                elif value is None and item == "operating_margin":
                    value = _ratio(self._statement_value(frames, report_period, "operating_income"), self._statement_value(frames, report_period, "revenue"))
                elif value is None and item == "book_value_per_share":
                    value = _ratio(self._statement_value(frames, report_period, "shareholders_equity"), self._statement_value(frames, report_period, "outstanding_shares"))
                row[item] = value
            records.append(row)
        return records

    def _info(self, ticker_obj: Any) -> dict:
        try:
            info = ticker_obj.info or {}
        except Exception:
            info = {}
        return info if isinstance(info, dict) else {}

    def _market_cap_from_ticker(self, ticker_obj: Any, info: dict) -> float | None:
        market_cap = info.get("marketCap")
        if market_cap is not None:
            return _safe_float(market_cap)
        try:
            return _safe_float(_get_fast_info_value(ticker_obj.fast_info, "market_cap"))
        except Exception:
            return None

    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
        api_key: str | None = None,
    ) -> list[FinancialMetrics]:
        cache_key = f"{self.name}:{ticker}_{period}_{end_date}_{limit}"
        if cached_data := _cache.get_financial_metrics(cache_key):
            return [FinancialMetrics(**metric) for metric in cached_data]

        try:
            ticker_obj = self._ticker(ticker)
            info = self._info(ticker_obj)
            records = self._line_item_records(ticker, end_date, period, limit)
        except RuntimeError:
            raise
        except Exception:
            return []

        market_cap = self._market_cap_from_ticker(ticker_obj, info)
        enterprise_value = _safe_float(info.get("enterpriseValue"))
        metrics = []

        if not records:
            records = [{"ticker": ticker.upper(), "report_period": end_date, "period": period, "currency": info.get("currency") or "USD"}]

        for index, record in enumerate(records[:limit]):
            previous = records[index + 1] if index + 1 < len(records) else {}
            revenue = record.get("revenue")
            gross_profit = record.get("gross_profit")
            operating_income = record.get("operating_income")
            net_income = record.get("net_income")
            free_cash_flow = record.get("free_cash_flow")
            total_assets = record.get("total_assets")
            total_liabilities = record.get("total_liabilities")
            current_assets = record.get("current_assets")
            current_liabilities = record.get("current_liabilities")
            cash = record.get("cash_and_equivalents")
            debt = record.get("total_debt")
            equity = record.get("shareholders_equity")
            shares = record.get("outstanding_shares")
            ebit = record.get("ebit")
            ebitda = record.get("ebitda")
            interest_expense = record.get("interest_expense")

            metric = FinancialMetrics(
                ticker=ticker.upper(),
                report_period=record["report_period"],
                period=period,
                currency=record.get("currency") or info.get("currency") or "USD",
                market_cap=market_cap,
                enterprise_value=enterprise_value,
                price_to_earnings_ratio=_safe_float(info.get("trailingPE")),
                price_to_book_ratio=_safe_float(info.get("priceToBook")),
                price_to_sales_ratio=_safe_float(info.get("priceToSalesTrailing12Months")),
                enterprise_value_to_ebitda_ratio=_first_not_none(_safe_float(info.get("enterpriseToEbitda")), _ratio(enterprise_value, ebitda)),
                enterprise_value_to_revenue_ratio=_first_not_none(_safe_float(info.get("enterpriseToRevenue")), _ratio(enterprise_value, revenue)),
                free_cash_flow_yield=_ratio(free_cash_flow, market_cap),
                peg_ratio=_safe_float(info.get("pegRatio")),
                gross_margin=_first_not_none(_ratio(gross_profit, revenue), _normalize_yfinance_ratio(info.get("grossMargins"))),
                operating_margin=_first_not_none(_ratio(operating_income, revenue), _normalize_yfinance_ratio(info.get("operatingMargins"))),
                net_margin=_first_not_none(_ratio(net_income, revenue), _normalize_yfinance_ratio(info.get("profitMargins"))),
                return_on_equity=_first_not_none(_ratio(net_income, equity), _normalize_yfinance_ratio(info.get("returnOnEquity"))),
                return_on_assets=_first_not_none(_ratio(net_income, total_assets), _normalize_yfinance_ratio(info.get("returnOnAssets"))),
                return_on_invested_capital=_ratio(operating_income, (debt or 0) + (equity or 0) - (cash or 0)),
                asset_turnover=_ratio(revenue, total_assets),
                inventory_turnover=None,
                receivables_turnover=None,
                days_sales_outstanding=None,
                operating_cycle=None,
                working_capital_turnover=_ratio(revenue, (current_assets or 0) - (current_liabilities or 0)),
                current_ratio=_first_not_none(_ratio(current_assets, current_liabilities), _safe_float(info.get("currentRatio"))),
                quick_ratio=_safe_float(info.get("quickRatio")),
                cash_ratio=_ratio(cash, current_liabilities),
                operating_cash_flow_ratio=_ratio(record.get("operating_cash_flow"), current_liabilities),
                debt_to_equity=_first_not_none(_ratio(debt, equity), _normalize_yfinance_ratio(info.get("debtToEquity"))),
                debt_to_assets=_ratio(debt, total_assets),
                interest_coverage=_ratio(ebit, abs(interest_expense)) if interest_expense else None,
                revenue_growth=_first_not_none(_growth(revenue, previous.get("revenue")), _normalize_yfinance_ratio(info.get("revenueGrowth"))),
                earnings_growth=_first_not_none(_growth(net_income, previous.get("net_income")), _normalize_yfinance_ratio(info.get("earningsGrowth"))),
                book_value_growth=_growth(equity, previous.get("shareholders_equity")),
                earnings_per_share_growth=_growth(record.get("earnings_per_share"), previous.get("earnings_per_share")),
                free_cash_flow_growth=_growth(free_cash_flow, previous.get("free_cash_flow")),
                operating_income_growth=_growth(operating_income, previous.get("operating_income")),
                ebitda_growth=_growth(ebitda, previous.get("ebitda")),
                payout_ratio=_normalize_yfinance_ratio(info.get("payoutRatio")),
                earnings_per_share=_first_not_none(record.get("earnings_per_share"), _safe_float(info.get("trailingEps"))),
                book_value_per_share=_first_not_none(record.get("book_value_per_share"), _ratio(equity, shares), _safe_float(info.get("bookValue"))),
                free_cash_flow_per_share=_ratio(free_cash_flow, shares),
            )
            metrics.append(metric)

        _cache.set_financial_metrics(cache_key, [m.model_dump() for m in metrics])
        return metrics

    def search_line_items(
        self,
        ticker: str,
        line_items: list[str],
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
        api_key: str | None = None,
    ) -> list[LineItem]:
        cache_key = f"{self.name}:line_items:{ticker}_{','.join(line_items)}_{period}_{end_date}_{limit}"
        if cached_data := _cache.get_line_items(cache_key):
            return [LineItem(**item) for item in cached_data]

        try:
            records = self._line_item_records(ticker, end_date, period, limit, requested_items=line_items)
        except RuntimeError:
            raise
        except Exception:
            return []

        line_item_results = [LineItem(**record) for record in records]
        if line_item_results:
            _cache.set_line_items(cache_key, [item.model_dump() for item in line_item_results])
        return line_item_results

    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
        api_key: str | None = None,
    ) -> list[InsiderTrade]:
        cache_key = f"{self.name}:{ticker}_{start_date or 'none'}_{end_date}_{limit}"
        if cached_data := _cache.get_insider_trades(cache_key):
            return [InsiderTrade(**trade) for trade in cached_data]

        try:
            trades_df = self._ticker(ticker).insider_transactions
        except RuntimeError:
            raise
        except Exception:
            return []

        if trades_df is None or trades_df.empty:
            return []

        trades: list[InsiderTrade] = []
        start = _to_datetime(start_date)
        end = _to_datetime(end_date)
        for _, row in trades_df.head(limit).iterrows():
            raw_date = row.get("Start Date") or row.get("Date") or row.get("Filing Date") or end_date
            trade_date = _to_datetime(_date_str(raw_date))
            if start and trade_date and trade_date.date() < start.date():
                continue
            if end and trade_date and trade_date.date() > end.date():
                continue

            shares = _safe_float(row.get("Shares"))
            value = _safe_float(row.get("Value"))
            price_per_share = _ratio(value, abs(shares)) if shares else None
            filing_date = _date_str(raw_date)

            trades.append(
                InsiderTrade(
                    ticker=ticker.upper(),
                    issuer=None,
                    name=row.get("Insider"),
                    title=row.get("Position"),
                    is_board_director=None,
                    transaction_date=filing_date,
                    transaction_shares=shares,
                    transaction_price_per_share=price_per_share,
                    transaction_value=value,
                    shares_owned_before_transaction=None,
                    shares_owned_after_transaction=None,
                    security_title=row.get("Transaction") or row.get("Text"),
                    filing_date=filing_date,
                )
            )

        if not trades:
            return []

        _cache.set_insider_trades(cache_key, [trade.model_dump() for trade in trades])
        return trades

    def _news_date(self, item: dict) -> str:
        content = item.get("content") or {}
        pub_date = content.get("pubDate")
        if pub_date:
            return str(pub_date)
        provider_time = item.get("providerPublishTime")
        if provider_time:
            return datetime.datetime.fromtimestamp(provider_time).isoformat()
        return datetime.datetime.now().isoformat()

    def get_company_news(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
        api_key: str | None = None,
    ) -> list[CompanyNews]:
        cache_key = f"{self.name}:{ticker}_{start_date or 'none'}_{end_date}_{limit}"
        if cached_data := _cache.get_company_news(cache_key):
            return [CompanyNews(**news) for news in cached_data]

        try:
            items = self._ticker(ticker).news or []
        except RuntimeError:
            raise
        except Exception:
            return []

        start = _to_datetime(start_date)
        end = _to_datetime(end_date)
        news: list[CompanyNews] = []
        for item in items:
            content = item.get("content") or {}
            provider = content.get("provider") or {}
            canonical_url = content.get("canonicalUrl") or {}
            date = self._news_date(item)
            parsed_date = _to_datetime(date)
            if start and parsed_date and parsed_date.date() < start.date():
                continue
            if end and parsed_date and parsed_date.date() > end.date():
                continue

            news.append(
                CompanyNews(
                    ticker=ticker.upper(),
                    title=content.get("title") or item.get("title") or "",
                    author=provider.get("displayName") or item.get("publisher") or "",
                    source=provider.get("displayName") or item.get("publisher") or "",
                    date=date,
                    url=canonical_url.get("url") or item.get("link") or "",
                    sentiment=None,
                )
            )
            if len(news) >= limit:
                break

        if news:
            _cache.set_company_news(cache_key, [item.model_dump() for item in news])
        return news

    def get_market_cap(self, ticker: str, end_date: str, api_key: str | None = None) -> float | None:
        try:
            ticker_obj = self._ticker(ticker)
            return self._market_cap_from_ticker(ticker_obj, self._info(ticker_obj))
        except RuntimeError:
            raise
        except Exception:
            return None
