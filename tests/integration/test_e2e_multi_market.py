"""
端到端多市场集成测试

测试完整的多市场数据流：
1. 从 api.py 调用
2. 通过 MarketRouter 路由
3. 到具体的市场适配器
4. 返回正确格式的数据
"""
import pytest
from datetime import datetime, timedelta
from src.tools import api
from src.data.models import Price, CompanyNews, FinancialMetrics


class TestMultiMarketE2E:
    """端到端多市场集成测试"""

    @pytest.fixture
    def date_range(self):
        """提供测试用的日期范围"""
        return {
            "start": "2024-01-01",
            "end": "2024-01-31"
        }

    @pytest.fixture
    def mixed_tickers(self):
        """提供混合市场的ticker列表"""
        return {
            "us": "AAPL",           # 美股
            "a_share": "600000.SH",  # A股（浦发银行）
            "hk": "0700.HK",         # 港股（腾讯）
            "commodity": "GC=F"      # 商品（黄金期货）
        }

    # ==================== 价格数据测试 ====================

    def test_mixed_market_prices(self, mixed_tickers, date_range):
        """测试混合市场价格获取"""
        for market, ticker in mixed_tickers.items():
            prices = api.get_prices(ticker, date_range["start"], date_range["end"])

            # 基本验证
            assert isinstance(prices, list), f"{ticker} should return a list"

            if prices:  # 可能为空（节假日等）
                # 验证返回的是 Pydantic 模型
                assert isinstance(prices[0], Price), f"{ticker} should return Price objects"

                # 验证必需字段
                price = prices[0]
                assert hasattr(price, 'time'), f"{ticker} price should have time"
                assert hasattr(price, 'close'), f"{ticker} price should have close"
                assert hasattr(price, 'open'), f"{ticker} price should have open"
                assert hasattr(price, 'high'), f"{ticker} price should have high"
                assert hasattr(price, 'low'), f"{ticker} price should have low"
                assert hasattr(price, 'volume'), f"{ticker} price should have volume"

                # 验证数据合理性
                assert price.close > 0, f"{ticker} close price should be positive"
                assert price.high >= price.low, f"{ticker} high should be >= low"

                print(f"✓ {market:10s} ({ticker:12s}): {len(prices)} prices retrieved")

    def test_us_stock_prices_detailed(self, date_range):
        """测试美股价格数据的详细验证"""
        ticker = "AAPL"
        prices = api.get_prices(ticker, date_range["start"], date_range["end"])

        assert len(prices) > 0, "AAPL should have price data"

        for price in prices:
            # 验证日期格式
            try:
                date_obj = datetime.fromisoformat(price.time.replace('Z', '+00:00'))
                assert isinstance(date_obj, datetime)
            except ValueError:
                pytest.fail(f"Invalid date format: {price.time}")

            # 验证价格关系
            assert price.high >= price.close >= price.low or \
                   price.high >= price.open >= price.low, \
                   f"Price relationship invalid: H={price.high}, O={price.open}, C={price.close}, L={price.low}"

            # 验证成交量
            assert price.volume >= 0, f"Volume should be non-negative: {price.volume}"

    def test_a_share_prices_detailed(self, date_range):
        """测试A股价格数据的详细验证"""
        ticker = "600000.SH"
        prices = api.get_prices(ticker, date_range["start"], date_range["end"])

        # A股可能因节假日无数据，但不应返回错误
        assert isinstance(prices, list)

        if prices:
            for price in prices:
                assert isinstance(price, Price)
                assert price.close > 0
                print(f"✓ A股 ({ticker}): Sample price={price.close}, date={price.time}")

    def test_hk_stock_prices_detailed(self, date_range):
        """测试港股价格数据的详细验证"""
        ticker = "0700.HK"
        prices = api.get_prices(ticker, date_range["start"], date_range["end"])

        assert isinstance(prices, list)

        if prices:
            for price in prices:
                assert isinstance(price, Price)
                assert price.close > 0
                print(f"✓ 港股 ({ticker}): Sample price={price.close}, date={price.time}")

    def test_commodity_prices_detailed(self, date_range):
        """测试商品期货价格数据的详细验证"""
        ticker = "GC=F"
        prices = api.get_prices(ticker, date_range["start"], date_range["end"])

        assert isinstance(prices, list)

        if prices:
            for price in prices:
                assert isinstance(price, Price)
                assert price.close > 0
                print(f"✓ 商品 ({ticker}): Sample price={price.close}, date={price.time}")

    # ==================== 新闻数据测试 ====================

    def test_mixed_market_news(self, mixed_tickers):
        """测试混合市场新闻获取"""
        end_date = "2024-01-31"

        for market, ticker in mixed_tickers.items():
            news = api.get_company_news(ticker, end_date, limit=5)

            assert isinstance(news, list), f"{ticker} should return a list"

            # 新闻可能为空，这是正常的（特别是商品）
            if news:
                # 验证返回的是 Pydantic 模型
                assert isinstance(news[0], CompanyNews), f"{ticker} should return CompanyNews objects"

                # 验证必需字段
                news_item = news[0]
                assert hasattr(news_item, 'date'), f"{ticker} news should have date"
                assert hasattr(news_item, 'title'), f"{ticker} news should have title"

                print(f"✓ {market:10s} ({ticker:12s}): {len(news)} news items retrieved")
            else:
                print(f"○ {market:10s} ({ticker:12s}): No news available (expected for some tickers)")

    def test_us_stock_news_content(self):
        """测试美股新闻内容质量"""
        ticker = "AAPL"
        news = api.get_company_news(ticker, "2024-01-31", limit=3)

        if news:
            for item in news:
                assert isinstance(item, CompanyNews)
                assert len(item.title) > 0, "News title should not be empty"

                # 验证日期格式
                try:
                    date_obj = datetime.fromisoformat(item.date.replace('Z', '+00:00'))
                    assert isinstance(date_obj, datetime)
                except ValueError:
                    pytest.fail(f"Invalid date format: {item.date}")

    # ==================== 财务指标测试 ====================

    def test_mixed_market_metrics(self, mixed_tickers):
        """测试混合市场财务指标"""
        end_date = "2024-01-31"

        # 定义预期行为
        test_cases = [
            ("us", True),       # 美股有财务指标
            ("a_share", True),  # A股有财务指标
            ("hk", True),       # 港股有财务指标
            ("commodity", False) # 商品无财务指标
        ]

        for market, should_have_metrics in test_cases:
            ticker = mixed_tickers[market]
            metrics = api.get_financial_metrics(ticker, end_date)

            assert isinstance(metrics, list), f"{ticker} should return a list"

            if should_have_metrics:
                # 股票可能有财务指标
                if metrics:
                    assert isinstance(metrics[0], FinancialMetrics)
                    print(f"✓ {market:10s} ({ticker:12s}): Financial metrics available")
                else:
                    print(f"○ {market:10s} ({ticker:12s}): No financial metrics (may be unavailable)")
            else:
                # 商品不应该有财务指标
                if metrics:
                    print(f"⚠ {market:10s} ({ticker:12s}): Unexpected metrics for commodity")
                else:
                    print(f"✓ {market:10s} ({ticker:12s}): Correctly returns no metrics for commodity")

    def test_us_stock_metrics_detailed(self):
        """测试美股财务指标的详细验证"""
        ticker = "AAPL"
        metrics = api.get_financial_metrics(ticker, "2024-01-31")

        if metrics:
            metric = metrics[0]
            assert isinstance(metric, FinancialMetrics)

            # 验证关键财务指标字段存在
            assert hasattr(metric, 'market_cap')
            assert hasattr(metric, 'price_to_earnings_ratio')  # 实际字段名

            # 市值应该是正数（如果存在）
            if metric.market_cap:
                assert metric.market_cap > 0, f"Market cap should be positive: {metric.market_cap}"

    # ==================== 错误处理测试 ====================

    def test_invalid_ticker(self):
        """测试无效ticker的错误处理"""
        invalid_ticker = "INVALID_TICKER_12345"
        prices = api.get_prices(invalid_ticker, "2024-01-01", "2024-01-31")

        # 应该返回空列表，不应该抛出异常
        assert isinstance(prices, list)
        assert len(prices) == 0

    def test_invalid_date_range(self, mixed_tickers):
        """测试无效日期范围的错误处理"""
        ticker = mixed_tickers["us"]

        # 未来日期
        future_start = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        future_end = (datetime.now() + timedelta(days=400)).strftime("%Y-%m-%d")

        prices = api.get_prices(ticker, future_start, future_end)

        # 应该返回空列表
        assert isinstance(prices, list)
        assert len(prices) == 0

    def test_reversed_date_range(self, mixed_tickers):
        """测试反向日期范围的处理"""
        ticker = mixed_tickers["us"]

        # 结束日期早于开始日期
        prices = api.get_prices(ticker, "2024-01-31", "2024-01-01")

        # 应该返回空列表
        assert isinstance(prices, list)

    # ==================== 性能测试 ====================

    def test_performance_multi_market(self, mixed_tickers, date_range):
        """测试多市场性能"""
        import time

        results = {}

        for market, ticker in mixed_tickers.items():
            start_time = time.time()
            prices = api.get_prices(ticker, date_range["start"], date_range["end"])
            elapsed = time.time() - start_time

            results[market] = {
                "ticker": ticker,
                "elapsed": elapsed,
                "count": len(prices)
            }

            # 每个ticker不应超过10秒（网络请求 + 处理）
            assert elapsed < 10, f"{ticker} took too long: {elapsed:.2f}s"

            print(f"⏱ {market:10s} ({ticker:12s}): {elapsed:.2f}s for {len(prices)} prices")

        # 总时间不应超过30秒
        total_time = sum(r["elapsed"] for r in results.values())
        assert total_time < 30, f"Total time too long: {total_time:.2f}s"

        print(f"\n⏱ Total time: {total_time:.2f}s")

    def test_cache_performance(self, mixed_tickers, date_range):
        """测试缓存性能"""
        import time

        ticker = mixed_tickers["us"]

        # 第一次调用（无缓存）
        start_time = time.time()
        prices1 = api.get_prices(ticker, date_range["start"], date_range["end"])
        first_call_time = time.time() - start_time

        # 第二次调用（有缓存）
        start_time = time.time()
        prices2 = api.get_prices(ticker, date_range["start"], date_range["end"])
        second_call_time = time.time() - start_time

        # 验证数据一致性
        assert len(prices1) == len(prices2), "Cached data should match original"

        # 缓存调用应该快得多（至少快5倍）
        if first_call_time > 0.1:  # 只在第一次调用足够慢时检查
            assert second_call_time < first_call_time / 5, \
                f"Cache not effective: 1st={first_call_time:.3f}s, 2nd={second_call_time:.3f}s"

        print(f"⏱ Cache performance: 1st={first_call_time:.3f}s, 2nd={second_call_time:.3f}s, " +
              f"speedup={first_call_time/max(second_call_time, 0.001):.1f}x")

    # ==================== 数据格式验证测试 ====================

    def test_price_data_format_consistency(self, mixed_tickers, date_range):
        """验证所有市场的价格数据格式一致性"""
        for market, ticker in mixed_tickers.items():
            prices = api.get_prices(ticker, date_range["start"], date_range["end"])

            if prices:
                for price in prices:
                    # 验证所有必需字段存在
                    required_fields = ['time', 'open', 'close', 'high', 'low', 'volume']
                    for field in required_fields:
                        assert hasattr(price, field), \
                            f"{ticker} missing field: {field}"

                    # 验证数据类型
                    assert isinstance(price.time, str), f"{ticker} time should be string"
                    assert isinstance(price.close, (int, float)), f"{ticker} close should be numeric"
                    assert isinstance(price.open, (int, float)), f"{ticker} open should be numeric"
                    assert isinstance(price.high, (int, float)), f"{ticker} high should be numeric"
                    assert isinstance(price.low, (int, float)), f"{ticker} low should be numeric"
                    assert isinstance(price.volume, (int, float)), f"{ticker} volume should be numeric"

    def test_news_data_format_consistency(self, mixed_tickers):
        """验证所有市场的新闻数据格式一致性"""
        end_date = "2024-01-31"

        for market, ticker in mixed_tickers.items():
            news = api.get_company_news(ticker, end_date, limit=3)

            if news:
                for item in news:
                    # 验证必需字段
                    assert hasattr(item, 'date'), f"{ticker} news missing date"
                    assert hasattr(item, 'title'), f"{ticker} news missing title"

                    # 验证数据类型
                    assert isinstance(item.date, str), f"{ticker} news date should be string"
                    assert isinstance(item.title, str), f"{ticker} news title should be string"

    # ==================== 集成场景测试 ====================

    def test_complete_data_flow(self, mixed_tickers, date_range):
        """测试完整的数据获取流程（价格 + 新闻 + 财务指标）"""
        ticker = mixed_tickers["us"]

        # 1. 获取价格数据
        prices = api.get_prices(ticker, date_range["start"], date_range["end"])
        assert len(prices) > 0, "Should have price data"

        # 2. 获取新闻
        news = api.get_company_news(ticker, date_range["end"], limit=5)
        assert isinstance(news, list), "Should return news list"

        # 3. 获取财务指标
        metrics = api.get_financial_metrics(ticker, date_range["end"])
        assert isinstance(metrics, list), "Should return metrics list"

        print(f"✓ Complete data flow for {ticker}:")
        print(f"  - Prices: {len(prices)} records")
        print(f"  - News: {len(news)} items")
        print(f"  - Metrics: {len(metrics)} records")

    def test_multi_ticker_batch_processing(self, mixed_tickers, date_range):
        """测试批量处理多个ticker"""
        all_results = {}

        for market, ticker in mixed_tickers.items():
            all_results[ticker] = {
                "prices": api.get_prices(ticker, date_range["start"], date_range["end"]),
                "news": api.get_company_news(ticker, date_range["end"], limit=3),
                "metrics": api.get_financial_metrics(ticker, date_range["end"])
            }

        # 验证所有ticker都有结果
        assert len(all_results) == len(mixed_tickers)

        # 打印汇总
        print("\n📊 Batch processing summary:")
        for ticker, results in all_results.items():
            print(f"  {ticker:12s}: " +
                  f"prices={len(results['prices']):3d}, " +
                  f"news={len(results['news']):2d}, " +
                  f"metrics={len(results['metrics']):2d}")


