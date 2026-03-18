"""
MarketRouter路由器测试

测试ticker到适配器的路由逻辑
"""
import pytest
from src.markets.router import MarketRouter
from src.markets.base import MarketAdapter


class MockUSAdapter(MarketAdapter):
    """模拟美股适配器"""

    def __init__(self):
        super().__init__(market="US", data_sources=[])

    def normalize_ticker(self, ticker: str) -> str:
        return ticker.upper().strip()

    def supports_ticker(self, ticker: str) -> bool:
        # 美股作为默认，支持所有不带特殊后缀的ticker
        return not any(suffix in ticker for suffix in ['.SH', '.SZ', '.HK', '=F'])

    def get_prices(self, ticker: str, start_date: str, end_date: str):
        return [{'date': '2024-01-01', 'close': 100.0}]

    def get_company_news(self, ticker: str, end_date: str, limit: int):
        return [{'title': 'US News'}]

    def get_financial_metrics(self, ticker: str, end_date: str):
        return {'pe_ratio': 15.0}


class MockCNAdapter(MarketAdapter):
    """模拟A股适配器"""

    def __init__(self):
        super().__init__(market="CN", data_sources=[])

    def normalize_ticker(self, ticker: str) -> str:
        ticker = ticker.upper().strip()
        if ticker.endswith(".SH") or ticker.endswith(".SZ"):
            ticker = ticker[:-3]
        return ticker

    def supports_ticker(self, ticker: str) -> bool:
        return ticker.endswith('.SH') or ticker.endswith('.SZ')

    def get_prices(self, ticker: str, start_date: str, end_date: str):
        return [{'date': '2024-01-01', 'close': 10.0}]

    def get_company_news(self, ticker: str, end_date: str, limit: int):
        return [{'title': 'CN News'}]

    def get_financial_metrics(self, ticker: str, end_date: str):
        return {'pe_ratio': 20.0}


class MockHKAdapter(MarketAdapter):
    """模拟港股适配器"""

    def __init__(self):
        super().__init__(market="HK", data_sources=[])

    def normalize_ticker(self, ticker: str) -> str:
        ticker = ticker.upper().strip()
        if ticker.endswith(".HK"):
            ticker = ticker[:-3]
        return ticker.zfill(5) if ticker.isdigit() else ticker

    def supports_ticker(self, ticker: str) -> bool:
        return ticker.endswith('.HK')

    def get_prices(self, ticker: str, start_date: str, end_date: str):
        return [{'date': '2024-01-01', 'close': 300.0}]

    def get_company_news(self, ticker: str, end_date: str, limit: int):
        return [{'title': 'HK News'}]

    def get_financial_metrics(self, ticker: str, end_date: str):
        return {'pe_ratio': 25.0}


class MockCommodityAdapter(MarketAdapter):
    """模拟商品适配器"""

    def __init__(self):
        super().__init__(market="COMMODITY", data_sources=[])

    def normalize_ticker(self, ticker: str) -> str:
        return ticker.upper().strip()

    def supports_ticker(self, ticker: str) -> bool:
        return '=F' in ticker

    def get_prices(self, ticker: str, start_date: str, end_date: str):
        return [{'date': '2024-01-01', 'close': 2000.0}]

    def get_company_news(self, ticker: str, end_date: str, limit: int):
        return [{'title': 'Gold News'}]

    def get_financial_metrics(self, ticker: str, end_date: str):
        return {}


def test_router_initialization():
    """测试路由器初始化"""
    router = MarketRouter()
    assert router is not None
    assert hasattr(router, 'adapters')
    assert len(router.adapters) > 0


def test_router_routes_cn_stock():
    """测试路由A股ticker到CN适配器"""
    router = MarketRouter()
    # 注入mock适配器用于测试
    router.adapters = [MockCNAdapter(), MockHKAdapter(), MockCommodityAdapter(), MockUSAdapter()]

    adapter = router.route('600000.SH')
    assert isinstance(adapter, MockCNAdapter)

    adapter = router.route('000001.SZ')
    assert isinstance(adapter, MockCNAdapter)


def test_router_routes_hk_stock():
    """测试路由港股ticker到HK适配器"""
    router = MarketRouter()
    router.adapters = [MockCNAdapter(), MockHKAdapter(), MockCommodityAdapter(), MockUSAdapter()]

    adapter = router.route('0700.HK')
    assert isinstance(adapter, MockHKAdapter)


def test_router_routes_commodity():
    """测试路由商品ticker到Commodity适配器"""
    router = MarketRouter()
    router.adapters = [MockCNAdapter(), MockHKAdapter(), MockCommodityAdapter(), MockUSAdapter()]

    adapter = router.route('GC=F')
    assert isinstance(adapter, MockCommodityAdapter)


def test_router_routes_us_stock():
    """测试路由美股ticker到US适配器"""
    router = MarketRouter()
    router.adapters = [MockCNAdapter(), MockHKAdapter(), MockCommodityAdapter(), MockUSAdapter()]

    adapter = router.route('AAPL')
    assert isinstance(adapter, MockUSAdapter)

    adapter = router.route('TSLA')
    assert isinstance(adapter, MockUSAdapter)


def test_router_raises_on_unsupported_ticker():
    """测试不支持的ticker抛出异常"""
    router = MarketRouter()
    router.adapters = []  # 空适配器列表

    with pytest.raises(ValueError, match="未找到支持该ticker的适配器"):
        router.route('INVALID')


def test_router_get_prices_convenience_method():
    """测试get_prices便捷方法"""
    router = MarketRouter()
    router.adapters = [MockCNAdapter(), MockUSAdapter()]

    prices = router.get_prices('600000.SH', '2024-01-01', '2024-01-31')
    assert len(prices) > 0
    assert prices[0]['close'] == 10.0


def test_router_get_company_news_convenience_method():
    """测试get_company_news便捷方法"""
    router = MarketRouter()
    router.adapters = [MockHKAdapter(), MockUSAdapter()]

    news = router.get_company_news('0700.HK', '2024-01-31', 10)
    assert len(news) > 0
    assert news[0]['title'] == 'HK News'


def test_router_get_financial_metrics_convenience_method():
    """测试get_financial_metrics便捷方法"""
    router = MarketRouter()
    router.adapters = [MockCommodityAdapter(), MockUSAdapter()]

    metrics = router.get_financial_metrics('GC=F', '2024-01-31')
    assert metrics == {}  # 商品无财务指标


def test_router_get_adapter():
    """测试get_adapter方法"""
    router = MarketRouter()
    router.adapters = [MockCNAdapter(), MockHKAdapter(), MockCommodityAdapter(), MockUSAdapter()]

    # Test CN stock
    adapter = router.get_adapter('600000.SH')
    assert isinstance(adapter, MockCNAdapter)

    # Test HK stock
    adapter = router.get_adapter('0700.HK')
    assert isinstance(adapter, MockHKAdapter)

    # Test US stock
    adapter = router.get_adapter('AAPL')
    assert isinstance(adapter, MockUSAdapter)

    # Test error case
    router.adapters = []
    with pytest.raises(ValueError, match="No adapter found for ticker"):
        router.get_adapter('INVALID')
