"""Tushare data provider for A-share stocks.

Drop-in replacement for src/tools/api.py. Returns the same Pydantic models
so all agents work without modification.

Set environment variable DATA_SOURCE=tushare and TUSHARE_TOKEN=<your_token>
to activate.
"""

from __future__ import annotations

import datetime
import logging
import math
import os

import pandas as pd
import tushare as ts

from src.data.cache import get_cache
from src.data.models import (
    CompanyNews,
    FinancialMetrics,
    InsiderTrade,
    LineItem,
    Price,
)

logger = logging.getLogger(__name__)

_cache = get_cache()
_pro = None


def _safe_fetch(pro, api_name: str, **kwargs):
    """Fetch data from Tushare API with error handling."""
    try:
        fn = getattr(pro, api_name)
        return fn(**kwargs)
    except Exception as e:
        logger.warning("Tushare %s failed: %s", api_name, e)
        return None


def _get_pro_api():
    global _pro
    if _pro is None:
        token = os.environ.get("TUSHARE_TOKEN")
        if not token:
            raise ValueError("TUSHARE_TOKEN environment variable is required")
        ts.set_token(token)
        _pro = ts.pro_api()
    return _pro


def _fmt(date_str: str) -> str:
    """YYYY-MM-DD → YYYYMMDD"""
    return date_str.replace("-", "")


def _parse(date_str: str) -> str:
    """YYYYMMDD → YYYY-MM-DD"""
    s = str(date_str)
    if len(s) == 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s


def _safe_float(val, default=None):
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return default
    try:
        if isinstance(val, pd.Timestamp):
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val, default=0):
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return default
    try:
        if isinstance(val, pd.Timestamp):
            return default
        return int(val)
    except (ValueError, TypeError):
        return default


# ── Mapping: English line item name → (tushare_api, field_name) ──────────

LINE_ITEM_MAP: dict[str, tuple[str, str]] = {
    # Income
    "revenue": ("income", "total_revenue"),
    "net_income": ("income", "n_income_attr_p"),
    "operating_income": ("income", "operate_profit"),
    "operating_expense": ("income", "oper_cost"),
    "gross_profit": ("income", "_calc_gross_profit"),
    "ebit": ("income", "ebit"),
    "ebitda": ("income", "ebitda"),
    "interest_expense": ("income", "fin_exp"),
    "research_and_development": ("income", "rd_exp"),
    "earnings_per_share": ("income", "basic_eps"),
    # Balance sheet
    "total_assets": ("balancesheet", "total_assets"),
    "total_liabilities": ("balancesheet", "total_liab"),
    "current_assets": ("balancesheet", "total_cur_assets"),
    "current_liabilities": ("balancesheet", "total_cur_liab"),
    "cash_and_equivalents": ("balancesheet", "money_cap"),
    "shareholders_equity": ("balancesheet", "total_hldr_eqy_exc_min_int"),
    "total_debt": ("balancesheet", "_calc_total_debt"),
    "goodwill_and_intangible_assets": ("balancesheet", "_calc_gw_intan"),
    "intangible_assets": ("balancesheet", "intan_assets"),
    "outstanding_shares": ("balancesheet", "total_share"),
    "book_value_per_share": ("balancesheet", "_calc_bps"),
    "working_capital": ("balancesheet", "_calc_working_capital"),
    # Cash flow
    "depreciation_and_amortization": ("cashflow", "depr_fa_coga_dpba"),
    "capital_expenditure": ("cashflow", "c_pay_acq_const_fiolta"),
    "free_cash_flow": ("cashflow", "free_cashflow"),
    "dividends_and_other_cash_distributions": ("cashflow", "c_pay_dist_dpcp_int_exp"),
    "issuance_or_purchase_of_equity_shares": ("cashflow", "_calc_equity_flow"),
    # Calculated (from any available data)
    "gross_margin": ("income", "_calc_gross_margin"),
    "operating_margin": ("income", "_calc_oper_margin"),
    "debt_to_equity": ("balancesheet", "_calc_dte"),
    "return_on_invested_capital": ("income", "_calc_roic"),
}


