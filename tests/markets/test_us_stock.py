"""
USStockAdapter (美股适配器) 单元测试
"""
import pytest
from unittest.mock import patch, MagicMock
from src.markets.us_stock import USStockAdapter
from src.data.models import Price, FinancialMetrics, CompanyNews


@pytest.fixture
def mock_api_prices():
    """模拟api.get_prices返回的Price对象列表"""
    return [
        Price(
            open=100.0,
            close=105.0,
            high=106.0,
            low=99.0,
            volume=1000000,
            time="2024-01-01"
        ),
        Price(
            open=105.0,
            close=103.0,
            high=107.0,
            low=102.0,
            volume=1200000,
            time="2024-01-02"
        )
    ]


@pytest.fixture
def mock_api_financial_metrics():
    """模拟api.get_financial_metrics返回的FinancialMetrics对象列表"""
    return [
        FinancialMetrics(
            ticker="AAPL",
            report_period="2024-03-31",
            period="ttm",
            currency="USD",
            market_cap=5000000000.0,
            enterprise_value=5200000000.0,
            price_to_earnings_ratio=25.5,
            price_to_book_ratio=3.2,
            price_to_sales_ratio=7.5,
            enterprise_value_to_ebitda_ratio=18.2,
            enterprise_value_to_revenue_ratio=None,
            free_cash_flow_yield=None,
            peg_ratio=None,
            gross_margin=None,
            operating_margin=None,
            net_margin=None,
            return_on_equity=None,
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
            revenue_growth=None,
            earnings_growth=None,
            book_value_growth=None,
            earnings_per_share_growth=None,
            free_cash_flow_growth=None,
            operating_income_growth=None,
            ebitda_growth=None,
            payout_ratio=None,
            earnings_per_share=None,
            book_value_per_share=None,
            free_cash_flow_per_share=None
        )
    ]


@pytest.fixture
def mock_api_company_news():
    """模拟api.get_company_news返回的CompanyNews对象列表"""
    return [
        CompanyNews(
            ticker="AAPL",
            title="Test News 1",
            author="John Doe",
            source="Bloomberg",
            date="2024-01-01T10:00:00Z",
            url="http://example.com/1",
            sentiment="positive"
        ),
        CompanyNews(
            ticker="AAPL",
            title="Test News 2",
            author="Jane Smith",
            source="Reuters",
            date="2024-01-01T11:00:00Z",
            url="http://example.com/2",
            sentiment=None
        )
    ]


# ============== Step 3: 测试 supports_ticker ==============

def test_supports_ticker_us_stock():
    """测试美股ticker识别"""
    adapter = USStockAdapter()

    # 美股ticker（纯大写字母，无后缀）
    assert adapter.supports_ticker("AAPL") is True
    assert adapter.supports_ticker("GOOGL") is True
    assert adapter.supports_ticker("MSFT") is True
    assert adapter.supports_ticker("TSLA") is True
    assert adapter.supports_ticker("NVDA") is True

    # 不支持的格式
    assert adapter.supports_ticker("600000.SH") is False  # A股
    assert adapter.supports_ticker("0700.HK") is False  # 港股
    assert adapter.supports_ticker("GC=F") is False  # 期货
    assert adapter.supports_ticker("aapl") is False  # 小写
    assert adapter.supports_ticker("AAPL.US") is False  # 带后缀
    assert adapter.supports_ticker("123") is False  # 数字
    assert adapter.supports_ticker("AAPL123") is False  # 混合字母数字


# ============== Step 6: 测试 get_prices ==============

@patch('src.markets.us_stock.api.get_prices')
def test_get_prices(mock_api_get_prices, mock_api_prices):
    """测试获取美股价格数据"""
    mock_api_get_prices.return_value = mock_api_prices

    adapter = USStockAdapter()
    prices = adapter.get_prices("AAPL", "2024-01-01", "2024-01-02")

    # 验证调用了正确的API
    mock_api_get_prices.assert_called_once_with(
        ticker="AAPL",
        start_date="2024-01-01",
        end_date="2024-01-02"
    )

    # 验证返回格式（应该转换为字典）
    assert len(prices) == 2
    assert prices[0]["date"] == "2024-01-01"
    assert prices[0]["open"] == 100.0
    assert prices[0]["close"] == 105.0
    assert prices[0]["high"] == 106.0
    assert prices[0]["low"] == 99.0
    assert prices[0]["volume"] == 1000000


@patch('src.markets.us_stock.api.get_prices')
def test_get_prices_empty_result(mock_api_get_prices):
    """测试价格数据为空的情况"""
    mock_api_get_prices.return_value = []

    adapter = USStockAdapter()
    prices = adapter.get_prices("AAPL", "2024-01-01", "2024-01-02")

    assert prices == []


