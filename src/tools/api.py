import datetime
import os
import pandas as pd
import requests
import time

from src.data.models import (
    CompanyNews,
    FinancialMetrics,
    Price,
    LineItem,
    InsiderTrade,
)

from src.data.cache import get_cache

# Global cache instance
_cache = get_cache()

# ---------------------------------------------------------------------------
# FMP base URL & auth helper
# ---------------------------------------------------------------------------
FMP_BASE_URL = "https://financialmodelingprep.com/stable"


def _fmp_params(extra: dict | None = None, api_key: str | None = None) -> dict:
    """Return query-params dict that always includes the FMP apikey."""
    key = api_key or os.environ.get("FMP_API_KEY", "")
    params = {"apikey": key}
    if extra:
        params.update(extra)
    return params


# ---------------------------------------------------------------------------
# Generic request helper with retry / rate-limit handling
# ---------------------------------------------------------------------------

def _make_api_request(url: str, params: dict = None, max_retries: int = 3) -> requests.Response:
    """
    Make an API request with rate limiting handling and moderate backoff.
    FMP uses query-param based auth, so no custom headers needed.
    """
    for attempt in range(max_retries + 1):
        response = requests.get(url, params=params)

        if response.status_code == 429 and attempt < max_retries:
            delay = 60 + (30 * attempt)
            print(f"Rate limited (429). Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s before retrying...")
            time.sleep(delay)
            continue

        return response


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------

def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    """Fetch daily OHLCV price data from FMP."""
    cache_key = f"{ticker}_{start_date}_{end_date}"

    if cached_data := _cache.get_prices(cache_key):
        return [Price(**price) for price in cached_data]

    url = f"{FMP_BASE_URL}/historical-price-eod/full"
    params = _fmp_params({
        "symbol": ticker,
        "from": start_date,
        "to": end_date,
    }, api_key)

    response = _make_api_request(url, params)
    if response.status_code != 200:
        return []

    try:
        data = response.json()
        # FMP returns a list of objects directly
        if not isinstance(data, list):
            return []
        prices = [
            Price(
                open=item["open"],
                close=item["close"],
                high=item["high"],
                low=item["low"],
                volume=int(item["volume"]),
                time=item["date"],
            )
            for item in data
        ]
    except Exception:
        return []

    if not prices:
        return []

    _cache.set_prices(cache_key, [p.model_dump() for p in prices])
    return prices


# ---------------------------------------------------------------------------
# Financial Metrics  (combines FMP /ratios, /key-metrics, /financial-growth)
# ---------------------------------------------------------------------------

