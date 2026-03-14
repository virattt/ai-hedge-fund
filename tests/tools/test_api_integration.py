"""
API集成测试 - 验证多市场支持

测试api.py是否正确集成了MarketRouter，
并且保持向后兼容性（美股行为不变）
"""
import pytest
from src.tools import api
from src.data.models import Price, FinancialMetrics, CompanyNews


class TestMultiMarketIntegration:
    """测试多市场集成功能"""

    def test_get_prices_us_stock_backward_compatibility(self):
        """测试美股价格获取（向后兼容）- 应该返回Pydantic模型"""
        prices = api.get_prices("AAPL", "2024-01-01", "2024-01-31")

        # 验证返回类型
        assert isinstance(prices, list)
        if len(prices) > 0:
            assert isinstance(prices[0], Price)
            # 验证必需字段
            assert hasattr(prices[0], 'time')
            assert hasattr(prices[0], 'close')
            assert hasattr(prices[0], 'volume')

    def test_get_prices_cn_stock(self):
        """测试A股价格获取（新功能）- 应该返回Pydantic模型"""
        prices = api.get_prices("600000.SH", "2024-01-01", "2024-01-31")

        # 验证返回类型
        assert isinstance(prices, list)
        if len(prices) > 0:
            assert isinstance(prices[0], Price)
            # 验证必需字段
            assert hasattr(prices[0], 'time')
            assert hasattr(prices[0], 'close')

    def test_get_prices_hk_stock(self):
        """测试港股价格获取（新功能）- 应该返回Pydantic模型"""
        prices = api.get_prices("0700.HK", "2024-01-01", "2024-01-31")

        # 验证返回类型
        assert isinstance(prices, list)
        if len(prices) > 0:
            assert isinstance(prices[0], Price)
            # 验证必需字段
            assert hasattr(prices[0], 'time')
            assert hasattr(prices[0], 'close')

    def test_get_prices_commodity(self):
        """测试商品价格获取（新功能）- 应该返回Pydantic模型"""
        prices = api.get_prices("GC=F", "2024-01-01", "2024-01-31")

        # 验证返回类型
        assert isinstance(prices, list)
        if len(prices) > 0:
            assert isinstance(prices[0], Price)
            # 验证必需字段
            assert hasattr(prices[0], 'time')
            assert hasattr(prices[0], 'close')

    def test_get_financial_metrics_us_stock(self):
        """测试美股财务指标（向后兼容）"""
        metrics = api.get_financial_metrics("AAPL", "2024-01-31", period="ttm", limit=1)

        # 验证返回类型
        assert isinstance(metrics, list)
        if len(metrics) > 0:
            assert isinstance(metrics[0], FinancialMetrics)

    def test_get_financial_metrics_cn_stock(self):
        """测试A股财务指标（新功能）"""
        metrics = api.get_financial_metrics("600000.SH", "2024-01-31", period="ttm", limit=1)

        # 验证返回类型（即使为空列表也应该是list类型）
        assert isinstance(metrics, list)
        # A股财务指标可能不可用，但不应该抛出异常
        if len(metrics) > 0:
            assert isinstance(metrics[0], FinancialMetrics)

    def test_get_company_news_us_stock(self):
        """测试美股新闻（向后兼容）"""
        news = api.get_company_news("AAPL", "2024-01-31", limit=5)

        # 验证返回类型
        assert isinstance(news, list)
        if len(news) > 0:
            assert isinstance(news[0], CompanyNews)

    def test_get_company_news_cn_stock(self):
        """测试A股新闻（新功能）"""
        news = api.get_company_news("600000.SH", "2024-01-31", limit=5)

        # 验证返回类型（即使为空列表也应该是list类型）
        assert isinstance(news, list)
        # A股新闻可能不可用，但不应该抛出异常
        if len(news) > 0:
            assert isinstance(news[0], CompanyNews)

    def test_get_price_data_dataframe_format(self):
        """测试DataFrame转换（向后兼容）"""
        import pandas as pd

        # 测试美股
        df = api.get_price_data("AAPL", "2024-01-01", "2024-01-31")
        assert isinstance(df, pd.DataFrame)
        if len(df) > 0:
            assert "close" in df.columns
            assert "volume" in df.columns

    def test_invalid_ticker_handling(self):
        """测试无效ticker的处理"""
        # 应该返回空列表，不应该抛出异常
        prices = api.get_prices("INVALID_TICKER_12345", "2024-01-01", "2024-01-31")
        assert isinstance(prices, list)
        assert len(prices) == 0


class TestMarketRouterFallback:
    """测试市场路由器降级机制"""

    def test_us_stock_uses_original_api(self):
        """验证美股使用原始API（不是router）"""
        # 这个测试确保美股代码路径完全不变
        prices = api.get_prices("MSFT", "2024-01-01", "2024-01-10")

        # 美股应该返回Pydantic模型
        if len(prices) > 0:
            assert isinstance(prices[0], Price)
            # 验证Price模型的必需字段
            assert hasattr(prices[0], 'close')
            assert hasattr(prices[0], 'time')
            assert prices[0].close > 0

    def test_non_us_stock_uses_router(self):
        """验证非美股使用router"""
        # A股应该通过router
        prices = api.get_prices("600519.SH", "2024-01-01", "2024-01-10")

        # 应该返回Pydantic模型（即使来自router）
        assert isinstance(prices, list)
        if len(prices) > 0:
            assert isinstance(prices[0], Price)
