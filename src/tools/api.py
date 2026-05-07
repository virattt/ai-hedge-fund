import datetime
import json
import logging
import os
import pandas as pd
import requests
import time
from pathlib import Path

logger = logging.getLogger(__name__)

from src.data.cache import get_cache
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

# Global cache instance
_cache = get_cache()


def _default_financial_metric_payload(ticker: str, report_period: str, period: str) -> dict:
    """
    【辅助函数】创建一个完整的财务指标字典模板，所有字段初始化为 None

    作用：为财务指标数据补充缺失的字段，确保数据结构完整
    应用场景：从本地文件或 API 加载数据时，用此模板填充缺失字段

    参数：
        ticker: 股票代码 (如 'AAPL')
        report_period: 报告期间 (如 '2024-12-31')
        period: 财报周期类型 (如 'ttm'=滚动12个月, 'q'=季度, 'a'=年度)

    返回：包含 40+ 个财务指标字段的字典，所有值初始化为 None
    """
    return {
        "ticker": ticker,
        "report_period": report_period,
        "period": period,
        "currency": "USD",
        "market_cap": None,
        "enterprise_value": None,
        "price_to_earnings_ratio": None,
        "price_to_book_ratio": None,
        "price_to_sales_ratio": None,
        "enterprise_value_to_ebitda_ratio": None,
        "enterprise_value_to_revenue_ratio": None,
        "free_cash_flow_yield": None,
        "peg_ratio": None,
        "gross_margin": None,
        "operating_margin": None,
        "net_margin": None,
        "return_on_equity": None,
        "return_on_assets": None,
        "return_on_invested_capital": None,
        "asset_turnover": None,
        "inventory_turnover": None,
        "receivables_turnover": None,
        "days_sales_outstanding": None,
        "operating_cycle": None,
        "working_capital_turnover": None,
        "current_ratio": None,
        "quick_ratio": None,
        "cash_ratio": None,
        "operating_cash_flow_ratio": None,
        "debt_to_equity": None,
        "debt_to_assets": None,
        "interest_coverage": None,
        "revenue_growth": None,
        "earnings_growth": None,
        "book_value_growth": None,
        "earnings_per_share_growth": None,
        "free_cash_flow_growth": None,
        "operating_income_growth": None,
        "ebitda_growth": None,
        "payout_ratio": None,
        "earnings_per_share": None,
        "book_value_per_share": None,
        "free_cash_flow_per_share": None,
    }


def _load_local_aapl_financial_metrics(period: str, end_date: str, limit: int) -> list[FinancialMetrics] | None:
    """
    【辅助函数】从本地 JSON 文件加载 AAPL 财务指标数据

    作用：跳过 API 调用，直接从本地文件读取，用于快速调试和离线开发
    应用场景：
        - 本地开发/测试时避免频繁 API 调用
        - 环境变量 AAPL_METRICS_FILE 指向自定义文件位置
        - 默认路径：project_root/debug/aapl_financial_metrics.txt

    参数：
        period: 财报周期 (如 'ttm', 'q', 'a')
        end_date: 截至日期 (如 '2024-12-31')
        limit: 返回最多多少条记录

    返回：
        list[FinancialMetrics]: 解析后的财务指标列表
        None: 文件不存在或解析失败时返回 None
    """
    project_root = Path(__file__).resolve().parents[2]
    local_file = Path(os.environ.get("AAPL_METRICS_FILE", project_root / "debug" / "aapl_financial_metrics.txt"))

    if not local_file.exists():
        return None

    try:
        raw_text = local_file.read_text(encoding="utf-8").strip()
        if not raw_text:
            return None

        raw_data = json.loads(raw_text)
        records = raw_data.get("records", []) if isinstance(raw_data, dict) else raw_data
        if not isinstance(records, list) or not records:
            return None

        parsed: list[FinancialMetrics] = []
        for row in records:
            if not isinstance(row, dict):
                continue

            report_period = row.get("report_period") or end_date
            payload = _default_financial_metric_payload("AAPL", report_period, period)
            payload.update(row)

            # Force the request's period/ticker so every agent call can reuse this stub.
            payload["ticker"] = "AAPL"
            payload["period"] = period
            parsed.append(FinancialMetrics(**payload))

        if not parsed:
            return None

        # Keep only rows not newer than requested end_date.
        filtered = [m for m in parsed if m.report_period <= end_date]
        if not filtered:
            filtered = parsed

        filtered.sort(key=lambda m: m.report_period, reverse=True)
        return filtered[:limit]
    except Exception as e:
        logger.warning("Failed to load local AAPL financial metrics from %s: %s", local_file, e)
        return None