def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
    """Fetch financial metrics by merging FMP ratios, key-metrics, and growth data."""
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"

    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**metric) for metric in cached_data]

    # Map period names: the old API used "ttm"/"annual"/"quarterly"
    # FMP uses "annual"/"quarter" for statements; for ratios/key-metrics it
    # also supports "quarter" and "annual" (no "ttm" param – annual is closest).
    fmp_period = "quarter" if period == "quarterly" else "annual"

    # --- Ratios ---
    ratios_url = f"{FMP_BASE_URL}/ratios"
    ratios_params = _fmp_params({"symbol": ticker, "period": fmp_period, "limit": limit}, api_key)
    ratios_resp = _make_api_request(ratios_url, ratios_params)
    ratios_list = ratios_resp.json() if ratios_resp.status_code == 200 else []
    if not isinstance(ratios_list, list):
        ratios_list = []

    # --- Key Metrics ---
    km_url = f"{FMP_BASE_URL}/key-metrics"
    km_params = _fmp_params({"symbol": ticker, "period": fmp_period, "limit": limit}, api_key)
    km_resp = _make_api_request(km_url, km_params)
    km_list = km_resp.json() if km_resp.status_code == 200 else []
    if not isinstance(km_list, list):
        km_list = []

    # --- Financial Growth ---
    growth_url = f"{FMP_BASE_URL}/financial-growth"
    growth_params = _fmp_params({"symbol": ticker, "period": fmp_period, "limit": limit}, api_key)
    growth_resp = _make_api_request(growth_url, growth_params)
    growth_list = growth_resp.json() if growth_resp.status_code == 200 else []
    if not isinstance(growth_list, list):
        growth_list = []

    # Index by date for merging
    ratios_by_date = {r.get("date"): r for r in ratios_list}
    km_by_date = {k.get("date"): k for k in km_list}
    growth_by_date = {g.get("date"): g for g in growth_list}

    all_dates = sorted(
        set(list(ratios_by_date.keys()) + list(km_by_date.keys()) + list(growth_by_date.keys())),
        reverse=True,
    )

    # Filter dates <= end_date
    all_dates = [d for d in all_dates if d and d <= end_date][:limit]

    metrics = []
    for date in all_dates:
        r = ratios_by_date.get(date, {})
        k = km_by_date.get(date, {})
        g = growth_by_date.get(date, {})

        metrics.append(FinancialMetrics(
            ticker=ticker,
            report_period=date,
            period=period,
            currency=r.get("reportedCurrency") or k.get("reportedCurrency") or "USD",
            market_cap=k.get("marketCap"),
            enterprise_value=k.get("enterpriseValue"),
            price_to_earnings_ratio=r.get("priceToEarningsRatio"),
            price_to_book_ratio=r.get("priceToBookRatio"),
            price_to_sales_ratio=r.get("priceToSalesRatio"),
            enterprise_value_to_ebitda_ratio=r.get("enterpriseValueMultiple"),
            enterprise_value_to_revenue_ratio=k.get("evToSales"),
            free_cash_flow_yield=k.get("freeCashFlowYield"),
            peg_ratio=r.get("priceToEarningsGrowthRatio"),
            gross_margin=r.get("grossProfitMargin"),
            operating_margin=r.get("operatingProfitMargin"),
            net_margin=r.get("netProfitMargin"),
            return_on_equity=k.get("returnOnEquity"),
            return_on_assets=k.get("returnOnAssets"),
            return_on_invested_capital=k.get("returnOnInvestedCapital"),
            asset_turnover=r.get("assetTurnover"),
            inventory_turnover=r.get("inventoryTurnover"),
            receivables_turnover=r.get("receivablesTurnover"),
            days_sales_outstanding=k.get("daysOfSalesOutstanding"),
            operating_cycle=k.get("operatingCycle"),
            working_capital_turnover=r.get("workingCapitalTurnoverRatio"),
            current_ratio=k.get("currentRatio") or r.get("currentRatio"),
            quick_ratio=r.get("quickRatio"),
            cash_ratio=r.get("cashRatio"),
            operating_cash_flow_ratio=r.get("operatingCashFlowRatio"),
            debt_to_equity=r.get("debtToEquityRatio"),
            debt_to_assets=r.get("debtToAssetsRatio"),
            interest_coverage=r.get("interestCoverageRatio"),
            revenue_growth=g.get("revenueGrowth"),
            earnings_growth=g.get("netIncomeGrowth"),
            book_value_growth=g.get("bookValueperShareGrowth"),
            earnings_per_share_growth=g.get("epsgrowth"),
            free_cash_flow_growth=g.get("freeCashFlowGrowth"),
            operating_income_growth=g.get("operatingIncomeGrowth"),
            ebitda_growth=g.get("ebitdaGrowth"),
            payout_ratio=r.get("dividendPayoutRatio"),
            earnings_per_share=r.get("netIncomePerShare"),
            book_value_per_share=r.get("bookValuePerShare"),
            free_cash_flow_per_share=r.get("freeCashFlowPerShare"),
        ))

    if not metrics:
        return []

    _cache.set_financial_metrics(cache_key, [m.model_dump() for m in metrics])
    return metrics


# ---------------------------------------------------------------------------
# Line Items  (replaces POST /financials/search/line-items)
# ---------------------------------------------------------------------------

