#!/usr/bin/env python3
"""Test script to verify parallel data source requests and URL logging."""
import logging
import sys
from datetime import datetime, timedelta

# Setup logging to see all details
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Import the CN stock adapter
from src.markets.cn_stock import CNStockAdapter

def main():
    """Test CN stock adapter with parallel requests."""
    print("=" * 80)
    print("Testing CN Stock Adapter - Parallel Requests & URL Logging")
    print("=" * 80)

    # Create adapter
    adapter = CNStockAdapter()

    # Test ticker
    ticker = "000001.SZ"  # Ping An Bank

    # Date range (last 30 days)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    print(f"\nTesting ticker: {ticker}")
    print(f"Date range: {start_date} to {end_date}")
    print("\n" + "=" * 80)
    print("FETCHING PRICES (should be parallel)")
    print("=" * 80 + "\n")

    # Test get_prices (should fetch from all sources in parallel)
    prices = adapter.get_prices(ticker, start_date, end_date)

    print("\n" + "=" * 80)
    print(f"RESULT: Got {len(prices)} price records")
    print("=" * 80)

    if prices:
        print(f"\nFirst price: {prices[0]}")
        print(f"Last price: {prices[-1]}")

    print("\n" + "=" * 80)
    print("FETCHING FINANCIAL METRICS (should be parallel)")
    print("=" * 80 + "\n")

    # Test get_financial_metrics (should fetch from all sources in parallel)
    metrics = adapter.get_financial_metrics(ticker, end_date)

    print("\n" + "=" * 80)
    print(f"RESULT: Got financial metrics: {metrics is not None}")
    print("=" * 80)

    if metrics:
        print(f"\nMetrics preview:")
        for key in ['market_cap', 'price_to_earnings_ratio', 'price_to_book_ratio', 'return_on_equity']:
            if key in metrics:
                print(f"  {key}: {metrics[key]}")

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print("\nExpected behavior:")
    print("1. ✓ All data sources should request in parallel (concurrent logs)")
    print("2. ✓ Each source should log its request URL with 📡 emoji")
    print("3. ✓ Sina and Eastmoney should successfully fetch data")
    print("4. ✓ Request method (GET) and full URL with parameters should be visible")

if __name__ == "__main__":
    main()