def _calc_field(name: str, row: dict):
    """Compute calculated fields from a flat dict of raw data."""
    match name:
        case "_calc_gross_profit":
            rev = _safe_float(row.get("total_revenue"))
            cost = _safe_float(row.get("oper_cost"))
            if rev is not None and cost is not None:
                return rev - cost
            return None
        case "_calc_total_debt":
            st = _safe_float(row.get("st_borr")) or 0
            lt = _safe_float(row.get("lt_borr")) or 0
            bond = _safe_float(row.get("bond_payable")) or 0
            return st + lt + bond
        case "_calc_gw_intan":
            gw = _safe_float(row.get("goodwill")) or 0
            ia = _safe_float(row.get("intan_assets")) or 0
            return gw + ia
        case "_calc_bps":
            equity = _safe_float(row.get("total_hldr_eqy_exc_min_int"))
            shares = _safe_float(row.get("total_share"))
            if equity and shares and shares > 0:
                return equity / shares
            return None
        case "_calc_working_capital":
            ca = _safe_float(row.get("total_cur_assets")) or 0
            cl = _safe_float(row.get("total_cur_liab")) or 0
            return ca - cl
        case "_calc_equity_flow":
            abs_net = _safe_float(row.get("cash_add_cp_imp_fin_pro"))
            if abs_net is not None:
                return -abs_net
            return None
        case "_calc_gross_margin":
            rev = _safe_float(row.get("total_revenue"))
            cost = _safe_float(row.get("oper_cost"))
            if rev and cost and rev > 0:
                return (rev - cost) / rev
            return None
        case "_calc_oper_margin":
            rev = _safe_float(row.get("total_revenue"))
            op = _safe_float(row.get("operate_profit"))
            if rev and op and rev > 0:
                return op / rev
            return None
        case "_calc_dte":
            total_liab = _safe_float(row.get("total_liab"))
            equity = _safe_float(row.get("total_hldr_eqy_exc_min_int"))
            if total_liab and equity and equity > 0:
                return total_liab / equity
            return None
        case "_calc_roic":
            n_income = _safe_float(row.get("n_income_attr_p"))
            total_assets = _safe_float(row.get("total_assets"))
            total_liab = _safe_float(row.get("total_liab"))
            if n_income and total_assets and total_liab:
                invested = total_assets - total_liab
                if invested > 0:
                    return n_income / invested
            return None
        case _:
            return None