# Mapping from snake_case line-item names used by agents → (FMP endpoint suffix, FMP camelCase key)
_LINE_ITEM_MAP: dict[str, tuple[str, str]] = {
    # Income Statement
    "revenue":                              ("income-statement", "revenue"),
    "net_income":                           ("income-statement", "netIncome"),
    "operating_income":                     ("income-statement", "operatingIncome"),
    "ebit":                                 ("income-statement", "ebit"),
    "ebitda":                               ("income-statement", "ebitda"),
    "interest_expense":                     ("income-statement", "interestExpense"),
    "gross_profit":                         ("income-statement", "grossProfit"),
    "operating_expense":                    ("income-statement", "operatingExpenses"),
    "research_and_development":             ("income-statement", "researchAndDevelopmentExpenses"),
    "earnings_per_share":                   ("income-statement", "eps"),
    "outstanding_shares":                   ("income-statement", "weightedAverageShsOut"),
    # Balance Sheet
    "total_assets":                         ("balance-sheet-statement", "totalAssets"),
    "total_liabilities":                    ("balance-sheet-statement", "totalLiabilities"),
    "current_assets":                       ("balance-sheet-statement", "totalCurrentAssets"),
    "current_liabilities":                  ("balance-sheet-statement", "totalCurrentLiabilities"),
    "shareholders_equity":                  ("balance-sheet-statement", "totalStockholdersEquity"),
    "total_debt":                           ("balance-sheet-statement", "totalDebt"),
    "cash_and_equivalents":                 ("balance-sheet-statement", "cashAndCashEquivalents"),
    "goodwill_and_intangible_assets":       ("balance-sheet-statement", "goodwillAndIntangibleAssets"),
    "intangible_assets":                    ("balance-sheet-statement", "intangibleAssets"),
    # Cash Flow Statement
    "free_cash_flow":                       ("cash-flow-statement", "freeCashFlow"),
    "capital_expenditure":                  ("cash-flow-statement", "capitalExpenditure"),
    "depreciation_and_amortization":        ("cash-flow-statement", "depreciationAndAmortization"),
    "dividends_and_other_cash_distributions": ("cash-flow-statement", "netDividendsPaid"),
    "issuance_or_purchase_of_equity_shares": ("cash-flow-statement", "netStockIssuance"),
    # Derived / Key Metrics
    "working_capital":                      ("key-metrics", "workingCapital"),
    "gross_margin":                         ("ratios", "grossProfitMargin"),
    "operating_margin":                     ("ratios", "operatingProfitMargin"),
    "book_value_per_share":                 ("ratios", "bookValuePerShare"),
    "debt_to_equity":                       ("ratios", "debtToEquityRatio"),
    "return_on_invested_capital":           ("key-metrics", "returnOnInvestedCapital"),
}


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    """
    Replaces the old POST /financials/search/line-items by fetching the
    required FMP statement endpoints and extracting the requested fields.
    """
    fmp_period = "quarter" if period == "quarterly" else "annual"

    # Determine which FMP endpoints we need
    needed_endpoints: set[str] = set()
    for item in line_items:
        if item in _LINE_ITEM_MAP:
            needed_endpoints.add(_LINE_ITEM_MAP[item][0])
        # If not in map, we still try income-statement as fallback
        else:
            needed_endpoints.add("income-statement")

    # Fetch each endpoint once
    endpoint_data: dict[str, list[dict]] = {}
    for ep in needed_endpoints:
        url = f"{FMP_BASE_URL}/{ep}"
        params = _fmp_params({"symbol": ticker, "period": fmp_period, "limit": limit}, api_key)
        resp = _make_api_request(url, params)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                endpoint_data[ep] = data
            else:
                endpoint_data[ep] = []
        else:
            endpoint_data[ep] = []

    # Determine the set of report dates available (use the first endpoint that has data)
    all_dates: list[str] = []
    for ep_records in endpoint_data.values():
        for rec in ep_records:
            d = rec.get("date")
            if d and d not in all_dates:
                all_dates.append(d)
    all_dates = sorted(set(all_dates), reverse=True)
    all_dates = [d for d in all_dates if d <= end_date][:limit]

    # Index endpoint data by date
    indexed: dict[str, dict[str, dict]] = {}  # date -> endpoint -> record
    for ep, records in endpoint_data.items():
        for rec in records:
            d = rec.get("date")
            if d:
                indexed.setdefault(d, {})[ep] = rec

    results: list[LineItem] = []
    for date in all_dates:
        ep_records = indexed.get(date, {})
        extra_fields: dict[str, any] = {}

        for item_name in line_items:
            if item_name in _LINE_ITEM_MAP:
                ep, fmp_key = _LINE_ITEM_MAP[item_name]
                rec = ep_records.get(ep, {})
                extra_fields[item_name] = rec.get(fmp_key)
            else:
                # Try to find the camelCase version in any available endpoint
                camel = _snake_to_camel(item_name)
                found = False
                for rec in ep_records.values():
                    if camel in rec:
                        extra_fields[item_name] = rec[camel]
                        found = True
                        break
                if not found:
                    extra_fields[item_name] = None

        # Determine currency from any available record
        currency = "USD"
        for rec in ep_records.values():
            if "reportedCurrency" in rec:
                currency = rec["reportedCurrency"]
                break

        li = LineItem(
            ticker=ticker,
            report_period=date,
            period=period,
            currency=currency,
            **extra_fields,
        )
        results.append(li)

    return results[:limit]


def _snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


# ---------------------------------------------------------------------------
# Insider Trades
# ---------------------------------------------------------------------------

