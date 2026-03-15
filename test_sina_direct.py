#!/usr/bin/env python3
"""Direct test of SinaFinance source."""
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,  # Use DEBUG to see all logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

from src.markets.sources.sina_finance_source import SinaFinanceSource

def main():
    print("Testing SinaFinance directly")
    print("=" * 80)

    source = SinaFinanceSource()

    ticker = "000001.SZ"
    start_date = "2026-02-13"
    end_date = "2026-03-15"

    print(f"\nTesting ticker: {ticker}")
    print(f"Date range: {start_date} to {end_date}\n")

    prices = source.get_prices(ticker, start_date, end_date)

    print(f"\nResult: {len(prices)} prices")
    if prices:
        print(f"First: {prices[0]}")
        print(f"Last: {prices[-1]}")

if __name__ == "__main__":
    main()
