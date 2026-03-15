#!/usr/bin/env python3
"""Test HK stock data fetching with URL logging."""
import logging
import sys

# Configure logging to show INFO level
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

from src.markets.hk_stock import HKStockAdapter

def main():
    print("=" * 80)
    print("Testing HK Stock Adapter - URL Logging")
    print("=" * 80)

    adapter = HKStockAdapter()

    ticker = "3690.HK"  # 美团
    start_date = "2026-02-01"
    end_date = "2026-03-15"

    print(f"\nTesting ticker: {ticker}")
    print(f"Date range: {start_date} to {end_date}\n")

    print("=" * 80)
    print("FETCHING PRICES")
    print("=" * 80 + "\n")

    prices = adapter.get_prices(ticker, start_date, end_date)

    print(f"\n{'=' * 80}")
    print(f"RESULT: Got {len(prices)} price records")
    print("=" * 80)

    if prices:
        print(f"\nFirst price: {prices[0]}")
        print(f"Last price: {prices[-1]}")

    print("\n" + "=" * 80)
    print("FETCHING FINANCIAL METRICS")
    print("=" * 80 + "\n")

    metrics = adapter.get_financial_metrics(ticker, end_date)

    print(f"\n{'=' * 80}")
    print(f"RESULT: Got financial metrics: {metrics is not None}")
    print("=" * 80)

    if metrics:
        print(f"\nMetrics preview:")
        for key in ['market_cap', 'price_to_earnings_ratio', 'price_to_book_ratio']:
            if key in metrics:
                print(f"  {key}: {metrics[key]}")

if __name__ == "__main__":
    main()