def _merge_dfs(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    """Merge multiple DataFrames by ts_code + end_date, prefixing non-key columns."""
    tagged = []
    for tag, df in dfs:
        if df is not None and not df.empty:
            df = df.rename(columns=lambda c: f"{tag}__{c}" if c not in ("ts_code", "end_date") else c)
            tagged.append(df)
    if not tagged:
        return pd.DataFrame()

    merged = tagged[0]
    for df in tagged[1:]:
        merged = merged.merge(df, on=["ts_code", "end_date"], how="outer", suffixes=("", "_dup"))
        merged = merged[[c for c in merged.columns if not c.endswith("_dup")]]
    return merged.sort_values("end_date", ascending=False)


def _flatten_row(row) -> dict:
    """Build a flat dict from a merged row, stripping tag prefixes."""
    flat = {}
    for col in row.index:
        if "__" in col:
            flat[col.split("__", 1)[1]] = row[col]
        else:
            flat[col] = row[col]
    return flat


def _calc_growth_rates(merged: pd.DataFrame) -> dict[str, dict]:
    """Calculate YoY growth rates from merged financial data by comparing periods.

    Returns dict mapping end_date → {growth_field: value}.
    """
    growth_data: dict[str, dict] = {}
    rows = list(merged.iterrows())
    # Build a list of (end_date, flat_dict) sorted by end_date ascending
    periods = []
    for _, row in rows:
        flat = _flatten_row(row)
        ed = str(flat.get("end_date", ""))
        if ed:
            periods.append((ed, flat))

    # Sort ascending so we can look back
    periods.sort(key=lambda x: x[0])

    for i, (ed, flat) in enumerate(periods):
        cur_rev = _safe_float(flat.get("total_revenue"))
        cur_ni = _safe_float(flat.get("n_income_attr_p"))
        cur_eps = _safe_float(flat.get("basic_eps"))
        cur_op = _safe_float(flat.get("operate_profit"))
        cur_fcf = _safe_float(flat.get("free_cashflow"))
        cur_ocf = _safe_float(flat.get("n_cashflow_act"))
        cur_bv = _safe_float(flat.get("total_hldr_eqy_exc_min_int"))

        growth = {}
        # Find same-period last year for YoY (e.g., 20241231 vs 20231231)
        # Or just use previous available period
        if i > 0:
            _, prev_flat = periods[i - 1]
            prev_rev = _safe_float(prev_flat.get("total_revenue"))
            prev_ni = _safe_float(prev_flat.get("n_income_attr_p"))
            prev_eps = _safe_float(prev_flat.get("basic_eps"))
            prev_op = _safe_float(prev_flat.get("operate_profit"))
            prev_fcf = _safe_float(prev_flat.get("free_cashflow"))
            prev_ocf = _safe_float(prev_flat.get("n_cashflow_act"))
            prev_bv = _safe_float(prev_flat.get("total_hldr_eqy_exc_min_int"))

            if prev_rev and cur_rev and prev_rev != 0:
                growth["revenue_growth"] = (cur_rev - prev_rev) / abs(prev_rev) * 100
            if prev_ni and cur_ni and prev_ni != 0:
                growth["earnings_growth"] = (cur_ni - prev_ni) / abs(prev_ni) * 100
            if prev_eps and cur_eps and prev_eps != 0:
                growth["earnings_per_share_growth"] = (cur_eps - prev_eps) / abs(prev_eps) * 100
            if prev_op and cur_op and prev_op != 0:
                growth["operating_income_growth"] = (cur_op - prev_op) / abs(prev_op) * 100
            if prev_fcf and cur_fcf and prev_fcf != 0:
                growth["free_cash_flow_growth"] = (cur_fcf - prev_fcf) / abs(prev_fcf) * 100
            if prev_ocf and cur_ocf and prev_ocf != 0:
                growth["free_cash_flow_growth"] = (cur_ocf - prev_ocf) / abs(prev_ocf) * 100
            if prev_bv and cur_bv and prev_bv != 0:
                growth["book_value_growth"] = (cur_bv - prev_bv) / abs(prev_bv) * 100

        growth_data[ed] = growth
    return growth_data


# ── Prices ───────────────────────────────────────────────────────────────


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str | None = None) -> list[Price]:
    cache_key = f"{ticker}_{start_date}_{end_date}"
    if cached := _cache.get_prices(cache_key):
        return [Price(**p) for p in cached]

    pro = _get_pro_api()
    df = _safe_fetch(pro, "daily", ts_code=ticker, start_date=_fmt(start_date), end_date=_fmt(end_date))

    if df is None or df.empty:
        return []

    prices = []
    for _, row in df.sort_values("trade_date").iterrows():
        prices.append(
            Price(
                open=_safe_float(row["open"], 0),
                close=_safe_float(row["close"], 0),
                high=_safe_float(row["high"], 0),
                low=_safe_float(row["low"], 0),
                volume=_safe_int(row["vol"], 0) * 100,  # 手 → 股
                time=_parse(row["trade_date"]),
            )
        )

    _cache.set_prices(cache_key, [p.model_dump() for p in prices])
    return prices


