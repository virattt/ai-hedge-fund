"""
API Configuration Module

Allows switching between Financial Datasets API and Yahoo Finance API.
Set USE_YAHOO_FINANCE environment variable to control which API to use.
"""

import os
from typing import Literal

# API Provider type
APIProvider = Literal["financial_datasets", "yahoo_finance"]


def get_api_provider() -> APIProvider:
    """
    Determine which API provider to use based on environment variable.

    Returns:
        "yahoo_finance" if USE_YAHOO_FINANCE is set to "true", "1", or "yes"
        "financial_datasets" otherwise
    """
    use_yahoo = os.environ.get("USE_YAHOO_FINANCE", "false").lower()

    if use_yahoo in ["true", "1", "yes", "y"]:
        return "yahoo_finance"

    return "financial_datasets"


def is_using_yahoo_finance() -> bool:
    """Check if Yahoo Finance API is being used."""
    return get_api_provider() == "yahoo_finance"


def is_using_financial_datasets() -> bool:
    """Check if Financial Datasets API is being used."""
    return get_api_provider() == "financial_datasets"


def get_api_info() -> dict:
    """
    Get information about the current API configuration.

    Returns:
        Dictionary with API provider info and capabilities
    """
    provider = get_api_provider()

    if provider == "yahoo_finance":
        return {
            "provider": "Yahoo Finance (yfinance)",
            "cost": "Free",
            "capabilities": {
                "historical_prices": True,
                "financial_metrics": True,
                "financial_statements": True,
                "insider_trades": False,
                "company_news": True,
                "news_sentiment": False,
            },
            "limitations": [
                "No insider trading data",
                "No pre-calculated sentiment analysis",
                "Some financial metrics may be incomplete for historical periods",
            ],
        }
    else:
        return {
            "provider": "Financial Datasets API",
            "cost": "Paid (requires API credits)",
            "capabilities": {
                "historical_prices": True,
                "financial_metrics": True,
                "financial_statements": True,
                "insider_trades": True,
                "company_news": True,
                "news_sentiment": True,
            },
            "limitations": [
                "Requires API key and credits",
            ],
        }


def print_api_info():
    """Print current API configuration information."""
    info = get_api_info()

    print("\n" + "="*60)
    print(f"API Configuration")
    print("="*60)
    print(f"Provider: {info['provider']}")
    print(f"Cost: {info['cost']}")
    print("\nCapabilities:")
    for capability, available in info['capabilities'].items():
        status = "✅" if available else "❌"
        print(f"  {status} {capability.replace('_', ' ').title()}")

    if info['limitations']:
        print("\nLimitations:")
        for limitation in info['limitations']:
            print(f"  ⚠️  {limitation}")

    print("="*60 + "\n")