def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
    """Fetch insider trades from FMP."""
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"

    if cached_data := _cache.get_insider_trades(cache_key):
        return [InsiderTrade(**trade) for trade in cached_data]

    url = f"{FMP_BASE_URL}/insider-trading/search"
    params = _fmp_params({"symbol": ticker, "limit": min(limit, 500)}, api_key)

    all_trades: list[InsiderTrade] = []
    page = 0

    while True:
        params["page"] = page
        response = _make_api_request(url, params)
        if response.status_code != 200:
            break

        try:
            data = response.json()
            if not isinstance(data, list) or not data:
                break
        except Exception:
            break

        for item in data:
            filing_date = (item.get("filingDate") or "").split(" ")[0]
            transaction_date = (item.get("transactionDate") or "").split(" ")[0]

            # Filter by date range
            if filing_date and filing_date > end_date:
                continue
            if start_date and filing_date and filing_date < start_date:
                continue

            # Determine transaction value
            shares = item.get("securitiesTransacted")
            price = item.get("price")
            tx_value = None
            if shares is not None and price is not None:
                try:
                    tx_value = float(shares) * float(price)
                except (ValueError, TypeError):
                    pass

            # Determine if board director from typeOfOwner
            type_of_owner = (item.get("typeOfOwner") or "").lower()
            is_board = "director" in type_of_owner

            trade = InsiderTrade(
                ticker=ticker,
                issuer=None,
                name=item.get("reportingName"),
                title=item.get("typeOfOwner"),
                is_board_director=is_board,
                transaction_date=transaction_date or None,
                transaction_shares=float(shares) if shares is not None else None,
                transaction_price_per_share=float(price) if price is not None else None,
                transaction_value=tx_value,
                shares_owned_before_transaction=None,
                shares_owned_after_transaction=float(item["securitiesOwned"]) if item.get("securitiesOwned") is not None else None,
                security_title=item.get("securityName"),
                filing_date=filing_date,
            )
            all_trades.append(trade)

        # Stop if we have enough or the page was not full
        if len(all_trades) >= limit or len(data) < 500:
            break
        page += 1

    all_trades = all_trades[:limit]

    if not all_trades:
        return []

    _cache.set_insider_trades(cache_key, [trade.model_dump() for trade in all_trades])
    return all_trades


# ---------------------------------------------------------------------------
# Company News
# ---------------------------------------------------------------------------

def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
    """Fetch company news from FMP."""
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"

    if cached_data := _cache.get_company_news(cache_key):
        return [CompanyNews(**news) for news in cached_data]

    url = f"{FMP_BASE_URL}/news/stock"
    params = _fmp_params({
        "symbols": ticker,
        "limit": min(limit, 100),
        "page": 0,
    }, api_key)

    all_news: list[CompanyNews] = []
    page = 0

    while True:
        params["page"] = page
        response = _make_api_request(url, params)
        if response.status_code != 200:
            break

        try:
            data = response.json()
            if not isinstance(data, list) or not data:
                break
        except Exception:
            break

        for item in data:
            pub_date = (item.get("publishedDate") or "").split(" ")[0]

            # Filter by date range
            if pub_date and pub_date > end_date:
                continue
            if start_date and pub_date and pub_date < start_date:
                continue

            news = CompanyNews(
                ticker=ticker,
                title=item.get("title", ""),
                author=item.get("publisher", ""),
                source=item.get("site", ""),
                date=pub_date,
                url=item.get("url", ""),
                sentiment=None,  # FMP does not provide sentiment; filled by SentimentAnalyzer
            )
            all_news.append(news)

        if len(all_news) >= limit or len(data) < 100:
            break
        page += 1

    all_news = all_news[:limit]

    if not all_news:
        return []

    _cache.set_company_news(cache_key, [news.model_dump() for news in all_news])
    return all_news


# ---------------------------------------------------------------------------
# Market Cap
# ---------------------------------------------------------------------------

def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
) -> float | None:
    """Fetch market cap from FMP."""
    if end_date == datetime.datetime.now().strftime("%Y-%m-%d"):
        # Use company profile for real-time market cap
        url = f"{FMP_BASE_URL}/profile"
        params = _fmp_params({"symbol": ticker}, api_key)
        response = _make_api_request(url, params)
        if response.status_code != 200:
            return None
        try:
            data = response.json()
            if isinstance(data, list) and data:
                return data[0].get("marketCap")
            return None
        except Exception:
            return None

    financial_metrics = get_financial_metrics(ticker, end_date, api_key=api_key)
    if not financial_metrics:
        return None

    market_cap = financial_metrics[0].market_cap
    return market_cap if market_cap else None


# ---------------------------------------------------------------------------
# DataFrame helpers
# ---------------------------------------------------------------------------

def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """Convert prices to a DataFrame."""
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)
