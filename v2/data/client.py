"""yfinance-backed implementation of the DataClient protocol.

Class name kept as FDClient for backward compatibility with all existing imports.
Insider trades are sourced from SEC EDGAR Form 4 filings (free, no key).
Earnings estimates / surprise flags are always None (not in yfinance statements).
"""

from __future__ import annotations

import datetime
import logging
import math
import time
import xml.etree.ElementTree as ET

import pandas as pd
import requests
import yfinance as yf

from v2.data.models import (
    CompanyFacts,
    CompanyNews,
    Earnings,
    EarningsData,
    EarningsRecord,
    FinancialMetrics,
    InsiderTrade,
    Price,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level helpers (mirrors src/tools/api.py — kept independent of src)
# ---------------------------------------------------------------------------

def _safe(val) -> float | None:
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _div(a, b) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return _safe(a / b)


def _growth(current, previous) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return _safe((current - previous) / abs(previous))


def _stmt_val(df: pd.DataFrame, col, *row_names: str) -> float | None:
    if df is None or df.empty or col is None or col not in df.columns:
        return None
    for row in row_names:
        try:
            if row in df.index:
                v = df.loc[row, col]
                if v is not None and pd.notna(v):
                    return float(v)
        except Exception:
            continue
    return None


def _nearest_col(df: pd.DataFrame, target):
    if df is None or df.empty or target is None:
        return None
    if target in df.columns:
        return target
    target_ts = pd.Timestamp(target)
    diffs = {c: abs((pd.Timestamp(c) - target_ts).days) for c in df.columns}
    nearest = min(diffs, key=diffs.get)
    return nearest if diffs[nearest] <= 45 else None


_EDGAR_HEADERS = {"User-Agent": "ai-hedge-fund research@example.com"}
_CIK_CACHE: dict[str, str] = {}


def _get_cik(ticker: str) -> str | None:
    if ticker in _CIK_CACHE:
        return _CIK_CACHE[ticker]
    try:
        resp = requests.get("https://www.sec.gov/files/company_tickers.json", headers=_EDGAR_HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        upper = ticker.upper()
        for entry in resp.json().values():
            if entry.get("ticker", "").upper() == upper:
                cik = str(entry["cik_str"]).zfill(10)
                _CIK_CACHE[ticker] = cik
                return cik
    except Exception as e:
        logger.warning("CIK lookup failed for %s: %s", ticker, e)
    return None


def _build_earnings_data(inc: pd.DataFrame, bal: pd.DataFrame, cf: pd.DataFrame, col) -> EarningsData:
    """Assemble an EarningsData from one period column across three statement DataFrames."""
    bal_col = _nearest_col(bal, col)
    cf_col  = _nearest_col(cf, col)

    ocf   = _stmt_val(cf, cf_col, "Operating Cash Flow")
    capex = _stmt_val(cf, cf_col, "Capital Expenditure")
    fcf   = (ocf + capex) if (ocf and capex) else _stmt_val(cf, cf_col, "Free Cash Flow")

    return EarningsData(
        revenue=_stmt_val(inc, col, "Total Revenue"),
        estimated_revenue=None,
        revenue_surprise=None,
        earnings_per_share=_stmt_val(inc, col, "Basic EPS", "Diluted EPS"),
        estimated_earnings_per_share=None,
        eps_surprise=None,
        net_income=_stmt_val(inc, col, "Net Income"),
        gross_profit=_stmt_val(inc, col, "Gross Profit"),
        operating_income=_stmt_val(inc, col, "Operating Income", "EBIT"),
        weighted_average_shares=_stmt_val(bal, bal_col, "Share Issued", "Ordinary Shares Number"),
        weighted_average_shares_diluted=_stmt_val(inc, col, "Diluted Average Shares"),
        free_cash_flow=fcf,
        cash_and_equivalents=_stmt_val(bal, bal_col, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"),
        total_debt=_stmt_val(bal, bal_col, "Total Debt"),
        total_assets=_stmt_val(bal, bal_col, "Total Assets"),
        total_liabilities=_stmt_val(bal, bal_col, "Total Liabilities Net Minority Interest"),
        shareholders_equity=_stmt_val(bal, bal_col, "Stockholders Equity", "Common Stock Equity"),
        net_cash_flow_from_operations=ocf,
        capital_expenditure=capex,
        net_cash_flow_from_investing=_stmt_val(cf, cf_col, "Investing Cash Flow"),
        net_cash_flow_from_financing=_stmt_val(cf, cf_col, "Financing Cash Flow"),
        change_in_cash_and_equivalents=_stmt_val(cf, cf_col, "Changes In Cash"),
    )


# ---------------------------------------------------------------------------
# FDClient
# ---------------------------------------------------------------------------

class FDClient:
    """yfinance-backed data client satisfying the DataClient protocol.

    Usage::

        with FDClient() as fd:
            prices = fd.get_prices("AAPL", "2024-01-01", "2024-12-31")

    The api_key / timeout constructor arguments are accepted but ignored —
    yfinance requires no authentication.
    """

    def __init__(self, api_key: str | None = None, timeout: float = 30.0) -> None:
        pass  # api_key kept for drop-in compatibility

    def __enter__(self) -> FDClient:
        return self

    def __exit__(self, *args) -> None:
        pass

    def close(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Prices
    # ------------------------------------------------------------------

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        interval: str = "day",
        interval_multiplier: int = 1,
    ) -> list[Price]:
        """Fetch OHLCV bars from yfinance (daily bars only)."""
        try:
            hist = yf.Ticker(ticker).history(start=start_date, end=end_date, interval="1d", auto_adjust=True)
        except Exception as e:
            logger.warning("yfinance price fetch failed for %s: %s", ticker, e)
            return []

        if hist is None or hist.empty:
            return []

        return [
            Price(
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
                time=dt.isoformat(),
            )
            for dt, row in hist.iterrows()
        ]

    # ------------------------------------------------------------------
    # Financial Metrics
    # ------------------------------------------------------------------

    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
    ) -> list[FinancialMetrics]:
        """Fetch financial metrics from yfinance.

        period='ttm'       → current snapshot from Ticker.info
        period='annual'    → computed from annual income/balance/cashflow stmts
        period='quarterly' → computed from quarterly statements
        """
        end_dt = datetime.date.fromisoformat(end_date)

        if period == "ttm":
            return self._metrics_from_info(ticker, end_date)

        try:
            yf_ticker = yf.Ticker(ticker)
            if period == "quarterly":
                inc = yf_ticker.quarterly_income_stmt
                bal = yf_ticker.quarterly_balance_sheet
                cf  = yf_ticker.quarterly_cash_flow
                plabel = "quarterly"
            else:
                inc = yf_ticker.income_stmt
                bal = yf_ticker.balance_sheet
                cf  = yf_ticker.cash_flow
                plabel = "annual"
        except Exception as e:
            logger.warning("yfinance statements failed for %s: %s", ticker, e)
            return []

        if inc is None or inc.empty:
            return []

        price_hist = self.get_prices(ticker, "2010-01-01", end_date)
        price_df   = self._to_price_df(price_hist) if price_hist else pd.DataFrame()

        def _price_near(dt) -> float | None:
            if price_df.empty:
                return None
            try:
                idx = price_df.index.get_indexer([pd.Timestamp(dt)], method="nearest")[0]
                return float(price_df.iloc[idx]["close"])
            except Exception:
                return None

        cols     = sorted(inc.columns, reverse=True)
        in_range = [c for c in cols if c.date() <= end_dt]
        extra    = cols[len(in_range)] if len(in_range) < len(cols) else None

        metrics: list[FinancialMetrics] = []
        for i, col in enumerate(in_range[:limit]):
            prev_col = in_range[i + 1] if i + 1 < len(in_range) else extra

            # Build as dict so we can add growth fields before constructing the model
            d = self._metrics_dict_from_stmts(ticker, col, plabel, inc, bal, cf, _price_near(col.date()))

            if prev_col is not None:
                d["revenue_growth"]            = _growth(_stmt_val(inc, col, "Total Revenue"),             _stmt_val(inc, prev_col, "Total Revenue"))
                d["earnings_growth"]           = _growth(_stmt_val(inc, col, "Net Income"),                _stmt_val(inc, prev_col, "Net Income"))
                d["operating_income_growth"]   = _growth(_stmt_val(inc, col, "Operating Income", "EBIT"),  _stmt_val(inc, prev_col, "Operating Income", "EBIT"))
                d["ebitda_growth"]             = _growth(_stmt_val(inc, col, "EBITDA"),                    _stmt_val(inc, prev_col, "EBITDA"))
                d["earnings_per_share_growth"] = _growth(_stmt_val(inc, col, "Basic EPS", "Diluted EPS"),  _stmt_val(inc, prev_col, "Basic EPS", "Diluted EPS"))
                d["book_value_growth"]         = _growth(
                    _stmt_val(bal, _nearest_col(bal, col),      "Stockholders Equity", "Common Stock Equity"),
                    _stmt_val(bal, _nearest_col(bal, prev_col), "Stockholders Equity", "Common Stock Equity"),
                )
                cf_c = _nearest_col(cf, col);      cf_p = _nearest_col(cf, prev_col)
                ocf_c = _stmt_val(cf, cf_c, "Operating Cash Flow"); cap_c = _stmt_val(cf, cf_c, "Capital Expenditure")
                ocf_p = _stmt_val(cf, cf_p, "Operating Cash Flow"); cap_p = _stmt_val(cf, cf_p, "Capital Expenditure")
                fcf_c = (ocf_c + cap_c) if (ocf_c and cap_c) else _stmt_val(cf, cf_c, "Free Cash Flow")
                fcf_p = (ocf_p + cap_p) if (ocf_p and cap_p) else _stmt_val(cf, cf_p, "Free Cash Flow")
                d["free_cash_flow_growth"]     = _growth(fcf_c, fcf_p)

            metrics.append(FinancialMetrics(**d))

        return metrics

    def _metrics_from_info(self, ticker: str, end_date: str) -> list[FinancialMetrics]:
        try:
            info = yf.Ticker(ticker).info
        except Exception as e:
            logger.warning("yfinance .info failed for %s: %s", ticker, e)
            return []

        shares     = _safe(info.get("sharesOutstanding"))
        market_cap = _safe(info.get("marketCap"))
        fcf        = _safe(info.get("freeCashflow"))
        raw_de     = _safe(info.get("debtToEquity"))

        return [FinancialMetrics(
            ticker=ticker, report_period=end_date, period="ttm",
            currency=info.get("currency"),
            market_cap=market_cap,
            enterprise_value=_safe(info.get("enterpriseValue")),
            price_to_earnings_ratio=_safe(info.get("trailingPE")),
            price_to_book_ratio=_safe(info.get("priceToBook")),
            price_to_sales_ratio=_safe(info.get("priceToSalesTrailing12Months")),
            enterprise_value_to_ebitda_ratio=_safe(info.get("enterpriseToEbitda")),
            enterprise_value_to_revenue_ratio=_safe(info.get("enterpriseToRevenue")),
            free_cash_flow_yield=_div(fcf, market_cap),
            peg_ratio=_safe(info.get("pegRatio")),
            gross_margin=_safe(info.get("grossMargins")),
            operating_margin=_safe(info.get("operatingMargins")),
            net_margin=_safe(info.get("profitMargins")),
            return_on_equity=_safe(info.get("returnOnEquity")),
            return_on_assets=_safe(info.get("returnOnAssets")),
            return_on_invested_capital=None,
            asset_turnover=None, inventory_turnover=None, receivables_turnover=None,
            days_sales_outstanding=None, operating_cycle=None, working_capital_turnover=None,
            current_ratio=_safe(info.get("currentRatio")),
            quick_ratio=_safe(info.get("quickRatio")),
            cash_ratio=None, operating_cash_flow_ratio=None,
            debt_to_equity=_div(raw_de, 100.0) if raw_de is not None else None,
            debt_to_assets=None, interest_coverage=None,
            revenue_growth=_safe(info.get("revenueGrowth")),
            earnings_growth=_safe(info.get("earningsGrowth")),
            book_value_growth=None, earnings_per_share_growth=None,
            free_cash_flow_growth=None, operating_income_growth=None, ebitda_growth=None,
            payout_ratio=_safe(info.get("payoutRatio")),
            earnings_per_share=_safe(info.get("trailingEps")),
            book_value_per_share=_safe(info.get("bookValue")),
            free_cash_flow_per_share=_div(fcf, shares),
        )]

    def _metrics_dict_from_stmts(
        self,
        ticker: str,
        col,
        period_label: str,
        inc: pd.DataFrame,
        bal: pd.DataFrame,
        cf: pd.DataFrame,
        price: float | None,
    ) -> dict:
        """Return a plain dict with all FinancialMetrics fields computed from statements."""
        report_period = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)[:10]
        bal_col = _nearest_col(bal, col)
        cf_col  = _nearest_col(cf, col)

        revenue          = _stmt_val(inc, col,     "Total Revenue")
        gross_profit     = _stmt_val(inc, col,     "Gross Profit")
        operating_income = _stmt_val(inc, col,     "Operating Income", "EBIT")
        net_income       = _stmt_val(inc, col,     "Net Income")
        ebitda           = _stmt_val(inc, col,     "EBITDA")
        interest_expense = _stmt_val(inc, col,     "Interest Expense")
        eps              = _stmt_val(inc, col,     "Basic EPS", "Diluted EPS")

        total_assets   = _stmt_val(bal, bal_col, "Total Assets")
        current_assets = _stmt_val(bal, bal_col, "Current Assets")
        current_liab   = _stmt_val(bal, bal_col, "Current Liabilities")
        total_debt     = _stmt_val(bal, bal_col, "Total Debt")
        equity         = _stmt_val(bal, bal_col, "Stockholders Equity", "Common Stock Equity")
        cash           = _stmt_val(bal, bal_col, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")
        inventory      = _stmt_val(bal, bal_col, "Inventory")
        receivables    = _stmt_val(bal, bal_col, "Accounts Receivable")
        shares         = _stmt_val(bal, bal_col, "Share Issued", "Ordinary Shares Number")

        operating_cf = _stmt_val(cf, cf_col, "Operating Cash Flow")
        capex        = _stmt_val(cf, cf_col, "Capital Expenditure")
        fcf = (operating_cf + capex) if (operating_cf and capex) else _stmt_val(cf, cf_col, "Free Cash Flow")

        market_cap = (price * shares) if (price and shares) else None
        net_debt   = (total_debt or 0) - (cash or 0) if total_debt is not None else None
        ev         = (market_cap + net_debt) if (market_cap is not None and net_debt is not None) else None

        ie        = -interest_expense if (interest_expense is not None and interest_expense < 0) else interest_expense
        wc        = (current_assets - current_liab) if (current_assets is not None and current_liab is not None) else None
        ic        = (total_debt + equity) if (total_debt is not None and equity is not None) else None
        quick_num = (current_assets - inventory) if (current_assets is not None and inventory is not None) else current_assets

        return dict(
            ticker=ticker, report_period=report_period, period=period_label, currency=None,
            market_cap=market_cap, enterprise_value=ev,
            price_to_earnings_ratio=_div(market_cap, net_income),
            price_to_book_ratio=_div(market_cap, equity),
            price_to_sales_ratio=_div(market_cap, revenue),
            enterprise_value_to_ebitda_ratio=_div(ev, ebitda),
            enterprise_value_to_revenue_ratio=_div(ev, revenue),
            free_cash_flow_yield=_div(fcf, market_cap),
            peg_ratio=None,
            gross_margin=_div(gross_profit, revenue),
            operating_margin=_div(operating_income, revenue),
            net_margin=_div(net_income, revenue),
            return_on_equity=_div(net_income, equity),
            return_on_assets=_div(net_income, total_assets),
            return_on_invested_capital=_div(operating_income, ic),
            asset_turnover=_div(revenue, total_assets),
            inventory_turnover=_div(revenue, inventory),
            receivables_turnover=_div(revenue, receivables),
            days_sales_outstanding=_div(365.0, _div(revenue, receivables)),
            operating_cycle=None,
            working_capital_turnover=_div(revenue, wc),
            current_ratio=_div(current_assets, current_liab),
            quick_ratio=_div(quick_num, current_liab),
            cash_ratio=_div(cash, current_liab),
            operating_cash_flow_ratio=_div(operating_cf, current_liab),
            debt_to_equity=_div(total_debt, equity),
            debt_to_assets=_div(total_debt, total_assets),
            interest_coverage=_div(operating_income, ie),
            revenue_growth=None, earnings_growth=None, book_value_growth=None,
            earnings_per_share_growth=None, free_cash_flow_growth=None,
            operating_income_growth=None, ebitda_growth=None,
            payout_ratio=None,
            earnings_per_share=eps,
            book_value_per_share=_div(equity, shares),
            free_cash_flow_per_share=_div(fcf, shares),
        )

    # ------------------------------------------------------------------
    # News
    # ------------------------------------------------------------------

    def get_news(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
    ) -> list[CompanyNews]:
        """Fetch company news from yfinance. Sentiment is always None."""
        try:
            raw_news = yf.Ticker(ticker).news
        except Exception as e:
            logger.warning("yfinance news fetch failed for %s: %s", ticker, e)
            return []

        if not raw_news:
            return []

        articles: list[CompanyNews] = []
        for item in raw_news:
            pub_ts = item.get("providerPublishTime")
            if not pub_ts:
                continue
            dt = datetime.datetime.fromtimestamp(pub_ts, tz=datetime.timezone.utc)
            date_only = dt.date().isoformat()
            if date_only > end_date:
                continue
            if start_date and date_only < start_date:
                continue
            articles.append(CompanyNews(
                ticker=ticker,
                title=item.get("title", ""),
                source=item.get("publisher", ""),
                date=dt.isoformat(),
                url=item.get("link"),
            ))

        return articles[:limit]

    # ------------------------------------------------------------------
    # Insider Trades — SEC EDGAR Form 4
    # ------------------------------------------------------------------

    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
    ) -> list[InsiderTrade]:
        """Fetch insider trades from SEC EDGAR Form 4 filings (free, no key)."""
        cik = _get_cik(ticker)
        if not cik:
            logger.warning("No CIK found for %s; returning empty insider trades", ticker)
            return []

        try:
            resp = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=_EDGAR_HEADERS, timeout=15)
            if resp.status_code != 200:
                return []
            recent = resp.json().get("filings", {}).get("recent", {})
        except Exception as e:
            logger.warning("EDGAR submissions fetch failed for %s: %s", ticker, e)
            return []

        form_types   = recent.get("form", [])
        filing_dates = recent.get("filingDate", [])
        accessions   = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])

        all_trades: list[InsiderTrade] = []
        for i, form_type in enumerate(form_types):
            if len(all_trades) >= limit:
                break
            if form_type not in ("4", "4/A"):
                continue
            fd = filing_dates[i]
            if fd > end_date:
                continue
            if start_date and fd < start_date:
                continue

            acc_nodash  = accessions[i].replace("-", "")
            primary_doc = primary_docs[i] if i < len(primary_docs) else "form4.xml"
            xml_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_nodash}/{primary_doc}"

            try:
                xml_resp = requests.get(xml_url, headers=_EDGAR_HEADERS, timeout=10)
                if xml_resp.status_code != 200:
                    continue
            except Exception:
                continue

            all_trades.extend(self._parse_form4(xml_resp.content, ticker, fd))
            time.sleep(0.15)

        return all_trades[:limit]

    def _parse_form4(self, content: bytes, ticker: str, filing_date: str) -> list[InsiderTrade]:
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            return []

        def _text(*tags: str) -> str | None:
            for tag in tags:
                node = root.find(f".//{tag}")
                if node is not None and node.text:
                    return node.text.strip()
            return None

        name     = _text("rptOwnerName") or ""
        issuer   = _text("issuerName")
        title    = _text("officerTitle")
        is_board = _text("isDirector") == "1"

        trades: list[InsiderTrade] = []
        for tx in root.findall(".//nonDerivativeTransaction"):
            def _tx(tag: str) -> str | None:
                node = tx.find(f".//{tag}")
                return node.text.strip() if node is not None and node.text else None

            acquired_code = _tx("transactionAcquiredDisposedCode")

            try:
                raw = _tx("transactionShares")
                shares = float(raw) if raw else None
                if shares and acquired_code == "D":
                    shares = -shares
            except (TypeError, ValueError):
                shares = None
            try:
                raw = _tx("transactionPricePerShare")
                price = float(raw) if raw else None
            except (TypeError, ValueError):
                price = None
            try:
                raw = _tx("sharesOwnedFollowingTransaction")
                shares_after = float(raw) if raw else None
            except (TypeError, ValueError):
                shares_after = None

            value = (abs(shares) * price) if (shares and price) else None
            if acquired_code == "D" and value:
                value = -value

            trades.append(InsiderTrade(
                ticker=ticker,
                name=name,
                filing_date=filing_date,
                is_board_director=is_board,
                issuer=issuer,
                title=title,
                transaction_date=_tx("transactionDate"),
                transaction_shares=shares,
                transaction_price_per_share=price,
                transaction_value=value,
                shares_owned_before_transaction=None,
                shares_owned_after_transaction=shares_after,
                security_title=_tx("securityTitle"),
            ))
        return trades

    # ------------------------------------------------------------------
    # Company Facts
    # ------------------------------------------------------------------

    def get_company_facts(self, ticker: str) -> CompanyFacts | None:
        """Fetch company metadata from yfinance Ticker.info."""
        try:
            info = yf.Ticker(ticker).info
            return CompanyFacts(
                ticker=ticker,
                name=info.get("longName") or info.get("shortName"),
                sector=info.get("sector"),
                industry=info.get("industry"),
                exchange=info.get("exchange"),
                location=info.get("country"),
                is_active=True,
            )
        except Exception as e:
            logger.warning("yfinance company facts failed for %s: %s", ticker, e)
            return None

    # ------------------------------------------------------------------
    # Earnings
    # ------------------------------------------------------------------

    def get_earnings(self, ticker: str) -> Earnings | None:
        """Fetch the most recent quarter's earnings from yfinance statements."""
        try:
            yf_ticker = yf.Ticker(ticker)
            q_inc = yf_ticker.quarterly_income_stmt
            q_bal = yf_ticker.quarterly_balance_sheet
            q_cf  = yf_ticker.quarterly_cash_flow
        except Exception as e:
            logger.warning("yfinance quarterly stmts failed for %s: %s", ticker, e)
            return None

        if q_inc is None or q_inc.empty:
            return None

        col       = q_inc.columns[0]
        quarterly = _build_earnings_data(q_inc, q_bal, q_cf, col)

        annual: EarningsData | None = None
        try:
            a_inc = yf_ticker.income_stmt
            a_bal = yf_ticker.balance_sheet
            a_cf  = yf_ticker.cash_flow
            if a_inc is not None and not a_inc.empty:
                annual = _build_earnings_data(a_inc, a_bal, a_cf, a_inc.columns[0])
        except Exception:
            pass

        return Earnings(
            ticker=ticker,
            report_period=col.strftime("%Y-%m-%d"),
            fiscal_period=f"Q{col.quarter}",
            currency="USD",
            quarterly=quarterly,
            annual=annual,
        )

    def get_earnings_history(self, ticker: str, limit: int = 12) -> list[EarningsRecord]:
        """Fetch historical quarterly earnings as a flat list."""
        try:
            yf_ticker = yf.Ticker(ticker)
            q_inc = yf_ticker.quarterly_income_stmt
            q_bal = yf_ticker.quarterly_balance_sheet
            q_cf  = yf_ticker.quarterly_cash_flow
        except Exception as e:
            logger.warning("yfinance quarterly stmts failed for %s: %s", ticker, e)
            return []

        if q_inc is None or q_inc.empty:
            return []

        records: list[EarningsRecord] = []
        for col in list(q_inc.columns)[:limit]:
            records.append(EarningsRecord(
                ticker=ticker,
                report_period=col.strftime("%Y-%m-%d"),
                source_type="10-Q",
                fiscal_period=f"Q{col.quarter}",
                currency="USD",
                quarterly=_build_earnings_data(q_inc, q_bal, q_cf, col),
            ))
        return records

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def get_market_cap(self, ticker: str, end_date: str) -> float | None:
        """Return market cap from Ticker.info, or price × shares as fallback."""
        try:
            info = yf.Ticker(ticker).info
            if mc := _safe(info.get("marketCap")):
                return mc
            shares = _safe(info.get("sharesOutstanding"))
            if shares:
                prices = self.get_prices(ticker, end_date, end_date)
                if not prices:
                    prev = (datetime.date.fromisoformat(end_date) - datetime.timedelta(days=5)).isoformat()
                    prices = self.get_prices(ticker, prev, end_date)
                if prices:
                    return prices[-1].close * shares
        except Exception as e:
            logger.warning("Market cap fetch failed for %s: %s", ticker, e)
        return None

    # ------------------------------------------------------------------
    # Private utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _to_price_df(prices: list[Price]) -> pd.DataFrame:
        rows = [{"time": p.time, "open": p.open, "close": p.close, "high": p.high, "low": p.low, "volume": p.volume} for p in prices]
        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["time"])
        df.set_index("Date", inplace=True)
        for col in ["open", "close", "high", "low", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df.sort_index(inplace=True)
        return df
