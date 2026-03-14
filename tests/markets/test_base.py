"""
MarketAdapter基类测试

测试抽象基类的接口定义和子类实现要求
"""
import pytest
from abc import ABC
from src.markets.base import MarketAdapter


def test_market_adapter_is_abstract():
    """测试MarketAdapter是抽象类，不能直接实例化"""
    with pytest.raises(TypeError):
        MarketAdapter()


def test_market_adapter_requires_all_methods():
    """测试子类必须实现所有抽象方法"""

    class IncompleteAdapter(MarketAdapter):
        """不完整的适配器实现"""
        pass

    with pytest.raises(TypeError):
        IncompleteAdapter()


def test_market_adapter_with_complete_implementation():
    """测试完整实现所有方法的子类可以实例化"""

    class CompleteAdapter(MarketAdapter):
        """完整的适配器实现"""

        def supports_ticker(self, ticker: str) -> bool:
            return True

        def get_prices(self, ticker: str, start_date: str, end_date: str):
            return []

        def get_company_news(self, ticker: str, end_date: str, limit: int):
            return []

        def get_financial_metrics(self, ticker: str, end_date: str):
            return {}

    # 应该能够成功实例化
    adapter = CompleteAdapter()
    assert isinstance(adapter, MarketAdapter)
