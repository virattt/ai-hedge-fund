#!/usr/bin/env python3
"""
Validation script for AKShare HK financial data enhancement.

This script demonstrates the improvement in data completeness
before and after the enhancement.
"""
import sys
sys.path.insert(0, '/Users/luobotao/.openclaw/workspace/ai-hedge-fund')

from src.markets.sources.akshare_source import AKShareSource
from src.agents.warren_buffett import analyze_fundamentals
from src.data.models import FinancialMetrics
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)

def validate_ticker(ticker: str):
    """Validate data completeness for a single ticker."""
    print(f"\n{'='*80}")
    print(f"Validating Enhanced AKShare HK Data: {ticker}")
    print(f"{'='*80}\n")

    # Get data from AKShare
    source = AKShareSource()
    metrics_dict = source.get_financial_metrics(ticker, end_date="2024-12-31")

    if not metrics_dict:
        print(f"❌ Failed to retrieve metrics for {ticker}")
        return False

    print(f"✅ Successfully retrieved metrics for {ticker}\n")

    # Define critical fields that analysts require
    critical_fields = {
        "Valuation": ["price_to_earnings_ratio", "price_to_book_ratio", "market_cap"],
        "Profitability": ["return_on_equity", "net_margin", "operating_margin", "gross_margin"],
        "Liquidity": ["current_ratio"],
        "Leverage": ["debt_to_equity"],
        "Growth": ["revenue_growth", "earnings_growth"],
        "Financial Data": ["revenue", "net_income"],
        "Per Share": ["earnings_per_share", "book_value_per_share"],
    }

    # Check completeness
    total_fields = sum(len(fields) for fields in critical_fields.values())
    available_fields = 0
    estimated_fields = 0

    print("Field Availability by Category:")
    print("-" * 80)

    for category, fields in critical_fields.items():
        print(f"\n{category}:")
        for field in fields:
            value = metrics_dict.get(field)
            if value is not None:
                available_fields += 1
                # Check if estimated
                is_estimated = field in ["operating_margin", "gross_margin", "current_ratio", "debt_to_equity"]
                if is_estimated:
                    estimated_fields += 1
                    print(f"  ✅ {field:30s} = {value:.4f} (estimated)")
                else:
                    print(f"  ✅ {field:30s} = {value:.4f}")
            else:
                print(f"  ❌ {field:30s} = MISSING")

    # Calculate statistics
    completeness = (available_fields / total_fields) * 100

    print("\n" + "=" * 80)
    print("Data Completeness Summary:")
    print("-" * 80)
    print(f"Total critical fields:     {total_fields}")
    print(f"Available fields:          {available_fields}")
    print(f"  - Direct from API:       {available_fields - estimated_fields}")
    print(f"  - Estimated:             {estimated_fields}")
    print(f"Missing fields:            {total_fields - available_fields}")
    print(f"Completeness:              {completeness:.1f}%")
    print("-" * 80)

    # Test with Warren Buffett's analysis
    print("\nTesting with Warren Buffett's Fundamental Analysis:")
    print("-" * 80)

    try:
        metrics_model = FinancialMetrics(**metrics_dict)
        result = analyze_fundamentals([metrics_model])

        print(f"Score: {result['score']}/7 ({result['score']/7*100:.1f}%)")
        print(f"Details: {result['details']}")

        # Check for success
        if "Insufficient" in result['details'] or result['score'] == 0:
            print("\n❌ Analysis failed - insufficient data")
            success = False
        else:
            print("\n✅ Analysis succeeded - sufficient data provided")
            success = True

    except Exception as e:
        print(f"\n❌ Analysis error: {e}")
        success = False

    print("=" * 80)

    return success and completeness == 100.0


def main():
    """Main validation routine."""
    print("\n" + "=" * 80)
    print("AKShare HK Financial Data Enhancement Validation")
    print("=" * 80)

    # Test with multiple tickers
    test_tickers = [
        ("00700", "Tencent Holdings"),
        ("00941", "China Mobile"),
        ("00388", "Hong Kong Exchanges"),
    ]

    results = {}
    for ticker, name in test_tickers:
        print(f"\n{'#' * 80}")
        print(f"# Testing: {ticker} - {name}")
        print(f"{'#' * 80}")

        results[ticker] = validate_ticker(ticker)

    # Final summary
    print("\n\n" + "=" * 80)
    print("FINAL VALIDATION SUMMARY")
    print("=" * 80)

    for ticker, name in test_tickers:
        status = "✅ PASS" if results[ticker] else "❌ FAIL"
        print(f"{ticker} ({name:30s}): {status}")

    success_count = sum(results.values())
    total_count = len(results)

    print("-" * 80)
    print(f"Success Rate: {success_count}/{total_count} ({success_count/total_count*100:.0f}%)")
    print("=" * 80)

    if success_count == total_count:
        print("\n✅✅✅ ALL TESTS PASSED - Enhancement successful! ✅✅✅\n")
        return 0
    else:
        print(f"\n❌ {total_count - success_count} test(s) failed\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