# ── Financial Metrics ────────────────────────────────────────────────────


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str | None = None,
) -> list[FinancialMetrics]:
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"
    if cached := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**m) for m in cached]

    pro = _get_pro_api()
    end_fmt = _fmt(end_date)

    # Fetch raw financial statements
    inc_df = _safe_fetch(pro, "income", ts_code=ticker, end_date=end_fmt)
    bs_df = _safe_fetch(pro, "balancesheet", ts_code=ticker, end_date=end_fmt)
    cf_df = _safe_fetch(pro, "cashflow", ts_code=ticker, end_date=end_fmt)

    # Fetch daily_basic for market valuation
    db = _safe_fetch(pro, "daily_basic", ts_code=ticker, trade_date=end_fmt)
    today_mc = today_pe = today_pb = today_ps = None
    if db is not None and not db.empty:
        r = db.iloc[0]
        mv = _safe_float(r.get("total_mv"))
        today_mc = mv * 10000 if mv else None
        today_pe = _safe_float(r.get("pe_ttm")) or _safe_float(r.get("pe"))
        today_pb = _safe_float(r.get("pb"))
        today_ps = _safe_float(r.get("ps_ttm"))

    # Merge by end_date (reporting period)
    merged = _merge_dfs([("inc", inc_df), ("bs", bs_df), ("cf", cf_df)])
    if merged.empty:
        return []

    if period == "annual":
        merged = merged[merged["end_date"].str.endswith("1231")]

    # Calculate growth rates from adjacent periods
    growth_data = _calc_growth_rates(merged)

    metrics_list = []
    for _, row in merged.head(limit).iterrows():
        d = _flatten_row(row)

        revenue = _safe_float(d.get("total_revenue"))
        oper_cost = _safe_float(d.get("oper_cost")) or _safe_float(d.get("total_cogs"))
        n_income = _safe_float(d.get("n_income_attr_p")) or _safe_float(d.get("n_income"))
        op_profit = _safe_float(d.get("operate_profit"))
        total_assets = _safe_float(d.get("total_assets"))
        total_liab = _safe_float(d.get("total_liab"))
        total_cur_assets = _safe_float(d.get("total_cur_assets"))
        total_cur_liab = _safe_float(d.get("total_cur_liab"))
        equity = _safe_float(d.get("total_hldr_eqy_exc_min_int"))
        total_share = _safe_float(d.get("total_share"))
        inventories = _safe_float(d.get("inventories"), 0)
        ncf_act = _safe_float(d.get("n_cashflow_act"))
        fcf = _safe_float(d.get("free_cashflow"))
        ebitda_val = _safe_float(d.get("ebitda"))
        interest_exp = _safe_float(d.get("fin_exp"))

        # Calculate ratios
        gross_margin = (revenue - oper_cost) / revenue if revenue and oper_cost and revenue > 0 else None
        net_margin = n_income / revenue if n_income and revenue and revenue > 0 else None
        oper_margin = op_profit / revenue if op_profit and revenue and revenue > 0 else None
        roe = n_income / equity * 100 if n_income and equity and equity > 0 else None
        roa = n_income / total_assets * 100 if n_income and total_assets and total_assets > 0 else None
        debt_to_assets = total_liab / total_assets * 100 if total_liab and total_assets and total_assets > 0 else None
        debt_to_equity = total_liab / equity if total_liab and equity and equity > 0 else None
        current_ratio = total_cur_assets / total_cur_liab if total_cur_assets and total_cur_liab and total_cur_liab > 0 else None
        quick_ratio = (total_cur_assets - (inventories or 0)) / total_cur_liab if total_cur_assets and total_cur_liab and total_cur_liab > 0 else None
        eps = _safe_float(d.get("basic_eps"))
        bps = equity / total_share if equity and total_share and total_share > 0 else None
        fcf_per_share = fcf / total_share if fcf and total_share and total_share > 0 else None
        interest_coverage = op_profit / abs(interest_exp) if op_profit and interest_exp and interest_exp != 0 else None
        asset_turnover = revenue / total_assets if revenue and total_assets and total_assets > 0 else None
        ocf_ratio = ncf_act / total_cur_liab if ncf_act and total_cur_liab and total_cur_liab > 0 else None

        # Enterprise Value = Market Cap + Total Debt - Cash
        ev = None
        if today_mc and total_assets and total_liab:
            cash = _safe_float(d.get("money_cap"), 0)
            ev = today_mc + total_liab - (cash or 0)

        # EV-based ratios
        ev_to_ebitda = ev / ebitda_val if ev and ebitda_val and ebitda_val > 0 else None
        ev_to_revenue = ev / revenue if ev and revenue and revenue > 0 else None
        fcf_yield = fcf / ev if fcf and ev and ev > 0 else None

        # Market cap only applies to the most recent report period
        report_period_raw = str(row.get("end_date", ""))
        report_period = _parse(report_period_raw)
        is_latest = (report_period_raw == merged.iloc[0]["end_date"])
        mc = today_mc if is_latest else None
        pe = today_pe if is_latest else None
        pb = today_pb if is_latest else None
        ps = today_ps if is_latest else None

        # Growth rates from period comparison
        growth = growth_data.get(report_period_raw, {})

        metrics_list.append(
            FinancialMetrics(
                ticker=ticker,
                report_period=report_period,
                period=period,
                currency="CNY",
                market_cap=mc,
                enterprise_value=ev if is_latest else None,
                price_to_earnings_ratio=pe,
                price_to_book_ratio=pb,
                price_to_sales_ratio=ps,
                enterprise_value_to_ebitda_ratio=ev_to_ebitda if is_latest else None,
                enterprise_value_to_revenue_ratio=ev_to_revenue if is_latest else None,
                free_cash_flow_yield=fcf_yield if is_latest else None,
                peg_ratio=None,
                gross_margin=gross_margin,
                operating_margin=oper_margin,
                net_margin=net_margin,
                return_on_equity=roe,
                return_on_assets=roa,
                return_on_invested_capital=roe,
                asset_turnover=asset_turnover,
                inventory_turnover=None,
                receivables_turnover=None,
                days_sales_outstanding=None,
                operating_cycle=None,
                working_capital_turnover=None,
                current_ratio=current_ratio,
                quick_ratio=quick_ratio,
                cash_ratio=None,
                operating_cash_flow_ratio=ocf_ratio,
                debt_to_equity=debt_to_equity,
                debt_to_assets=debt_to_assets,
                interest_coverage=interest_coverage,
                revenue_growth=growth.get("revenue_growth"),
                earnings_growth=growth.get("earnings_growth"),
                book_value_growth=growth.get("book_value_growth"),
                earnings_per_share_growth=growth.get("earnings_per_share_growth"),
                free_cash_flow_growth=growth.get("free_cash_flow_growth"),
                operating_income_growth=growth.get("operating_income_growth"),
                ebitda_growth=None,
                payout_ratio=None,
                earnings_per_share=eps,
                book_value_per_share=bps,
                free_cash_flow_per_share=fcf_per_share,
            )
        )

    _cache.set_financial_metrics(cache_key, [m.model_dump() for m in metrics_list])
    return metrics_list