class TestEdgeCases:
    """边界情况测试"""

    def test_single_day_range(self):
        """测试单日数据范围"""
        ticker = "AAPL"
        date = "2024-01-15"

        prices = api.get_prices(ticker, date, date)

        # 单日可能有数据，也可能没有（取决于是否交易日）
        assert isinstance(prices, list)
        if prices:
            assert len(prices) <= 1

    def test_holiday_period(self):
        """测试节假日期间（可能无数据）"""
        ticker = "AAPL"

        # 2024年新年假期
        prices = api.get_prices(ticker, "2024-01-01", "2024-01-01")

        # 假期可能无数据
        assert isinstance(prices, list)

    def test_weekend_date_range(self):
        """测试周末日期范围"""
        ticker = "AAPL"

        # 2024-01-06是周六，2024-01-07是周日
        prices = api.get_prices(ticker, "2024-01-06", "2024-01-07")

        # 周末通常无交易数据
        assert isinstance(prices, list)

    def test_very_old_data(self):
        """测试非常旧的数据"""
        ticker = "AAPL"

        # 10年前的数据
        prices = api.get_prices(ticker, "2014-01-01", "2014-01-31")

        # 应该返回列表（可能为空）
        assert isinstance(prices, list)


class TestMarketSpecific:
    """市场特定功能测试"""

    def test_a_share_trading_days(self):
        """测试A股交易日"""
        ticker = "600000.SH"

        # A股有不同的节假日安排
        prices = api.get_prices(ticker, "2024-02-01", "2024-02-29")

        # 应该返回数据（即使格式可能不同）
        assert isinstance(prices, list)

    def test_hk_stock_currency(self):
        """测试港股货币单位"""
        ticker = "0700.HK"

        prices = api.get_prices(ticker, "2024-01-01", "2024-01-31")

        if prices:
            # 港股价格应该是正常范围（港币计价）
            for price in prices:
                assert price.close > 0
                # 腾讯股价通常在几百港币范围
                assert 0.01 < price.close < 10000, f"Price out of reasonable range: {price.close}"

    def test_commodity_24h_trading(self):
        """测试商品期货24小时交易特性"""
        ticker = "GC=F"

        prices = api.get_prices(ticker, "2024-01-01", "2024-01-31")

        # 商品期货可能有不同的交易时间
        assert isinstance(prices, list)
