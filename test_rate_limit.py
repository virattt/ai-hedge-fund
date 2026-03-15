#!/usr/bin/env python
"""Test script to verify anti-rate-limit improvements."""

import logging
import sys
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from src.markets.sources.yfinance_source import YFinanceSource


def test_yfinance_rate_limit():
    """Test YFinance with anti-rate-limit improvements."""
    print("\n" + "=" * 80)
    print("Testing YFinance Anti-Rate-Limit Improvements")
    print("=" * 80 + "\n")

    # Initialize YFinance source
    yf_source = YFinanceSource()

    # Test tickers
    test_cases = [
        ("3690.HK", "Meituan (Hong Kong)"),
        ("AAPL", "Apple (US)"),
        ("0700.HK", "Tencent (Hong Kong)"),
    ]

    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    end_str = end_date.strftime("%Y-%m-%d")
    start_str = start_date.strftime("%Y-%m-%d")

    results = []

    for ticker, name in test_cases:
        print(f"\n{'─' * 80}")
        print(f"Testing: {ticker} ({name})")
        print(f"Date range: {start_str} to {end_str}")
        print(f"{'─' * 80}\n")

        try:
            # Test price data
            print("📊 Fetching price data...")
            prices = yf_source.get_prices(ticker, start_str, end_str)

            if prices:
                print(f"✅ SUCCESS: Retrieved {len(prices)} price records")
                results.append((ticker, "Prices", "✅ Success", len(prices)))
            else:
                print(f"⚠️  WARNING: No price data available")
                results.append((ticker, "Prices", "⚠️  No data", 0))

            # Test financial metrics
            print("\n💰 Fetching financial metrics...")
            metrics = yf_source.get_financial_metrics(ticker, end_str)

            if metrics:
                available_metrics = sum(1 for v in metrics.values() if v is not None)
                print(f"✅ SUCCESS: Retrieved {available_metrics} financial metrics")
                results.append((ticker, "Metrics", "✅ Success", available_metrics))
            else:
                print(f"⚠️  WARNING: No financial metrics available")
                results.append((ticker, "Metrics", "⚠️  No data", 0))

            # Test news
            print("\n📰 Fetching company news...")
            news = yf_source.get_company_news(ticker, end_str, start_str, limit=5)

            if news:
                print(f"✅ SUCCESS: Retrieved {len(news)} news items")
                results.append((ticker, "News", "✅ Success", len(news)))
            else:
                print(f"⚠️  WARNING: No news available")
                results.append((ticker, "News", "⚠️  No data", 0))

        except Exception as e:
            print(f"❌ ERROR: {e}")
            results.append((ticker, "All", f"❌ Error: {e}", 0))

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80 + "\n")

    print(f"{'Ticker':<15} {'Type':<15} {'Status':<20} {'Count':<10}")
    print("─" * 80)
    for ticker, data_type, status, count in results:
        print(f"{ticker:<15} {data_type:<15} {status:<20} {count:<10}")

    # Overall success rate
    success_count = sum(1 for _, _, status, _ in results if "Success" in status)
    total_count = len(results)
    success_rate = (success_count / total_count * 100) if total_count > 0 else 0

    print("\n" + "=" * 80)
    print(f"Overall Success Rate: {success_count}/{total_count} ({success_rate:.1f}%)")
    print("=" * 80 + "\n")

    if success_rate >= 50:
        print("✅ Anti-rate-limit improvements are working!")
        return 0
    else:
        print("⚠️  Some requests still failed. Consider:")
        print("   - Waiting longer between requests")
        print("   - Using a VPN or proxy")
        print("   - Checking your network connection")
        return 1


if __name__ == "__main__":
    sys.exit(test_yfinance_rate_limit())