# ── Line Items ───────────────────────────────────────────────────────────


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str | None = None,
) -> list[LineItem]:
    pro = _get_pro_api()
    end_fmt = _fmt(end_date)

    # Determine which Tushare APIs we need
    apis_needed: set[str] = set()
    for item in line_items:
        if item in LINE_ITEM_MAP:
            apis_needed.add(LINE_ITEM_MAP[item][0])

    # Fetch raw data from each needed API
    raw: list[tuple[str, pd.DataFrame]] = []

    if "income" in apis_needed:
        df = _safe_fetch(pro, "income", ts_code=ticker, end_date=end_fmt, fields=(
            "ts_code,ann_date,end_date,"
            "total_revenue,oper_cost,total_cogs,operate_profit,total_profit,"
            "n_income,n_income_attr_p,"
            "ebit,ebitda,"
            "sell_exp,admin_exp,fin_exp,rd_exp,"
            "basic_eps"
        ))
        if df is not None and not df.empty:
            raw.append(("income", df))

    if "balancesheet" in apis_needed:
        df = _safe_fetch(pro, "balancesheet", ts_code=ticker, end_date=end_fmt, fields=(
            "ts_code,end_date,"
            "total_assets,total_liab,"
            "total_cur_assets,total_cur_liab,"
            "money_cap,"
            "total_hldr_eqy_exc_min_int,"
            "st_borr,lt_borr,bond_payable,"
            "goodwill,intan_assets,"
            "total_share,"
            "inventories"
        ))
        if df is not None and not df.empty:
            raw.append(("balancesheet", df))

    if "cashflow" in apis_needed:
        df = _safe_fetch(pro, "cashflow", ts_code=ticker, end_date=end_fmt, fields=(
            "ts_code,end_date,"
            "n_cashflow_act,free_cashflow,"
            "depr_fa_coga_dpba,"
            "c_pay_acq_const_fiolta,"
            "c_pay_dist_dpcp_int_exp,"
            "cash_add_cp_imp_fin_pro"
        ))
        if df is not None and not df.empty:
            raw.append(("cashflow", df))

    merged = _merge_dfs(raw)
    if merged.empty:
        return []

    # For annual period, filter to year-end reports
    if period == "annual":
        merged = merged[merged["end_date"].str.endswith("1231")]

    results = []
    for _, row in merged.head(limit).iterrows():
        flat = _flatten_row(row)

        extra = {}
        for item_name in line_items:
            if item_name in LINE_ITEM_MAP:
                _, field = LINE_ITEM_MAP[item_name]
                if field.startswith("_calc_"):
                    val = _calc_field(field, flat)
                else:
                    val = _safe_float(flat.get(field))
                extra[item_name] = val

        report_period = _parse(str(row.get("end_date", "")))
        results.append(
            LineItem(
                ticker=ticker,
                report_period=report_period,
                period=period,
                currency="CNY",
                **extra,
            )
        )

    return results[:limit]


