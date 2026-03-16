import datetime
import logging
import os
import pandas as pd
import requests
import time

logger = logging.getLogger(__name__)

from src.data.cache import get_cache
from src.data.dual_cache import get_dual_cache
from src.data.models import (
    CompanyNews,
    CompanyNewsResponse,
    FinancialMetrics,
    FinancialMetricsResponse,
    Price,
    PriceResponse,
    LineItem,
    LineItemResponse,
    InsiderTrade,
    InsiderTradeResponse,
    CompanyFactsResponse,
)

# Global cache instances
_cache = get_cache()  # L1 cache (backward compatibility)


def _get_dual_cache():
    """Get the dual-layer cache instance (lazy initialization)."""
    return get_dual_cache()

# Global market router instance - 延迟初始化以避免循环依赖
_market_router = None


def _get_market_router():
    """
    获取市场路由器实例（延迟初始化）

    延迟导入避免循环依赖：
    api.py -> router.py -> us_stock.py -> api.py

    Returns:
        MarketRouter: 路由器实例
    """
    global _market_router
    if _market_router is None:
        from src.markets.router import MarketRouter
        _market_router = MarketRouter()
    return _market_router


def _is_us_stock(ticker: str) -> bool:
    """
    判断ticker是否为美股

    美股ticker特征：
    - 纯字母（如AAPL, MSFT）
    - 不包含点号或等号

    非美股ticker特征：
    - A股: 600000.SH, 000001.SZ
    - 港股: 0700.HK
    - 商品: GC=F, CL=F

    Args:
        ticker: 股票/商品代码

    Returns:
        bool: 如果是美股返回True，否则False
    """
    # 包含点号或等号的都不是美股
    if '.' in ticker or '=' in ticker:
        return False

    # 纯字母的是美股
    return ticker.isalpha()


