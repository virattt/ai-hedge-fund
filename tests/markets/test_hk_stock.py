"""
HKStockAdapter (港股适配器) 单元测试
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime
from src.markets.hk_stock import HKStockAdapter


@pytest.fixture
def mock_yf_ticker():
    """模拟yfinance Ticker对象"""
    mock = MagicMock()

    # 模拟历史数据
    mock.history.return_value = pd.DataFrame({
        'Open': [100.0, 105.0],
        'Close': [105.0, 103.0],
        'High': [106.0, 107.0],
        'Low': [99.0, 102.0],
        'Volume': [1000000, 1200000]
    }, index=pd.DatetimeIndex(['2024-01-01', '2024-01-02']))

    # 模拟新闻
    mock.news = [
        {
            'title': 'Test News 1',
            'link': 'http://example.com/1',
            'providerPublishTime': 1704096000,  # 2024-01-01 10:00:00 UTC
            'publisher': 'Test Publisher'
        },
        {
            'title': 'Test News 2',
            'link': 'http://example.com/2',
            'providerPublishTime': 1704099600,  # 2024-01-01 11:00:00 UTC
            'publisher': 'Another Publisher'
        }
    ]

    # 模拟财务信息
    mock.info = {
        'trailingPE': 25.5,
        'priceToBook': 3.2,
        'marketCap': 5000000000,
        'totalRevenue': 10000000000,
        'netIncomeToCommon': 1000000000
    }

    return mock


# ============== Step 3: 测试 supports_ticker ==============

def test_supports_ticker_hk_stock():
    """测试港股ticker识别"""
    adapter = HKStockAdapter()

    # 港股格式（XXXX.HK）
    assert adapter.supports_ticker("0700.HK") is True
    assert adapter.supports_ticker("9988.HK") is True
    assert adapter.supports_ticker("0001.HK") is True
    assert adapter.supports_ticker("3690.HK") is True

    # 不支持的格式
    assert adapter.supports_ticker("AAPL") is False
    assert adapter.supports_ticker("600000.SH") is False
    assert adapter.supports_ticker("000001.SZ") is False
    assert adapter.supports_ticker("GC=F") is False
    assert adapter.supports_ticker("0700") is False  # 缺少.HK后缀


# ============== Step 6: 测试 get_prices ==============

@patch('src.markets.hk_stock.yf.Ticker')
def test_get_prices(mock_ticker_class, mock_yf_ticker):
    """测试获取港股价格数据"""
    mock_ticker_class.return_value = mock_yf_ticker

    adapter = HKStockAdapter()
    prices = adapter.get_prices("0700.HK", "2024-01-01", "2024-01-02")

    # 验证yfinance调用
    mock_ticker_class.assert_called_once_with("0700.HK")
    mock_yf_ticker.history.assert_called_once_with(
        start="2024-01-01",
        end="2024-01-02"
    )

    # 验证返回格式
    assert len(prices) == 2
    assert prices[0]["date"] == "2024-01-01"
    assert prices[0]["open"] == 100.0
    assert prices[0]["close"] == 105.0
    assert prices[0]["high"] == 106.0
    assert prices[0]["low"] == 99.0
    assert prices[0]["volume"] == 1000000


@patch('src.markets.hk_stock.yf.Ticker')
def test_get_prices_empty_result(mock_ticker_class):
    """测试价格数据为空的情况"""
    mock = MagicMock()
    mock.history.return_value = pd.DataFrame()  # 空DataFrame
    mock_ticker_class.return_value = mock

    adapter = HKStockAdapter()
    prices = adapter.get_prices("0700.HK", "2024-01-01", "2024-01-02")

    assert prices == []


# ============== Step 9: 测试 get_company_news ==============

@patch('src.markets.hk_stock.yf.Ticker')
def test_get_company_news(mock_ticker_class, mock_yf_ticker):
    """测试获取港股新闻"""
    mock_ticker_class.return_value = mock_yf_ticker

    adapter = HKStockAdapter()
    news = adapter.get_company_news("0700.HK", "2024-01-01", limit=5)

    # 验证返回格式
    assert len(news) == 2
    assert news[0]["title"] == "Test News 1"
    assert news[0]["link"] == "http://example.com/1"
    assert "2024-01-01" in news[0]["published"]
    assert news[0]["source"] == "Test Publisher"
    assert news[0]["sentiment"] is None


@patch('src.markets.hk_stock.yf.Ticker')
def test_get_company_news_with_limit(mock_ticker_class, mock_yf_ticker):
    """测试新闻数量限制"""
    mock_ticker_class.return_value = mock_yf_ticker

    adapter = HKStockAdapter()
    news = adapter.get_company_news("0700.HK", "2024-01-01", limit=1)

    # 应该只返回1条
    assert len(news) == 1
    assert news[0]["title"] == "Test News 1"


@patch('src.markets.hk_stock.yf.Ticker')
def test_get_company_news_no_news(mock_ticker_class):
    """测试无新闻的情况"""
    mock = MagicMock()
    mock.news = []
    mock_ticker_class.return_value = mock

    adapter = HKStockAdapter()
    news = adapter.get_company_news("0700.HK", "2024-01-01", limit=5)

    assert news == []


# ============== Step 12: 测试 get_financial_metrics ==============

@patch('src.markets.hk_stock.yf.Ticker')
def test_get_financial_metrics(mock_ticker_class, mock_yf_ticker):
    """测试获取港股财务指标"""
    mock_ticker_class.return_value = mock_yf_ticker

    adapter = HKStockAdapter()
    metrics = adapter.get_financial_metrics("0700.HK", "2024-03-31")

    # 验证返回的财务指标
    assert metrics["pe_ratio"] == 25.5
    assert metrics["pb_ratio"] == 3.2
    assert metrics["market_cap"] == 5000000000
    assert metrics["revenue"] == 10000000000
    assert metrics["net_profit"] == 1000000000


@patch('src.markets.hk_stock.yf.Ticker')
def test_get_financial_metrics_missing_fields(mock_ticker_class):
    """测试财务指标字段缺失"""
    mock = MagicMock()
    mock.info = {
        'trailingPE': 25.5,
        # 其他字段缺失或为None
    }
    mock_ticker_class.return_value = mock

    adapter = HKStockAdapter()
    metrics = adapter.get_financial_metrics("0700.HK", "2024-03-31")

    # 缺失字段应该为0
    assert metrics["pe_ratio"] == 25.5
    assert metrics["pb_ratio"] == 0
    assert metrics["market_cap"] == 0
    assert metrics["revenue"] == 0
    assert metrics["net_profit"] == 0


@patch('src.markets.hk_stock.yf.Ticker')
def test_get_financial_metrics_exception(mock_ticker_class):
    """测试财务数据获取异常"""
    # 让Ticker构造函数抛出异常
    mock_ticker_class.side_effect = Exception("API Error")

    adapter = HKStockAdapter()
    metrics = adapter.get_financial_metrics("0700.HK", "2024-03-31")

    # 应该返回空字典
    assert metrics == {}
