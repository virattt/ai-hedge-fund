"""
Demo script for multi-source data integration.

This script demonstrates:
1. Fetching data from CN and HK markets
2. Multi-source validation
3. Confidence scoring
4. Fallback mechanisms
"""

import logging
from datetime import datetime, timedelta

from src.markets.cn_stock import CNStockAdapter
from src.markets.hk_stock import HKStockAdapter
from src.data.validation import DataValidator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def demo_cn_stock():
    """Demonstrate CN stock data fetching."""
    logger.info("=" * 60)
    logger.info("Demo 1: China A-Share Stock Data")
    logger.info("=" * 60)

    # Create CN stock adapter
    adapter = CNStockAdapter()

    # Test ticker normalization
    test_tickers = ["SH600000", "000001", "1"]
    logger.info("\nTicker Normalization:")
    for ticker in test_tickers:
        normalized = adapter.normalize_ticker(ticker)
        exchange = adapter.detect_exchange(normalized)
        full = adapter.get_full_ticker(normalized)
        logger.info(f"  {ticker:12} -> {normalized} ({exchange}) -> {full}")

    # Get price data for Ping An Bank (000001)
    ticker = "000001"
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    logger.info(f"\nFetching prices for {ticker} from {start_date} to {end_date}...")

    try:
        prices = adapter.get_prices(ticker, start_date, end_date)
        if prices:
            logger.info(f"Retrieved {len(prices)} price records")
            logger.info(f"Latest price: Open={prices[-1].open}, Close={prices[-1].close}")
        else:
            logger.warning("No price data available")
    except Exception as e:
        logger.error(f"Error fetching prices: {e}")

    # Get financial metrics
    logger.info(f"\nFetching financial metrics for {ticker}...")
    try:
        metrics = adapter.get_financial_metrics(ticker, end_date)
        if metrics:
            logger.info("Financial metrics retrieved:")
            logger.info(f"  PE Ratio: {metrics.get('price_to_earnings_ratio')}")
            logger.info(f"  PB Ratio: {metrics.get('price_to_book_ratio')}")
            logger.info(f"  ROE: {metrics.get('return_on_equity')}")
        else:
            logger.warning("No financial metrics available")
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")


def demo_hk_stock():
    """Demonstrate HK stock data fetching with multi-source validation."""
    logger.info("\n" + "=" * 60)
    logger.info("Demo 2: Hong Kong Stock Data (Multi-Source)")
    logger.info("=" * 60)

    # Create validator with custom settings
    validator = DataValidator(
        source_weights={
            "AKShare": 1.0,
            "YFinance": 0.8,
        },
        price_threshold=0.02,
    )

    # Create HK stock adapter
    adapter = HKStockAdapter(validator=validator)

    # Test ticker normalization
    test_tickers = ["700", "00700", "0700.HK", "1398"]
    logger.info("\nTicker Normalization:")
    for ticker in test_tickers:
        normalized = adapter.normalize_ticker(ticker)
        yf_format = adapter.get_yfinance_ticker(normalized)
        logger.info(f"  {ticker:12} -> {normalized} -> {yf_format}")

    # Get price data for Tencent (00700)
    ticker = "00700"
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    logger.info(f"\nFetching prices for {ticker} from {start_date} to {end_date}...")
    logger.info("Note: Will attempt to fetch from multiple sources and validate")

    try:
        prices = adapter.get_prices(ticker, start_date, end_date)
        if prices:
            logger.info(f"Retrieved {len(prices)} validated price records")
            logger.info(f"Latest price: Open={prices[-1].open}, Close={prices[-1].close}")
            logger.info("Data has been validated across multiple sources")
        else:
            logger.warning("No price data available")
    except Exception as e:
        logger.error(f"Error fetching prices: {e}")

    # Get financial metrics
    logger.info(f"\nFetching financial metrics for {ticker}...")
    try:
        metrics = adapter.get_financial_metrics(ticker, end_date)
        if metrics:
            logger.info("Financial metrics retrieved:")
            logger.info(f"  PE Ratio: {metrics.get('price_to_earnings_ratio')}")
            logger.info(f"  PB Ratio: {metrics.get('price_to_book_ratio')}")
            logger.info(f"  ROE: {metrics.get('return_on_equity')}")
            if 'num_sources' in metrics:
                logger.info(f"  Validated from {metrics['num_sources']} sources")
                logger.info(f"  Confidence: {metrics.get('confidence', 0):.2f}")
        else:
            logger.warning("No financial metrics available")
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")


def demo_validation():
    """Demonstrate data validation capabilities."""
    logger.info("\n" + "=" * 60)
    logger.info("Demo 3: Data Validation")
    logger.info("=" * 60)

    # Create validator with different threshold settings
    logger.info("\nValidator Configuration:")

    strict_validator = DataValidator(
        source_weights={"AKShare": 1.0, "YFinance": 0.8},
        price_threshold=0.01,  # 1% - strict
    )
    logger.info(f"  Strict: {strict_validator.price_threshold * 100}% threshold")

    normal_validator = DataValidator(
        source_weights={"AKShare": 1.0, "YFinance": 0.8},
        price_threshold=0.02,  # 2% - normal
    )
    logger.info(f"  Normal: {normal_validator.price_threshold * 100}% threshold")

    lenient_validator = DataValidator(
        source_weights={"AKShare": 1.0, "YFinance": 0.8},
        price_threshold=0.05,  # 5% - lenient
    )
    logger.info(f"  Lenient: {lenient_validator.price_threshold * 100}% threshold")

    # Demonstrate confidence calculation
    logger.info("\nConfidence Score Examples:")
    logger.info("  (Higher = better agreement between sources)")

    scenarios = [
        (1, 0.00, "Single source, no deviation"),
        (2, 0.00, "Two sources, perfect agreement"),
        (2, 0.01, "Two sources, 1% deviation"),
        (3, 0.00, "Three sources, perfect agreement"),
        (2, 0.05, "Two sources, 5% deviation"),
    ]

    for num_sources, deviation, desc in scenarios:
        confidence = normal_validator._calculate_confidence(num_sources, deviation)
        logger.info(f"  {desc:40} -> {confidence:.2f}")


def demo_market_comparison():
    """Compare data from different markets."""
    logger.info("\n" + "=" * 60)
    logger.info("Demo 4: Market Comparison")
    logger.info("=" * 60)

    cn_adapter = CNStockAdapter()
    hk_adapter = HKStockAdapter()

    logger.info("\nMarket Capabilities:")
    logger.info(f"  CN Adapter: {len(cn_adapter.active_sources)} active source(s)")
    for source in cn_adapter.active_sources:
        logger.info(f"    - {source.name}")

    logger.info(f"  HK Adapter: {len(hk_adapter.active_sources)} active source(s)")
    for source in hk_adapter.active_sources:
        logger.info(f"    - {source.name}")

    logger.info("\nData Source Support:")
    markets = ["CN", "HK", "US"]
    for source in hk_adapter.data_sources:
        supported = [m for m in markets if source.supports_market(m)]
        logger.info(f"  {source.name:20} -> {', '.join(supported)}")


def main():
    """Run all demos."""
    logger.info("Multi-Source Data Integration Demo")
    logger.info("=" * 60)

    try:
        # Demo 1: CN Stock
        demo_cn_stock()

        # Demo 2: HK Stock with multi-source
        demo_hk_stock()

        # Demo 3: Validation
        demo_validation()

        # Demo 4: Market comparison
        demo_market_comparison()

        logger.info("\n" + "=" * 60)
        logger.info("Demo completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)


if __name__ == "__main__":
    main()