def _make_api_request(url: str, headers: dict, method: str = "GET", json_data: dict = None, max_retries: int = 3) -> requests.Response:
    """
    Make an API request with rate limiting handling and moderate backoff.

    Args:
        url: The URL to request
        headers: Headers to include in the request
        method: HTTP method (GET or POST)
        json_data: JSON data for POST requests
        max_retries: Maximum number of retries (default: 3)

    Returns:
        requests.Response: The response object

    Raises:
        Exception: If the request fails after all retries
    """
    last_exception = None

    for attempt in range(max_retries + 1):  # +1 for initial attempt
        try:
            if method.upper() == "POST":
                response = requests.post(url, headers=headers, json=json_data, timeout=30)
            else:
                response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 429 and attempt < max_retries:
                # Linear backoff: 60s, 90s, 120s, 150s...
                delay = 60 + (30 * attempt)
                logger.warning(f"Rate limited (429). Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s before retrying...")
                time.sleep(delay)
                continue

            # Return the response (whether success or other errors)
            return response

        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            last_exception = e
            if attempt < max_retries:
                # Exponential backoff for connection errors: 2s, 4s, 8s
                delay = 2 ** (attempt + 1)
                logger.warning(f"Connection error: {type(e).__name__}. Attempt {attempt + 1}/{max_retries + 1}. Retrying in {delay}s...")
                time.sleep(delay)
                continue
            else:
                # Last attempt failed, raise the exception
                logger.error(f"Connection error after {max_retries + 1} attempts: {type(e).__name__}")
                raise

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception
    raise Exception("Unexpected error in _make_api_request")


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    """
    获取股票历史价格数据（支持多市场）

    支持的市场：
    - 美股: AAPL, MSFT, GOOGL
    - A股: 600000.SH, 000001.SZ
    - 港股: 0700.HK, 9988.HK
    - 商品期货: GC=F, CL=F

    Args:
        ticker: 股票/商品代码
        start_date: 开始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD）
        api_key: API密钥（可选）

    Returns:
        list[Price]: 价格数据列表（Pydantic模型）
    """
    # Check dual-layer cache first (L1 → L2)
    if cached_prices := _get_dual_cache().get_prices(ticker, start_date, end_date):
        return cached_prices

    # 判断是否为美股 - 美股使用原始API，其他市场使用MarketRouter
    if _is_us_stock(ticker):
        # 美股：使用原始 financialdatasets API（保持向后兼容）
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        url = f"https://api.financialdatasets.ai/prices/?ticker={ticker}&interval=day&interval_multiplier=1&start_date={start_date}&end_date={end_date}"
        response = _make_api_request(url, headers)
        if response.status_code != 200:
            return []

        # Parse response with Pydantic model
        try:
            price_response = PriceResponse(**response.json())
            prices = price_response.prices
        except Exception as e:
            logger.warning("Failed to parse price response for %s: %s", ticker, e)
            return []

        if not prices:
            return []

        # Cache the results in dual-layer cache (L1 + L2)
        _get_dual_cache().set_prices(ticker, start_date, end_date, prices)
        return prices
    else:
        # 非美股：使用 MarketRouter（支持A股、港股、商品等）
        try:
            prices = _get_market_router().get_prices(ticker, start_date, end_date)

            # MarketRouter已经返回Price对象列表，无需再次转换
            if prices:
                # Cache the results in dual-layer cache (L1 + L2)
                _get_dual_cache().set_prices(ticker, start_date, end_date, prices)

            return prices
        except ValueError as e:
            # 未找到支持该ticker的适配器
            logger.warning("MarketRouter error for %s: %s", ticker, e)
            return []
        except Exception as e:
            logger.warning("Failed to fetch prices via MarketRouter for %s: %s", ticker, e)
            return []


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
    """
    获取财务指标（支持多市场）

    支持的市场：
    - 美股: AAPL, MSFT, GOOGL
    - A股: 600000.SH, 000001.SZ
    - 港股: 0700.HK, 9988.HK
    - 商品期货: 不支持财务指标

    Args:
        ticker: 股票代码
        end_date: 截止日期（YYYY-MM-DD）
        period: 报告期（ttm, quarterly等）
        limit: 最大返回数量
        api_key: API密钥（可选）

    Returns:
        list[FinancialMetrics]: 财务指标列表（Pydantic模型）
    """
    # Check dual-layer cache first (L1 → L2)
    if cached_metrics := _get_dual_cache().get_financial_metrics(ticker, end_date, period, limit):
        return cached_metrics

    # 判断是否为美股
    if _is_us_stock(ticker):
        # 美股：使用原始 financialdatasets API（保持向后兼容）
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}&report_period_lte={end_date}&limit={limit}&period={period}"
        response = _make_api_request(url, headers)
        if response.status_code != 200:
            return []

        # Parse response with Pydantic model
        try:
            metrics_response = FinancialMetricsResponse(**response.json())
            financial_metrics = metrics_response.financial_metrics
        except Exception as e:
            logger.warning("Failed to parse financial metrics response for %s: %s", ticker, e)
            return []

        if not financial_metrics:
            return []

        # Cache the results in dual-layer cache (L1 + L2)
        _get_dual_cache().set_financial_metrics(ticker, end_date, period, limit, financial_metrics)
        return financial_metrics
    else:
        # 非美股：使用 MarketRouter
        try:
            metrics_dict = _get_market_router().get_financial_metrics(ticker, end_date)

            if not metrics_dict:
                return []

            # 将字典转换为 Pydantic 模型
            # 注意：需要确保字段匹配
            metric = FinancialMetrics(**metrics_dict)
            metrics = [metric]

            # Cache the results in dual-layer cache (L1 + L2)
            _get_dual_cache().set_financial_metrics(ticker, end_date, period, limit, metrics)

            return metrics
        except ValueError as e:
            # 未找到支持该ticker的适配器
            logger.warning("MarketRouter error for %s: %s", ticker, e)
            return []
        except Exception as e:
            logger.warning("Failed to fetch financial metrics via MarketRouter for %s: %s", ticker, e)
            return []


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    """
    Fetch line items from API (支持多市场).

    对于美股：使用 financialdatasets.ai API
    对于非美股（港股、A股）：从 financial_metrics 构建 LineItem 对象
    """
    # 判断是否为美股
    if _is_us_stock(ticker):
        # 美股：使用原始 financialdatasets API
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        url = "https://api.financialdatasets.ai/financials/search/line-items"

        body = {
            "tickers": [ticker],
            "line_items": line_items,
            "end_date": end_date,
            "period": period,
            "limit": limit,
        }
        response = _make_api_request(url, headers, method="POST", json_data=body)
        if response.status_code != 200:
            return []

        try:
            data = response.json()
            response_model = LineItemResponse(**data)
            search_results = response_model.search_results
        except Exception as e:
            logger.warning("Failed to parse line items response for %s: %s", ticker, e)
            return []
        if not search_results:
            return []

        return search_results[:limit]
    else:
        # 非美股：从 financial_metrics 构建 LineItem
        # 获取多期财务数据
        metrics_list = get_financial_metrics(ticker, end_date, period=period, limit=limit, api_key=api_key)

        if not metrics_list:
            return []

        # 将 FinancialMetrics 转换为 LineItem 格式
        line_items_result = []
        for metric in metrics_list:
            # 构建 LineItem 对象，将请求的字段映射到 metric 中的对应字段
            line_item_dict = {
                "ticker": metric.ticker,
                "report_period": metric.report_period or "",
                "period": metric.period,
                "currency": metric.currency or "USD",
            }

            # 映射请求的字段到 metric 中的对应字段
            field_mapping = {
                "revenue": "revenue",
                "operating_margin": "operating_margin",
                "debt_to_equity": "debt_to_equity",
                "free_cash_flow": "free_cash_flow",
                "total_assets": "total_assets",
                "total_liabilities": "total_liabilities",
                "dividends_and_other_cash_distributions": "dividends",
                "outstanding_shares": "outstanding_shares",
            }

            # 为所有请求的字段添加值（即使是None），确保字段可访问
            for requested_field in line_items:
                metric_field = field_mapping.get(requested_field, requested_field)
                value = getattr(metric, metric_field, None)
                line_item_dict[requested_field] = value

            line_items_result.append(LineItem(**line_item_dict))

        return line_items_result


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
    """
    Fetch insider trades from cache or API (支持多市场).

    支持的市场：
    - 美股: AAPL, MSFT, GOOGL (使用 financialdatasets API)
    - A股: 600000.SH, 000001.SZ (使用 MarketRouter -> AKShare)
    - 港股: 0700.HK, 9988.HK (暂无数据源，返回空列表)

    Args:
        ticker: 股票代码
        end_date: 截止日期（YYYY-MM-DD）
        start_date: 开始日期（可选，YYYY-MM-DD）
        limit: 最大返回数量
        api_key: API密钥（可选）

    Returns:
        list[InsiderTrade]: 内部交易数据列表（Pydantic模型）
    """
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"

    # Check L1 cache first (insider trades not in L2 yet)
    if cached_data := _cache.get_insider_trades(cache_key):
        return [InsiderTrade(**trade) for trade in cached_data]

    # 判断是否为美股
    if _is_us_stock(ticker):
        # 美股：使用原始 financialdatasets API（保持向后兼容）
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        all_trades = []
        current_end_date = end_date

        while True:
            url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}"
            if start_date:
                url += f"&filing_date_gte={start_date}"
            url += f"&limit={limit}"

            response = _make_api_request(url, headers)
            if response.status_code != 200:
                break

            try:
                data = response.json()
                response_model = InsiderTradeResponse(**data)
                insider_trades = response_model.insider_trades
            except Exception as e:
                logger.warning("Failed to parse insider trades response for %s: %s", ticker, e)
                break

            if not insider_trades:
                break

            all_trades.extend(insider_trades)

            # Only continue pagination if we have a start_date and got a full page
            if not start_date or len(insider_trades) < limit:
                break

            # Update end_date to the oldest filing date from current batch for next iteration
            current_end_date = min(trade.filing_date for trade in insider_trades).split("T")[0]

            # If we've reached or passed the start_date, we can stop
            if current_end_date <= start_date:
                break

        if not all_trades:
            return []

        # Cache the results using the comprehensive cache key
        _cache.set_insider_trades(cache_key, [trade.model_dump() for trade in all_trades])
        return all_trades
    else:
        # 非美股：使用 MarketRouter（支持A股、港股等）
        try:
            trades_dicts = _get_market_router().get_insider_trades(ticker, end_date, start_date, limit)

            if not trades_dicts:
                return []

            # 将字典转换为 Pydantic 模型
            trades_list = [InsiderTrade(**trade_dict) for trade_dict in trades_dicts]

            # Cache the results
            _cache.set_insider_trades(cache_key, [trade.model_dump() for trade in trades_list])

            return trades_list
        except ValueError as e:
            # 未找到支持该ticker的适配器
            logger.warning("MarketRouter error for %s: %s", ticker, e)
            return []
        except Exception as e:
            logger.warning("Failed to fetch insider trades via MarketRouter for %s: %s", ticker, e)
            return []


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
    """
    获取公司新闻（支持多市场）

    支持的市场：
    - 美股: AAPL, MSFT, GOOGL
    - A股: 600000.SH, 000001.SZ
    - 港股: 0700.HK, 9988.HK
    - 商品期货: 不支持新闻

    Args:
        ticker: 股票代码
        end_date: 截止日期（YYYY-MM-DD）
        start_date: 开始日期（可选，YYYY-MM-DD）
        limit: 最大返回数量
        api_key: API密钥（可选）

    Returns:
        list[CompanyNews]: 新闻列表（Pydantic模型）
    """
    # Check dual-layer cache first (L1 → L2)
    if cached_news := _get_dual_cache().get_company_news(ticker, start_date or end_date, end_date, limit):
        return cached_news

    # 判断是否为美股
    if _is_us_stock(ticker):
        # 美股：使用原始 financialdatasets API（保持向后兼容）
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        all_news = []
        current_end_date = end_date

        while True:
            url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end_date}"
            if start_date:
                url += f"&start_date={start_date}"
            url += f"&limit={limit}"

            response = _make_api_request(url, headers)
            if response.status_code != 200:
                break

            try:
                data = response.json()
                response_model = CompanyNewsResponse(**data)
                company_news = response_model.news
            except Exception as e:
                logger.warning("Failed to parse company news response for %s: %s", ticker, e)
                break

            if not company_news:
                break

            all_news.extend(company_news)

            # Only continue pagination if we have a start_date and got a full page
            if not start_date or len(company_news) < limit:
                break

            # Update end_date to the oldest date from current batch for next iteration
            current_end_date = min(news.date for news in company_news).split("T")[0]

            # If we've reached or passed the start_date, we can stop
            if current_end_date <= start_date:
                break

        if not all_news:
            return []

        # Cache the results in dual-layer cache (L1 + L2)
        _get_dual_cache().set_company_news(ticker, start_date or end_date, end_date, limit, all_news)
        return all_news
    else:
        # 非美股：使用 MarketRouter
        try:
            news_dicts = _get_market_router().get_company_news(ticker, end_date, limit)

            if not news_dicts:
                return []

            # 将字典转换为 Pydantic 模型
            news_list = [CompanyNews(**news_dict) for news_dict in news_dicts]

            # Cache the results in dual-layer cache (L1 + L2)
            _get_dual_cache().set_company_news(ticker, start_date or end_date, end_date, limit, news_list)

            return news_list
        except ValueError as e:
            # 未找到支持该ticker的适配器
            logger.warning("MarketRouter error for %s: %s", ticker, e)
            return []
        except Exception as e:
            logger.warning("Failed to fetch company news via MarketRouter for %s: %s", ticker, e)
            return []


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
) -> float | None:
    """
    Fetch market cap from the API (支持多市场).

    对于美股：使用 financialdatasets.ai API
    对于非美股：从 financial_metrics 中获取 market_cap 字段
    """
    # 判断是否为美股
    if _is_us_stock(ticker):
        # 美股：使用原始逻辑
        # Check if end_date is today
        if end_date == datetime.datetime.now().strftime("%Y-%m-%d"):
            # Get the market cap from company facts API
            headers = {}
            financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
            if financial_api_key:
                headers["X-API-KEY"] = financial_api_key

            url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
            response = _make_api_request(url, headers)
            if response.status_code != 200:
                logger.warning(f"Error fetching company facts: {ticker} - {response.status_code}")
                return None

            data = response.json()
            response_model = CompanyFactsResponse(**data)
            return response_model.company_facts.market_cap

    # 非美股 或 美股历史数据：从 financial_metrics 获取
    financial_metrics = get_financial_metrics(ticker, end_date, api_key=api_key)
    if not financial_metrics:
        return None

    market_cap = financial_metrics[0].market_cap

    if not market_cap:
        return None

    return market_cap


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


# Update the get_price_data function to use the new functions
def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)
