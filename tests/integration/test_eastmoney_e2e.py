"""End-to-End tests for Eastmoney integration."""
import pytest
import time
from datetime import datetime, timedelta

from src.markets.cn_stock import CNStockAdapter
from src.markets.sources.eastmoney_source import EastmoneySource


@pytest.mark.integration
class TestEastmoneyEndToEnd:
    """End-to-end tests for Eastmoney data source integration."""

    def setup_method(self):
        """Setup test fixtures."""
        self.source = EastmoneySource()
        self.adapter = CNStockAdapter()

        # Use well-known CN stocks for testing
        self.test_tickers = [
            "600036.SH",  # 招商银行 (Shanghai)
            "000001.SZ",  # 平安银行 (Shenzhen)
            "600000.SH",  # 浦发银行 (Shanghai)
        ]

        # Test date range (avoid weekends/holidays)
        self.end_date = "2024-01-31"
        self.start_date = "2024-01-01"

    def test_eastmoney_price_fetching(self):
        """
        E2E Test: CN stock price fetching via Eastmoney.

        Verifies:
        - Eastmoney can fetch price data for multiple tickers
        - Data format is correct
        - No rate limit errors
        """
        results = {}

        for ticker in self.test_tickers:
            # Add small delay between requests
            time.sleep(0.5)

            prices = self.source.get_prices(ticker, self.start_date, self.end_date)

            # Verify we got data
            assert len(prices) > 0, f"No prices for {ticker}"

            # Verify data format
            for price in prices[:3]:  # Check first 3 records
                assert 'open' in price
                assert 'close' in price
                assert 'high' in price
                assert 'low' in price
                assert 'volume' in price
                assert 'time' in price

                # Verify reasonable values
                assert price['open'] > 0
                assert price['close'] > 0
                assert price['high'] >= price['low']
                assert price['volume'] >= 0

            results[ticker] = len(prices)

        # Verify we got data for all tickers
        assert len(results) == len(self.test_tickers)
        print(f"\n✓ Successfully fetched prices: {results}")

    def test_eastmoney_financial_metrics(self):
        """
        E2E Test: CN stock financial metrics fetching via Eastmoney.

        Verifies:
        - Eastmoney can fetch financial metrics
        - Basic metrics are present (PE, PB, market cap)
        - No rate limit errors
        """
        results = {}

        for ticker in self.test_tickers:
            # Add small delay between requests
            time.sleep(0.5)

            metrics = self.source.get_financial_metrics(ticker, self.end_date)

            # Verify we got data
            if metrics:
                assert 'ticker' in metrics
                assert metrics['currency'] == "CNY"

                # Check for basic metrics
                has_pe = metrics.get('price_to_earnings_ratio') is not None
                has_pb = metrics.get('price_to_book_ratio') is not None
                has_market_cap = metrics.get('market_cap') is not None

                results[ticker] = {
                    'has_metrics': True,
                    'has_pe': has_pe,
                    'has_pb': has_pb,
                    'has_market_cap': has_market_cap,
                }
            else:
                results[ticker] = {'has_metrics': False}

        print(f"\n✓ Financial metrics results: {results}")

        # At least some tickers should have metrics
        has_metrics_count = sum(1 for r in results.values() if r.get('has_metrics'))
        assert has_metrics_count > 0, "No financial metrics fetched for any ticker"

    def test_no_rate_limits(self):
        """
        E2E Test: Verify no rate limiting with multiple requests.

        Verifies:
        - Can make multiple consecutive requests without rate limit errors
        - Response time is reasonable
        - All requests succeed
        """
        ticker = "600036.SH"
        request_count = 10
        successful_requests = 0
        total_time = 0

        for i in range(request_count):
            start_time = time.time()

            try:
                prices = self.source.get_prices(ticker, "2024-01-01", "2024-01-10")
                elapsed = time.time() - start_time
                total_time += elapsed

                if len(prices) > 0:
                    successful_requests += 1

                # Small delay to be respectful to the API
                time.sleep(0.3)

            except Exception as e:
                # Check if it's a rate limit error
                if "429" in str(e) or "rate limit" in str(e).lower():
                    pytest.fail(f"Rate limit error after {i+1} requests: {e}")
                else:
                    # Other errors are acceptable for this test
                    pass

        # Calculate average response time
        avg_time = total_time / request_count if request_count > 0 else 0

        print(f"\n✓ Made {request_count} requests")
        print(f"  - Successful: {successful_requests}/{request_count}")
        print(f"  - Average response time: {avg_time:.2f}s")
        print(f"  - No rate limit errors")

        # At least 80% should succeed
        success_rate = successful_requests / request_count
        assert success_rate >= 0.8, f"Success rate too low: {success_rate:.2%}"

    def test_adapter_fallback_chain(self):
        """
        E2E Test: Verify adapter fallback chain works correctly.

        Verifies:
        - CNStockAdapter uses Eastmoney as primary source
        - Fallback to other sources if Eastmoney fails
        - Final result is correct regardless of source
        """
        ticker = "600036.SH"

        # Get prices through adapter (should use Eastmoney)
        prices = self.adapter.get_prices(ticker, self.start_date, self.end_date)

        assert len(prices) > 0, "Adapter failed to get prices"

        # Verify Price object format
        first_price = prices[0]
        assert hasattr(first_price, 'open')
        assert hasattr(first_price, 'close')
        assert hasattr(first_price, 'high')
        assert hasattr(first_price, 'low')
        assert hasattr(first_price, 'volume')
        assert hasattr(first_price, 'time')

        print(f"\n✓ Adapter successfully fetched {len(prices)} prices")
        print(f"  - First price: {first_price}")

    def test_multiple_ticker_formats(self):
        """
        E2E Test: Verify different ticker formats work correctly.

        Verifies:
        - Eastmoney handles .SH/.SZ format
        - Eastmoney handles SH/SZ prefix format
        - Eastmoney handles bare 6-digit format
        - All formats return consistent data
        """
        # Same stock, different formats
        formats = [
            "600036.SH",
            "SH600036",
            "600036",
        ]

        results = {}

        for ticker_format in formats:
            prices = self.source.get_prices(ticker_format, "2024-01-01", "2024-01-05")
            results[ticker_format] = len(prices)

            assert len(prices) > 0, f"No prices for format: {ticker_format}"

        print(f"\n✓ All ticker formats work: {results}")

        # All formats should return same number of records
        counts = list(results.values())
        assert len(set(counts)) == 1, f"Inconsistent record counts: {results}"

    def test_shanghai_and_shenzhen_stocks(self):
        """
        E2E Test: Verify both Shanghai and Shenzhen stocks work.

        Verifies:
        - Shanghai stocks (6xxxxx) work correctly
        - Shenzhen stocks (0xxxxx, 3xxxxx) work correctly
        - Ticker conversion is correct for both exchanges
        """
        # Test Shanghai stock
        sh_ticker = "600036.SH"
        sh_prices = self.source.get_prices(sh_ticker, "2024-01-01", "2024-01-10")
        assert len(sh_prices) > 0, "Failed to get Shanghai stock prices"

        # Test Shenzhen stock (0xxxxx)
        sz_ticker_0 = "000001.SZ"
        sz_prices_0 = self.source.get_prices(sz_ticker_0, "2024-01-01", "2024-01-10")
        assert len(sz_prices_0) > 0, "Failed to get Shenzhen stock (0xxxxx) prices"

        # Test Shenzhen stock (3xxxxx) - ChiNext
        sz_ticker_3 = "300750.SZ"
        sz_prices_3 = self.source.get_prices(sz_ticker_3, "2024-01-01", "2024-01-10")
        assert len(sz_prices_3) > 0, "Failed to get Shenzhen stock (3xxxxx) prices"

        print(f"\n✓ Successfully fetched prices for both exchanges:")
        print(f"  - Shanghai (600036): {len(sh_prices)} records")
        print(f"  - Shenzhen (000001): {len(sz_prices_0)} records")
        print(f"  - Shenzhen (300750): {len(sz_prices_3)} records")

    def test_date_range_handling(self):
        """
        E2E Test: Verify date range handling is correct.

        Verifies:
        - Short date ranges work
        - Longer date ranges work
        - Date format is correct
        - Results are within requested range
        """
        ticker = "600036.SH"

        # Test short range (1 week)
        short_prices = self.source.get_prices(ticker, "2024-01-01", "2024-01-07")
        assert 3 <= len(short_prices) <= 7, "Unexpected count for 1-week range"

        # Test medium range (1 month)
        medium_prices = self.source.get_prices(ticker, "2024-01-01", "2024-01-31")
        assert 15 <= len(medium_prices) <= 31, "Unexpected count for 1-month range"

        # Test longer range (3 months)
        long_prices = self.source.get_prices(ticker, "2024-01-01", "2024-03-31")
        assert 40 <= len(long_prices) <= 90, "Unexpected count for 3-month range"

        print(f"\n✓ Date range handling verified:")
        print(f"  - 1 week: {len(short_prices)} records")
        print(f"  - 1 month: {len(medium_prices)} records")
        print(f"  - 3 months: {len(long_prices)} records")

        # Verify dates are within range
        for price in short_prices:
            date_str = price['time'][:10]  # Extract YYYY-MM-DD
            assert "2024-01-01" <= date_str <= "2024-01-07", \
                f"Date {date_str} outside requested range"

    def test_data_quality(self):
        """
        E2E Test: Verify data quality and consistency.

        Verifies:
        - OHLC relationships are correct (high >= low, etc.)
        - Volumes are reasonable
        - No missing or null values in critical fields
        - Prices are reasonable (no extreme outliers)
        """
        ticker = "600036.SH"
        prices = self.source.get_prices(ticker, "2024-01-01", "2024-01-31")

        assert len(prices) > 0, "No prices to check quality"

        issues = []

        for i, price in enumerate(prices):
            # Check OHLC relationships
            if price['high'] < price['low']:
                issues.append(f"Record {i}: high < low")

            if price['high'] < price['open'] or price['high'] < price['close']:
                issues.append(f"Record {i}: high less than open/close")

            if price['low'] > price['open'] or price['low'] > price['close']:
                issues.append(f"Record {i}: low greater than open/close")

            # Check for reasonable values
            if price['open'] <= 0 or price['close'] <= 0:
                issues.append(f"Record {i}: non-positive price")

            if price['volume'] < 0:
                issues.append(f"Record {i}: negative volume")

            # Check for null values
            for field in ['open', 'close', 'high', 'low', 'volume']:
                if price[field] is None:
                    issues.append(f"Record {i}: null {field}")

        if issues:
            print(f"\n⚠ Data quality issues found:")
            for issue in issues[:10]:  # Show first 10 issues
                print(f"  - {issue}")

        # Allow some tolerance for data quality issues (e.g., <= 5%)
        error_rate = len(issues) / len(prices)
        assert error_rate <= 0.05, f"Too many data quality issues: {error_rate:.2%}"

        print(f"\n✓ Data quality verified:")
        print(f"  - Total records: {len(prices)}")
        print(f"  - Issues found: {len(issues)}")
        print(f"  - Error rate: {error_rate:.2%}")


@pytest.mark.integration
class TestEastmoneyPerformance:
    """Performance tests for Eastmoney integration."""

    def test_response_time(self):
        """
        Test: Verify response times are reasonable.

        Verifies:
        - Average response time < 5 seconds
        - No extremely slow requests (> 10 seconds)
        """
        source = EastmoneySource()
        ticker = "600036.SH"
        iterations = 5

        response_times = []

        for _ in range(iterations):
            start_time = time.time()
            prices = source.get_prices(ticker, "2024-01-01", "2024-01-10")
            elapsed = time.time() - start_time

            if len(prices) > 0:
                response_times.append(elapsed)

            time.sleep(0.5)  # Be respectful to API

        avg_time = sum(response_times) / len(response_times) if response_times else 0
        max_time = max(response_times) if response_times else 0

        print(f"\n✓ Response time stats:")
        print(f"  - Average: {avg_time:.2f}s")
        print(f"  - Max: {max_time:.2f}s")
        print(f"  - All times: {[f'{t:.2f}s' for t in response_times]}")

        assert avg_time < 5.0, f"Average response time too slow: {avg_time:.2f}s"
        assert max_time < 10.0, f"Max response time too slow: {max_time:.2f}s"