def _make_api_request(url: str, headers: dict, method: str = "GET", json_data: dict = None, max_retries: int = 3) -> requests.Response:
    """
    【核心工具函数】发起 HTTP 请求，内置 API 速率限制处理和指数退避重试

    作用：
        - 统一处理所有 API 请求，简化调用逻辑
        - 自动处理 HTTP 429 (Too Many Requests) 错误
        - 实现线性退避策略 (60s, 90s, 120s, 150s...)

    参数：
        url: API 端点 URL
        headers: HTTP 请求头 (含 X-API-KEY)
        method: 请求方法 ('GET' 或 'POST')
        json_data: POST 请求体数据
        max_retries: 最大重试次数 (默认 3)

    返回：requests.Response 对象 (无论成功还是失败都返回)

    重试逻辑：
        - 收到 429 且未超过重试次数 → 等待后重试
        - 其他错误 → 直接返回
        - 最后一次重试失败 → 返回失败响应
    """
    for attempt in range(max_retries + 1):  # +1 for initial attempt
        if method.upper() == "POST":
            response = requests.post(url, headers=headers, json=json_data)
        else:
            response = requests.get(url, headers=headers)

        if response.status_code == 429 and attempt < max_retries:
            # Linear backoff: 60s, 90s, 120s, 150s...
            delay = 60 + (30 * attempt)
            print(f"Rate limited (429). Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s before retrying...")
            time.sleep(delay)
            continue

        # Return the response (whether success, other errors, or final 429)
        return response


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    """
    【数据获取函数】获取股票日线价格数据

    作用：
        - 获取指定时间范围内的股票 OHLCV 数据 (Open, High, Low, Close, Volume)
        - 优先从缓存读取，缓存未命中则调用 API 获取并缓存

    参数：
        ticker: 股票代码 (如 'AAPL')
        start_date: 起始日期 (如 '2024-01-01')
        end_date: 截至日期 (如 '2024-12-31')
        api_key: API 密钥 (可选，优先使用环境变量 FINANCIAL_DATASETS_API_KEY)

    返回：list[Price] 按日期升序排列的价格数据

    缓存策略：
        - 缓存 key: '{ticker}_{start_date}_{end_date}'
        - 缓存精确匹配 (时间范围完全相同)

    使用场景：
        - 计算技术指标
        - 生成价格走势图
        - 回测和风险计算
    """
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date}_{end_date}"

    # Check cache first - simple exact match
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**price) for price in cached_data]

    # If not in cache, fetch from API
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

    # Cache the results using the comprehensive cache key
    _cache.set_prices(cache_key, [p.model_dump() for p in prices])
    return prices


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
    """
    【数据获取函数】获取股票财务指标数据 (财务比率、增长率等)

    作用：
        - 获取 P/E、P/B、ROE、负债率等 40+ 个财务指标
        - 支持多个时期比对 (滚动年度、季度、年度等)
        - 优先从本地文件/缓存读取，然后才调用 API

    参数：
        ticker: 股票代码
        end_date: 截至日期
        period: 财报周期类型 ('ttm'=滚动12月, 'q'=季度, 'a'=年度) 默认 'ttm'
        limit: 返回最多多少期数据 (默认 10)
        api_key: API 密钥 (可选)

    返回：list[FinancialMetrics] 从新到旧排序的财务指标列表

    优先级：
        1. 如果是 AAPL → 先尝试从本地文件加载 (_load_local_aapl_financial_metrics)
        2. 缓存查询 → 命中则直接返回
        3. API 调用 → 获取新数据并缓存

    使用场景：
        - Buffett / Graham 等投资分析 agent 的基础数据
        - 计算企业盈利能力、财务健康度
    """
    # For quick debugging, allow AAPL metrics to come from a local text file.
    if ticker.upper() == "AAPL":
        if local_metrics := _load_local_aapl_financial_metrics(period=period, end_date=end_date, limit=limit):
            return local_metrics

    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"

    # Check cache first - simple exact match
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**metric) for metric in cached_data]

    # If not in cache, fetch from API
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

    # Cache the results as dicts using the comprehensive cache key
    _cache.set_financial_metrics(cache_key, [m.model_dump() for m in financial_metrics])
    return financial_metrics


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    """
    【数据获取函数】搜索并获取财务报表的具体科目行项数据

    作用：
        - 获取财务报表中的原始数据项 (如 net_income, capital_expenditure 等)
        - 比 get_financial_metrics 更细粒度，直接来自财务报表的核心数据

    参数：
        ticker: 股票代码
        line_items: 要查询的财务科目列表，如：
            ['capital_expenditure', 'depreciation_and_amortization', 'net_income',
             'outstanding_shares', 'total_assets', 'shareholders_equity', ...]
        end_date: 截至日期
        period: 财报周期类型 (默认 'ttm')
        limit: 返回最多多少期 (默认 10)
        api_key: API 密钥

    返回：list[LineItem] 指定科目的历史数据列表

    API 端点：POST https://api.financialdatasets.ai/financials/search/line-items

    使用场景：
        - Warren Buffett agent 计算 ROE、负债率、自由现金流等
        - Fundamentals agent 分析公司基本面
        - 用于深度价值投资分析
    """
    # If not in cache or insufficient data, fetch from API
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

    # Cache the results
    return search_results[:limit]


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
    """
    【数据获取函数】获取公司内部人员交易记录

    作用：
        - 获取高管、董事等内部人士的买卖记录
        - 用于判断管理层对公司前景的真实信心
        - 分页获取，支持时间范围查询

    参数：
        ticker: 股票代码
        end_date: 截至日期
        start_date: 起始日期 (可选，如果不指定则不设下界)
        limit: 单页返回最多多少条 (默认 1000)
        api_key: API 密钥

    返回：list[InsiderTrade] 内部交易记录列表

    分页逻辑：
        - 从 end_date 开始向前翻页
        - 直到达到 start_date 或无更多数据
        - 自动合并所有页的数据

    缓存策略：
        - 缓存 key: '{ticker}_{start_date or none}_{end_date}_{limit}'

    使用场景：
        - 情感分析 agent (Sentiment agent) 检测内部人士信心
        - 评估管理层对公司的态度
    """
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"

    # Check cache first - simple exact match
    if cached_data := _cache.get_insider_trades(cache_key):
        return [InsiderTrade(**trade) for trade in cached_data]

    # If not in cache, fetch from API
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


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
    """
    【数据获取函数】获取公司相关的新闻报道

    作用：
        - 获取新闻标题、发布日期等信息
        - 用于情感分析和市场反应评估
        - 支持时间范围查询和分页

    参数：
        ticker: 股票代码
        end_date: 截至日期
        start_date: 起始日期 (可选)
        limit: 单页最多返回条数 (默认 1000)
        api_key: API 密钥

    返回：list[CompanyNews] 新闻记录列表

    分页逻辑：
        - 同 get_insider_trades，从新到旧翻页
        - 自动合并所有页数据

    缓存策略：
        - 缓存 key: '{ticker}_{start_date or none}_{end_date}_{limit}'

    使用场景：
        - Sentiment agent 进行新闻情感分析
        - 评估市场对公司的态度变化
    """
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"

    # Check cache first - simple exact match
    if cached_data := _cache.get_company_news(cache_key):
        return [CompanyNews(**news) for news in cached_data]

    # If not in cache, fetch from API
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

    # Cache the results using the comprehensive cache key
    _cache.set_company_news(cache_key, [news.model_dump() for news in all_news])
    return all_news


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
) -> float | None:
    """
    【数据获取函数】获取股票当前市值

    作用：
        - 获取股票的当前市值（企业市值 = 股价 × 流通股数）
        - 用于计算 P/E、P/B 等相对估值指标
        - 判断企业规模和投资价值

    参数：
        ticker: 股票代码
        end_date: 截至日期 (如果是今天则调用实时 API，否则从财务指标获取)
        api_key: API 密钥

    返回：float | None
        - 市值（以百万美元计）
        - None: 如果无法获取数据

    两种查询方式：
        1. 如果 end_date 是今天
           → 调用 /company/facts 接口获取实时市值
        2. 如果 end_date 是历史日期
           → 从 get_financial_metrics 获取历史市值

    缓存：间接利用 get_financial_metrics 的缓存

    使用场景：
        - Buffett agent 计算 P/E、P/B 估值倍数
        - 判断企业规模和 margin of safety (安全边际)
    """
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
            print(f"Error fetching company facts: {ticker} - {response.status_code}")
            return None

        data = response.json()
        response_model = CompanyFactsResponse(**data)
        return response_model.company_facts.market_cap

    financial_metrics = get_financial_metrics(ticker, end_date, api_key=api_key)
    if not financial_metrics:
        return None

    market_cap = financial_metrics[0].market_cap

    if not market_cap:
        return None

    return market_cap


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """
    【数据处理工具函数】将价格数据列表转换为 Pandas DataFrame

    作用：
        - 将 API 返回的价格数据统一转换为 DataFrame 格式
        - 标准化列名和数据类型
        - 方便后续的技术分析和时间序列操作

    参数：
        prices: list[Price] 价格数据对象列表

    返回：pd.DataFrame
        - index: Date （日期，从旧到新升序）
        - 列: open, close, high, low, volume （所有列为 float）
        - 数据已排序，可直接用于技术分析

    处理步骤：
        1. 将 Price 对象序列化为字典列表
        2. 创建 DataFrame
        3. 解析 time 列为 Date 并设为 index
        4. 清理数据类型（确保数值列为 float）
        5. 按日期升序排序

    使用场景：
        - 计算技术指标 (MA, RSI, Bollinger Bands 等)
        - 绘制股价走势图
        - 时间序列分析
    """
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    """
    【便利函数】获取价格数据并转换为 DataFrame

    作用：
        - 一站式获取股票价格数据的 DataFrame 形式
        - 简化调用者代码（无需分别调用 get_prices 和 prices_to_df）

    参数：
        ticker: 股票代码
        start_date: 起始日期
        end_date: 截至日期
        api_key: API 密钥

    返回：pd.DataFrame (同 prices_to_df 返回格式)
        - index: Date
        - 列: open, close, high, low, volume

    内部流程：
        1. 调用 get_prices() 从缓存/API 获取原始价格数据
        2. 调用 prices_to_df() 转换为 DataFrame

    使用场景：
        - 任何需要价格数据的地方（技术分析、风险计算等）
        - 是对外的主要接口，而不是直接调用 get_prices

    注意：
        - 缓存和重试逻辑由 get_prices 负责
        - 此函数只负责格式转换
    """
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)
