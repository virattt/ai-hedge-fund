#!/usr/bin/env python3
"""
Test script for Yahoo Finance API implementation.

Tests all major functions to ensure they work correctly.
"""

import os
import sys

# Set environment variable before importing
os.environ["USE_YAHOO_FINANCE"] = "true"

from src.tools.api import (
    get_prices,
    get_financial_metrics,
    search_line_items,
    get_insider_trades,
    get_company_news,
    get_market_cap,
)

def test_prices():
    """Test price data fetching."""
    print("\n" + "="*60)
    print("Testing: get_prices()")
    print("="*60)

    try:
        prices = get_prices("AAPL", "2024-01-01", "2024-01-31")
        print(f"✅ Successfully fetched {len(prices)} price records")

        if prices:
            print(f"\nSample (first record):")
            p = prices[0]
            print(f"  Date: {p.time}")
            print(f"  Open: ${p.open:.2f}")
            print(f"  Close: ${p.close:.2f}")
            print(f"  Volume: {p.volume:,}")
        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_financial_metrics():
    """Test financial metrics fetching."""
    print("\n" + "="*60)
    print("Testing: get_financial_metrics()")
    print("="*60)

    try:
        metrics = get_financial_metrics("AAPL", "2024-12-31", period="ttm", limit=1)
        print(f"✅ Successfully fetched {len(metrics)} metrics records")

        if metrics:
            m = metrics[0]
            print(f"\nSample metrics for {m.ticker}:")
            print(f"  Market Cap: ${m.market_cap:,.0f}" if m.market_cap else "  Market Cap: N/A")
            print(f"  P/E Ratio: {m.price_to_earnings_ratio:.2f}" if m.price_to_earnings_ratio else "  P/E Ratio: N/A")
            print(f"  ROE: {m.return_on_equity*100:.2f}%" if m.return_on_equity else "  ROE: N/A")
            print(f"  Debt/Equity: {m.debt_to_equity:.2f}" if m.debt_to_equity else "  Debt/Equity: N/A")
        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_line_items():
    """Test line items search."""
    print("\n" + "="*60)
    print("Testing: search_line_items()")
    print("="*60)

    try:
        line_items = search_line_items(
            "AAPL",
            ["revenue", "net_income", "free_cash_flow", "total_debt"],
            "2024-12-31",
            period="annual",
            limit=2
        )
        print(f"✅ Successfully fetched {len(line_items)} periods")

        if line_items:
            for idx, item in enumerate(line_items):
                print(f"\nPeriod {idx + 1} ({item.report_period}):")
                print(f"  Revenue: ${getattr(item, 'revenue', 0):,.0f}" if hasattr(item, 'revenue') and getattr(item, 'revenue') else "  Revenue: N/A")
                print(f"  Net Income: ${getattr(item, 'net_income', 0):,.0f}" if hasattr(item, 'net_income') and getattr(item, 'net_income') else "  Net Income: N/A")
                print(f"  Free Cash Flow: ${getattr(item, 'free_cash_flow', 0):,.0f}" if hasattr(item, 'free_cash_flow') and getattr(item, 'free_cash_flow') else "  Free Cash Flow: N/A")
        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_insider_trades():
    """Test insider trades (should return empty list)."""
    print("\n" + "="*60)
    print("Testing: get_insider_trades()")
    print("="*60)

    try:
        trades = get_insider_trades("AAPL", "2024-12-31", limit=10)
        print(f"✅ Returned {len(trades)} trades (expected 0 for Yahoo Finance)")

        if len(trades) == 0:
            print("⚠️  Note: Insider trading data not available in Yahoo Finance")
        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_company_news():
    """Test company news fetching."""
    print("\n" + "="*60)
    print("Testing: get_company_news()")
    print("="*60)

    try:
        news = get_company_news("AAPL", "2024-12-31", limit=5)
        print(f"✅ Successfully fetched {len(news)} news articles")

        if news:
            print(f"\nSample (first article):")
            n = news[0]
            print(f"  Title: {n.title[:80]}...")
            print(f"  Source: {n.source}")
            print(f"  Date: {n.date}")
            print(f"  Sentiment: {n.sentiment or 'N/A (not available in Yahoo Finance)'}")
        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_market_cap():
    """Test market cap fetching."""
    print("\n" + "="*60)
    print("Testing: get_market_cap()")
    print("="*60)

    try:
        market_cap = get_market_cap("AAPL", "2024-12-31")
        print(f"✅ Market Cap: ${market_cap:,.0f}" if market_cap else "⚠️  Market Cap: N/A")
        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def main():
    """Run all tests."""
    print("\n" + "🚀" * 30)
    print("Yahoo Finance API Test Suite")
    print("🚀" * 30)

    tests = [
        ("Price Data", test_prices),
        ("Financial Metrics", test_financial_metrics),
        ("Line Items", test_line_items),
        ("Insider Trades", test_insider_trades),
        ("Company News", test_company_news),
        ("Market Cap", test_market_cap),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} test crashed: {str(e)}")
            results.append((test_name, False))

    # Print summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}  {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Yahoo Finance API is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
