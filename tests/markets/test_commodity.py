"""
CommodityAdapter (商品期货适配器) 单元测试
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime
from src.markets.commodity import CommodityAdapter


@pytest.fixture
def mock_yf_ticker():
    """模拟yfinance Ticker对象"""
    mock = MagicMock()

    # 模拟期货历史数据
    mock.history.return_value = pd.DataFrame(
        {
            "Open": [1800.0, 1810.0],
            "Close": [1810.0, 1805.0],
            "High": [1820.0, 1815.0],
            "Low": [1795.0, 1800.0],
            "Volume": [50000, 52000],
        },
        index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"]),
    )

    return mock


@pytest.fixture
def mock_feedparser_gold():
    """模拟feedparser解析黄金新闻的返回值"""
    mock = MagicMock()

    # 创建模拟entry对象，支持.get()和属性访问
    entry1 = MagicMock()
    entry1.get = lambda key, default="": {
        "title": "Gold prices rise on inflation fears",
        "link": "http://example.com/gold-news-1",
    }.get(key, default)
    entry1.title = "Gold prices rise on inflation fears"
    entry1.link = "http://example.com/gold-news-1"
    entry1.published = "Mon, 01 Jan 2024 10:00:00 GMT"

    entry2 = MagicMock()
    entry2.get = lambda key, default="": {
        "title": "Central banks increase gold reserves",
        "link": "http://example.com/gold-news-2",
    }.get(key, default)
    entry2.title = "Central banks increase gold reserves"
    entry2.link = "http://example.com/gold-news-2"
    entry2.published = "Mon, 01 Jan 2024 12:00:00 GMT"

    mock.entries = [entry1, entry2]
    return mock


# ============== Step 1: 测试 supports_ticker ==============


def test_supports_ticker_commodity():
    """测试商品期货ticker识别（=F后缀）"""
    adapter = CommodityAdapter()

    # 支持的期货格式（=F结尾）
    assert adapter.supports_ticker("GC=F") is True  # 黄金期货
    assert adapter.supports_ticker("SI=F") is True  # 白银期货
    assert adapter.supports_ticker("CL=F") is True  # 原油期货
    assert adapter.supports_ticker("NG=F") is True  # 天然气期货
    assert adapter.supports_ticker("HG=F") is True  # 铜期货

    # 不支持的格式
    assert adapter.supports_ticker("AAPL") is False  # 美股
    assert adapter.supports_ticker("600000.SH") is False  # A股
    assert adapter.supports_ticker("0700.HK") is False  # 港股
    assert adapter.supports_ticker("GC") is False  # 缺少=F后缀
    assert adapter.supports_ticker("=F") is False  # 只有后缀


# ============== Step 2: 测试 get_prices ==============


@patch("src.markets.commodity.yf.Ticker")
def test_get_prices(mock_ticker_class, mock_yf_ticker):
    """测试获取商品期货价格数据"""
    mock_ticker_class.return_value = mock_yf_ticker

    adapter = CommodityAdapter()
    prices = adapter.get_prices("GC=F", "2024-01-01", "2024-01-02")

    # 验证yfinance调用
    mock_ticker_class.assert_called_once_with("GC=F")
    mock_yf_ticker.history.assert_called_once_with(
        start="2024-01-01", end="2024-01-02"
    )

    # 验证返回格式
    assert len(prices) == 2
    assert prices[0]["date"] == "2024-01-01"
    assert prices[0]["open"] == 1800.0
    assert prices[0]["close"] == 1810.0
    assert prices[0]["high"] == 1820.0
    assert prices[0]["low"] == 1795.0
    assert prices[0]["volume"] == 50000


@patch("src.markets.commodity.yf.Ticker")
def test_get_prices_empty_result(mock_ticker_class):
    """测试价格数据为空的情况"""
    mock = MagicMock()
    mock.history.return_value = pd.DataFrame()  # 空DataFrame
    mock_ticker_class.return_value = mock

    adapter = CommodityAdapter()
    prices = adapter.get_prices("GC=F", "2024-01-01", "2024-01-02")

    assert prices == []


@patch("src.markets.commodity.yf.Ticker")
def test_get_prices_exception(mock_ticker_class):
    """测试价格数据获取异常"""
    mock = MagicMock()
    mock.history.side_effect = Exception("Network error")
    mock_ticker_class.return_value = mock

    adapter = CommodityAdapter()

    with pytest.raises(Exception) as exc_info:
        adapter.get_prices("GC=F", "2024-01-01", "2024-01-02")

    assert "获取GC=F价格数据失败" in str(exc_info.value)


# ============== Step 3: 测试 get_company_news ==============


@patch("src.markets.commodity.feedparser.parse")
def test_get_company_news_gold(mock_feedparser, mock_feedparser_gold):
    """测试获取黄金期货新闻（通过Google News RSS）"""
    mock_feedparser.return_value = mock_feedparser_gold

    adapter = CommodityAdapter()
    news = adapter.get_company_news("GC=F", "2024-01-01", limit=5)

    # 验证RSS URL调用（应该搜索"Gold"）
    call_args = mock_feedparser.call_args[0][0]
    assert "Gold" in call_args
    assert "news.google.com" in call_args

    # 验证返回格式
    assert len(news) == 2
    assert news[0]["title"] == "Gold prices rise on inflation fears"
    assert news[0]["link"] == "http://example.com/gold-news-1"
    assert "2024-01-01" in news[0]["published"]
    assert news[0]["source"] == "google"
    assert news[0]["sentiment"] is None


@patch("src.markets.commodity.feedparser.parse")
def test_get_company_news_with_limit(mock_feedparser, mock_feedparser_gold):
    """测试新闻数量限制"""
    mock_feedparser.return_value = mock_feedparser_gold

    adapter = CommodityAdapter()
    news = adapter.get_company_news("GC=F", "2024-01-01", limit=1)

    # 应该只返回1条
    assert len(news) == 1
    assert news[0]["title"] == "Gold prices rise on inflation fears"


@patch("src.markets.commodity.feedparser.parse")
def test_get_company_news_silver(mock_feedparser):
    """测试获取白银期货新闻（验证商品名称提取）"""
    mock = MagicMock()
    mock.entries = [
        {
            "title": "Silver market analysis",
            "link": "http://example.com/silver",
            "published": "Mon, 01 Jan 2024 10:00:00 GMT",
        }
    ]
    mock_feedparser.return_value = mock

    adapter = CommodityAdapter()
    news = adapter.get_company_news("SI=F", "2024-01-01", limit=5)

    # 验证RSS URL中包含"Silver"
    call_args = mock_feedparser.call_args[0][0]
    assert "Silver" in call_args

    assert len(news) == 1
    assert news[0]["title"] == "Silver market analysis"


@patch("src.markets.commodity.feedparser.parse")
def test_get_company_news_oil(mock_feedparser):
    """测试获取原油期货新闻（验证商品名称提取）"""
    mock = MagicMock()
    mock.entries = [
        {
            "title": "Oil prices surge",
            "link": "http://example.com/oil",
            "published": "Mon, 01 Jan 2024 10:00:00 GMT",
        }
    ]
    mock_feedparser.return_value = mock

    adapter = CommodityAdapter()
    news = adapter.get_company_news("CL=F", "2024-01-01", limit=5)

    # 验证RSS URL中包含"Crude Oil"
    call_args = mock_feedparser.call_args[0][0]
    assert "Crude Oil" in call_args or "Oil" in call_args

    assert len(news) == 1


@patch("src.markets.commodity.feedparser.parse")
def test_get_company_news_no_news(mock_feedparser):
    """测试无新闻的情况"""
    mock = MagicMock()
    mock.entries = []
    mock_feedparser.return_value = mock

    adapter = CommodityAdapter()
    news = adapter.get_company_news("GC=F", "2024-01-01", limit=5)

    assert news == []


@patch("src.markets.commodity.feedparser.parse")
def test_get_company_news_exception(mock_feedparser):
    """测试新闻获取异常（应返回空列表）"""
    mock_feedparser.side_effect = Exception("RSS parse error")

    adapter = CommodityAdapter()
    news = adapter.get_company_news("GC=F", "2024-01-01", limit=5)

    # 应该返回空列表而不是抛出异常
    assert news == []


@patch("src.markets.commodity.feedparser.parse")
def test_get_company_news_invalid_ticker(mock_feedparser):
    """测试不支持的ticker格式"""
    adapter = CommodityAdapter()

    with pytest.raises(ValueError) as exc_info:
        adapter.get_company_news("AAPL", "2024-01-01", limit=5)

    assert "不支持的ticker格式" in str(exc_info.value)


# ============== Step 4: 测试 get_financial_metrics ==============


def test_get_financial_metrics_returns_empty():
    """测试商品期货返回空财务指标（商品没有财务指标）"""
    adapter = CommodityAdapter()

    # 各种期货ticker都应该返回空字典
    assert adapter.get_financial_metrics("GC=F", "2024-03-31") == {}
    assert adapter.get_financial_metrics("SI=F", "2024-03-31") == {}
    assert adapter.get_financial_metrics("CL=F", "2024-03-31") == {}


def test_get_financial_metrics_invalid_ticker():
    """测试不支持的ticker格式"""
    adapter = CommodityAdapter()

    with pytest.raises(ValueError) as exc_info:
        adapter.get_financial_metrics("AAPL", "2024-03-31")

    assert "不支持的ticker格式" in str(exc_info.value)


# ============== 辅助方法测试 ==============


def test_extract_commodity_name():
    """测试商品名称提取辅助方法"""
    adapter = CommodityAdapter()

    # 测试常见期货代码
    assert adapter._extract_commodity_name("GC=F") == "Gold"
    assert adapter._extract_commodity_name("SI=F") == "Silver"
    assert adapter._extract_commodity_name("CL=F") == "Crude Oil"
    assert adapter._extract_commodity_name("NG=F") == "Natural Gas"
    assert adapter._extract_commodity_name("HG=F") == "Copper"
    assert adapter._extract_commodity_name("ZC=F") == "Corn"
    assert adapter._extract_commodity_name("ZW=F") == "Wheat"

    # 未知期货代码应返回去掉=F的代码
    assert adapter._extract_commodity_name("XX=F") == "XX"
