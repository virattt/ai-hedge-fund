"""
CNStockAdapter (A股适配器) 单元测试
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from src.markets.cn_stock import CNStockAdapter


@pytest.fixture
def mock_akshare_price_data():
    """模拟AkShare返回的价格数据"""
    return pd.DataFrame([
        {
            "日期": "2024-01-01",
            "开盘": 100.0,
            "收盘": 105.0,
            "最高": 106.0,
            "最低": 99.0,
            "成交量": 1000000
        },
        {
            "日期": "2024-01-02",
            "开盘": 105.0,
            "收盘": 103.0,
            "最高": 107.0,
            "最低": 102.0,
            "成交量": 1200000
        }
    ])


@pytest.fixture
def mock_akshare_financial_data():
    """模拟AkShare返回的财务分析指标数据"""
    return pd.DataFrame([
        {
            "报告期": "2023-12-31",
            "市盈率": 20.0,
            "市净率": 2.5,
            "总市值": 4000000000.0,
            "营业收入": 8000000000.0,
            "净利润": 800000000.0
        },
        {
            "报告期": "2024-03-31",
            "市盈率": 25.5,
            "市净率": 3.2,
            "总市值": 5000000000.0,
            "营业收入": 10000000000.0,
            "净利润": 1000000000.0
        }
    ])


@pytest.fixture
def mock_feedparser_data():
    """模拟feedparser返回的新闻数据"""
    mock_entry = MagicMock()
    mock_entry.title = "测试新闻1"
    mock_entry.link = "http://example.com/1"
    mock_entry.published = "Mon, 01 Jan 2024 00:00:00 GMT"
    mock_entry.summary = "新闻摘要1"
    mock_entry.get = MagicMock(side_effect=lambda k, default='': {
        'published': 'Mon, 01 Jan 2024 00:00:00 GMT',
        'summary': '新闻摘要1'
    }.get(k, default))

    mock_feed = MagicMock()
    mock_feed.entries = [mock_entry]

    return mock_feed


# ============== Step 3: 测试 supports_ticker ==============

def test_supports_ticker_cn_stock():
    """测试A股ticker格式识别（上海和深圳交易所）"""
    adapter = CNStockAdapter()

    # 应该支持的格式
    assert adapter.supports_ticker("600000.SH") is True
    assert adapter.supports_ticker("000001.SZ") is True
    assert adapter.supports_ticker("688001.SH") is True  # 科创板
    assert adapter.supports_ticker("300001.SZ") is True  # 创业板

    # 不应该支持的格式
    assert adapter.supports_ticker("AAPL") is False
    assert adapter.supports_ticker("0700.HK") is False
    assert adapter.supports_ticker("GC=F") is False
    assert adapter.supports_ticker("600000") is False  # 缺少交易所后缀


# ============== Step 6: 测试 get_prices ==============

@patch('akshare.stock_zh_a_hist')
def test_get_prices(mock_hist, mock_akshare_price_data):
    """测试获取A股历史价格数据"""
    mock_hist.return_value = mock_akshare_price_data

    adapter = CNStockAdapter()
    prices = adapter.get_prices("600000.SH", "2024-01-01", "2024-01-02")

    # 验证返回数据结构
    assert len(prices) == 2
    assert prices[0]["date"] == "2024-01-01"
    assert prices[0]["open"] == 100.0
    assert prices[0]["close"] == 105.0
    assert prices[0]["high"] == 106.0
    assert prices[0]["low"] == 99.0
    assert prices[0]["volume"] == 1000000

    # 验证AkShare API调用参数
    mock_hist.assert_called_once()
    call_args = mock_hist.call_args[1]
    assert call_args["symbol"] == "600000"
    assert call_args["start_date"] == "20240101"
    assert call_args["end_date"] == "20240102"
    assert call_args["adjust"] == "qfq"  # 前复权


@patch('akshare.stock_zh_a_hist')
def test_get_prices_deep_market(mock_hist, mock_akshare_price_data):
    """测试深圳交易所股票价格获取"""
    mock_hist.return_value = mock_akshare_price_data

    adapter = CNStockAdapter()
    prices = adapter.get_prices("000001.SZ", "2024-01-01", "2024-01-02")

    assert len(prices) == 2
    call_args = mock_hist.call_args[1]
    assert call_args["symbol"] == "000001"


# ============== 测试 _convert_news_to_standard ==============

def test_convert_news_to_standard_eastmoney():
    """测试东方财富新闻格式转换"""
    adapter = CNStockAdapter()

    eastmoney_news = {
        "新闻标题": "测试新闻",
        "新闻链接": "http://example.com",
        "发布时间": "2024-01-01 10:30:00",
        "新闻内容": "新闻摘要"
    }

    result = adapter._convert_news_to_standard(eastmoney_news, source="eastmoney")

    assert result["title"] == "测试新闻"
    assert result["link"] == "http://example.com"
    assert result["published"] == "2024-01-01T10:30:00Z"
    assert result["source"] == "eastmoney"
    assert result["sentiment"] is None


def test_convert_news_to_standard_google():
    """测试Google News格式转换"""
    adapter = CNStockAdapter()

    google_entry = {
        "title": "测试新闻",
        "link": "http://example.com",
        "published": "Mon, 01 Jan 2024 10:30:00 GMT",
        "summary": "新闻摘要"
    }

    result = adapter._convert_news_to_standard(google_entry, source="google")

    assert result["title"] == "测试新闻"
    assert result["link"] == "http://example.com"
    assert result["published"] == "2024-01-01T10:30:00Z"
    assert result["source"] == "google"
    assert result["sentiment"] is None


# ============== Step 9: 测试 get_company_news ==============

@patch('akshare.stock_news_em')
def test_get_company_news_eastmoney(mock_news_em):
    """测试获取新闻（东方财富主要来源）"""
    mock_news_em.return_value = pd.DataFrame([
        {
            "新闻标题": "测试新闻1",
            "新闻链接": "http://example.com/1",
            "发布时间": "2024-01-01 10:00:00",
            "新闻内容": "摘要1"
        },
        {
            "新闻标题": "测试新闻2",
            "新闻链接": "http://example.com/2",
            "发布时间": "2024-01-01 11:00:00",
            "新闻内容": "摘要2"
        }
    ])

    adapter = CNStockAdapter()
    news = adapter.get_company_news("600000.SH", "2024-01-01", limit=5)

    # 验证返回数据结构
    assert len(news) == 2
    assert news[0]["title"] == "测试新闻1"
    assert news[0]["link"] == "http://example.com/1"
    assert news[0]["source"] == "eastmoney"
    assert "T" in news[0]["published"]  # ISO格式包含T
    assert news[0]["published"] == "2024-01-01T10:00:00Z"
    assert news[0]["sentiment"] is None

    # 验证API调用参数
    mock_news_em.assert_called_once_with(symbol="600000")


@patch('src.markets.cn_stock.feedparser.parse')
@patch('src.markets.cn_stock.ak.stock_news_em')
def test_get_company_news_fallback_to_google(mock_news_em, mock_parse):
    """测试新闻获取降级到Google News"""
    # 东方财富失败
    mock_news_em.side_effect = Exception("API Error")

    # Google News成功 - 使用类型对象而不是MagicMock
    class MockEntry:
        def __init__(self):
            self.title = "测试新闻2"
            self.link = "http://example.com/2"
            self.published = "Mon, 01 Jan 2024 10:00:00 GMT"
            self.summary = "摘要2"

        def get(self, key, default=''):
            return getattr(self, key, default)

    mock_feed = MagicMock()
    mock_feed.entries = [MockEntry()]
    mock_parse.return_value = mock_feed

    adapter = CNStockAdapter()
    news = adapter.get_company_news("600000.SH", "2024-01-01", limit=5)

    # 验证降级到Google News
    assert len(news) == 1
    assert news[0]["title"] == "测试新闻2"
    assert news[0]["link"] == "http://example.com/2"
    assert news[0]["source"] == "google"
    assert news[0]["published"] == "2024-01-01T10:00:00Z"

    # 验证RSS URL包含正确的股票代码
    mock_parse.assert_called_once()
    call_url = mock_parse.call_args[0][0]
    assert "600000" in call_url
    assert "股票" in call_url


@patch('akshare.stock_news_em')
def test_get_company_news_limit(mock_news_em):
    """测试新闻数量限制"""
    # 创建多条新闻
    news_data = []
    for i in range(10):
        news_data.append({
            "新闻标题": f"新闻{i}",
            "新闻链接": f"http://example.com/{i}",
            "发布时间": f"2024-01-01 1{i}:00:00",
            "新闻内容": f"摘要{i}"
        })

    mock_news_em.return_value = pd.DataFrame(news_data)

    adapter = CNStockAdapter()
    news = adapter.get_company_news("600000.SH", "2024-01-01", limit=3)

    # 应该只返回前3条
    assert len(news) == 3
    assert news[0]["title"] == "新闻0"
    assert news[2]["title"] == "新闻2"


# ============== Step 12: 测试 get_financial_metrics ==============

@patch('akshare.stock_financial_analysis_indicator')
def test_get_financial_metrics(mock_financial, mock_akshare_financial_data):
    """测试获取A股财务指标（使用正确的接口）"""
    mock_financial.return_value = mock_akshare_financial_data

    adapter = CNStockAdapter()
    metrics = adapter.get_financial_metrics("600000.SH", "2024-03-31")

    # 验证返回的财务指标（5个字段）
    assert metrics["pe_ratio"] == 25.5
    assert metrics["pb_ratio"] == 3.2
    assert metrics["market_cap"] == 5000000000.0
    assert metrics["revenue"] == 10000000000.0
    assert metrics["net_profit"] == 1000000000.0

    # 验证API调用参数
    mock_financial.assert_called_once_with(symbol="600000")


@patch('akshare.stock_financial_analysis_indicator')
def test_get_financial_metrics_empty_data(mock_financial):
    """测试财务数据为空的情况"""
    mock_financial.return_value = pd.DataFrame()

    adapter = CNStockAdapter()
    metrics = adapter.get_financial_metrics("600000.SH", "2024-03-31")

    # 应该返回空字典
    assert metrics == {}


@patch('akshare.stock_financial_analysis_indicator')
def test_get_financial_metrics_exception(mock_financial):
    """测试财务数据获取异常"""
    mock_financial.side_effect = Exception("API Error")

    adapter = CNStockAdapter()
    metrics = adapter.get_financial_metrics("600000.SH", "2024-03-31")

    # 应该返回空字典而不是抛出异常
    assert metrics == {}


@patch('akshare.stock_financial_analysis_indicator')
def test_get_financial_metrics_missing_fields(mock_financial):
    """测试财务数据缺少某些字段"""
    # 只包含部分字段
    partial_data = pd.DataFrame([{
        "报告期": "2024-03-31",
        "市盈率": 25.5,
        "总市值": 5000000000.0
    }])
    mock_financial.return_value = partial_data

    adapter = CNStockAdapter()
    metrics = adapter.get_financial_metrics("600000.SH", "2024-03-31")

    # 应该返回有值的字段为实际值，缺失字段为0
    assert metrics["pe_ratio"] == 25.5
    assert metrics["pb_ratio"] == 0
    assert metrics["market_cap"] == 5000000000.0
    assert metrics["revenue"] == 0
    assert metrics["net_profit"] == 0