# ============== Step 9: 测试 get_company_news ==============

@patch('src.markets.us_stock.api.get_company_news')
def test_get_company_news(mock_api_news, mock_api_company_news):
    """测试获取美股新闻"""
    mock_api_news.return_value = mock_api_company_news

    adapter = USStockAdapter()
    news = adapter.get_company_news("AAPL", "2024-01-01", limit=5)

    # 验证调用
    mock_api_news.assert_called_once_with(
        ticker="AAPL",
        end_date="2024-01-01",
        limit=5
    )

    # 验证返回格式（应该转换为字典）
    assert len(news) == 2
    assert news[0]["title"] == "Test News 1"
    assert news[0]["url"] == "http://example.com/1"
    assert news[0]["published_date"] == "2024-01-01T10:00:00Z"
    assert news[0]["source"] == "Bloomberg"
    assert news[0]["sentiment"] == "positive"


@patch('src.markets.us_stock.api.get_company_news')
def test_get_company_news_empty_result(mock_api_news):
    """测试新闻为空的情况"""
    mock_api_news.return_value = []

    adapter = USStockAdapter()
    news = adapter.get_company_news("AAPL", "2024-01-01", limit=5)

    assert news == []


@patch('src.markets.us_stock.api.get_company_news')
def test_get_company_news_with_limit(mock_api_news, mock_api_company_news):
    """测试新闻数量限制"""
    mock_api_news.return_value = mock_api_company_news

    adapter = USStockAdapter()
    news = adapter.get_company_news("AAPL", "2024-01-01", limit=1)

    # 验证limit参数传递
    mock_api_news.assert_called_once_with(
        ticker="AAPL",
        end_date="2024-01-01",
        limit=1
    )


# ============== Step 12: 测试 get_financial_metrics ==============

@patch('src.markets.us_stock.api.get_financial_metrics')
def test_get_financial_metrics(mock_api_metrics, mock_api_financial_metrics):
    """测试获取美股财务指标"""
    mock_api_metrics.return_value = mock_api_financial_metrics

    adapter = USStockAdapter()
    metrics = adapter.get_financial_metrics("AAPL", "2024-03-31")

    # 验证调用
    mock_api_metrics.assert_called_once_with(
        ticker="AAPL",
        end_date="2024-03-31"
    )

    # 验证返回格式（应该转换为字典）
    assert metrics["pe_ratio"] == 25.5
    assert metrics["pb_ratio"] == 3.2
    assert metrics["market_cap"] == 5000000000.0
    assert "revenue" in metrics  # 注意：API返回的是enterprise_value等，需要映射
    assert "net_profit" in metrics


@patch('src.markets.us_stock.api.get_financial_metrics')
def test_get_financial_metrics_empty_result(mock_api_metrics):
    """测试财务指标为空的情况"""
    mock_api_metrics.return_value = []

    adapter = USStockAdapter()
    metrics = adapter.get_financial_metrics("AAPL", "2024-03-31")

    assert metrics == {}


@patch('src.markets.us_stock.api.get_financial_metrics')
def test_get_financial_metrics_missing_fields(mock_api_metrics):
    """测试财务指标字段缺失"""
    # 创建缺少部分字段的metrics（pb_ratio为None）
    incomplete_metrics = [
        FinancialMetrics(
            ticker="AAPL",
            report_period="2024-03-31",
            period="ttm",
            currency="USD",
            market_cap=5000000000.0,
            enterprise_value=None,
            price_to_earnings_ratio=25.5,
            price_to_book_ratio=None,  # 这个字段为None
            price_to_sales_ratio=None,
            enterprise_value_to_ebitda_ratio=None,
            enterprise_value_to_revenue_ratio=None,
            free_cash_flow_yield=None,
            peg_ratio=None,
            gross_margin=None,
            operating_margin=None,
            net_margin=None,
            return_on_equity=None,
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
            revenue_growth=None,
            earnings_growth=None,
            book_value_growth=None,
            earnings_per_share_growth=None,
            free_cash_flow_growth=None,
            operating_income_growth=None,
            ebitda_growth=None,
            payout_ratio=None,
            earnings_per_share=None,
            book_value_per_share=None,
            free_cash_flow_per_share=None
        )
    ]
    mock_api_metrics.return_value = incomplete_metrics

    adapter = USStockAdapter()
    metrics = adapter.get_financial_metrics("AAPL", "2024-03-31")

    # 缺失字段应该为0
    assert metrics["pe_ratio"] == 25.5
    assert metrics["pb_ratio"] == 0  # None被转换为0
    assert metrics["market_cap"] == 5000000000.0