# ── Insider Trades ───────────────────────────────────────────────────────


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str | None = None,
) -> list[InsiderTrade]:
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    if cached := _cache.get_insider_trades(cache_key):
        return [InsiderTrade(**t) for t in cached]

    pro = _get_pro_api()
    df = _safe_fetch(
        pro, "stk_holdertrade",
        ts_code=ticker,
        end_date=_fmt(end_date),
        start_date=_fmt(start_date) if start_date else None,
    )

    if df is None or df.empty:
        return []

    trades = []
    for _, row in df.head(limit).iterrows():
        change_vol = _safe_float(row.get("change_vol"), 0)
        in_de = row.get("in_de", "") or ""
        shares = -(change_vol or 0) if in_de == "DE" else (change_vol or 0)
        avg_price = _safe_float(row.get("avg_price"))
        after_share = _safe_float(row.get("after_share"), 0)
        before_share = (after_share or 0) - (shares or 0) if after_share else None

        trades.append(
            InsiderTrade(
                ticker=ticker,
                issuer=None,
                name=row.get("holder_name"),
                title=row.get("holder_type"),
                is_board_director=row.get("holder_type") in ("G", "C"),
                transaction_date=_parse(str(row.get("ann_date", ""))),
                transaction_shares=shares,
                transaction_price_per_share=avg_price,
                transaction_value=shares * avg_price if avg_price and shares else None,
                shares_owned_before_transaction=before_share,
                shares_owned_after_transaction=after_share if after_share else None,
                security_title=None,
                filing_date=_parse(str(row.get("ann_date", ""))),
            )
        )

    if trades:
        _cache.set_insider_trades(cache_key, [t.model_dump() for t in trades])
    return trades


# ── Company News ─────────────────────────────────────────────────────────


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str | None = None,
) -> list[CompanyNews]:
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    if cached := _cache.get_company_news(cache_key):
        return [CompanyNews(**n) for n in cached]

    pro = _get_pro_api()
    if not start_date:
        dt = datetime.datetime.strptime(end_date, "%Y-%m-%d") - datetime.timedelta(days=70)
        start_date = dt.strftime("%Y-%m-%d")

    df = _safe_fetch(pro, "news", src="sina", start_date=_fmt(start_date), end_date=_fmt(end_date))

    if df is None or df.empty:
        return []

    # Filter news mentioning the ticker
    keyword = ticker.split(".")[0] if "." in ticker else ticker
    news_list = []
    for _, row in df.iterrows():
        title = str(row.get("title", ""))
        content = str(row.get("content", ""))
        if keyword in title or keyword in content:
            pub_time = str(row.get("datetime", row.get("pub_time", "")))
            date_val = pub_time[:10] if len(pub_time) >= 10 else pub_time

            url_val = row.get("url", "")
            news_list.append(
                CompanyNews(
                    ticker=ticker,
                    title=title,
                    author=None,
                    source=str(row.get("src", "tushare")),
                    date=date_val,
                    url=str(url_val) if pd.notna(url_val) else "",
                    sentiment=None,
                )
            )
            if len(news_list) >= limit:
                break

    if news_list:
        _cache.set_company_news(cache_key, [n.model_dump() for n in news_list])
    return news_list


# ── Market Cap ───────────────────────────────────────────────────────────


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str | None = None,
) -> float | None:
    pro = _get_pro_api()
    db = _safe_fetch(pro, "daily_basic", ts_code=ticker, trade_date=_fmt(end_date), fields="ts_code,trade_date,total_mv")
    if db is not None and not db.empty:
        mv = _safe_float(db.iloc[0]["total_mv"])
        if mv is not None:
            return mv * 10000  # 万元 → 元

    # Fallback: derive from financial metrics
    metrics = get_financial_metrics(ticker, end_date, api_key=api_key)
    if metrics:
        return metrics[0].market_cap
    return None


# ── Helpers (re-exported for compatibility) ──────────────────────────────


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str | None = None) -> pd.DataFrame:
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)
