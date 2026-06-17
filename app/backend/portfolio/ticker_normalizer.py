"""Broker ticker normalization for AJ Bell and similar UK brokers.

Maps broker-format tickers to the format expected by data providers.
LSE-listed tickers are marked as supported since Yahoo Finance provides
price, fundamental, and news data for them.
"""

# Explicit mapping for known UK/special tickers
BROKER_TO_ANALYSIS: dict[str, str] = {
    "BRK.B": "BRK-B",
    "BRK.A": "BRK-A",
    # UK ETFs / LSE-listed — these use Yahoo Finance via the provider layer
    "ISF": "ISF.L",
    "SGLN": "SGLN.L",
    "SSLN": "SSLN.L",
    "LGEN": "LGEN.L",
    "VWRL": "VWRL.L",
    "VMID": "VMID.L",
    "VUSA": "VUSA.L",
    "CSP1": "CSP1.L",
    "IITU": "IITU.L",
    "EQQQ": "EQQQ.L",
}

# Tickers that are known to be unsupported (bonds, money market, SEDOLs)
UNSUPPORTED_PATTERNS = {
    "B523MH2",  # SEDOL-style
}

LSE_SUFFIX = ".L"


def normalize_ticker(broker_ticker: str) -> tuple[str, bool]:
    """Normalize a broker ticker to an analysis ticker.

    Returns:
        (analysis_ticker, is_supported) — if not supported, the analysis
        pipeline should return WATCH with an unsupported-data-source note.
    """
    ticker = broker_ticker.strip().upper()

    # Check explicit unsupported list
    if ticker in UNSUPPORTED_PATTERNS:
        return ticker, False

    # Check explicit mapping
    if ticker in BROKER_TO_ANALYSIS:
        mapped = BROKER_TO_ANALYSIS[ticker]
        # LSE tickers are now supported via Yahoo Finance provider
        return mapped, True

    # If ticker already has .L suffix, it's LSE — supported via Yahoo Finance
    if ticker.endswith(LSE_SUFFIX):
        return ticker, True

    # US-listed tickers pass through as-is (NVDA, AAPL, SCCO, etc.)
    return ticker, True


def is_lse_ticker(ticker: str) -> bool:
    """Check if a ticker is LSE-listed (ends in .L after normalization)."""
    normalized, _ = normalize_ticker(ticker)
    return normalized.upper().endswith(LSE_SUFFIX)


def is_us_ticker(ticker: str) -> bool:
    """Quick check if a ticker is likely US-listed."""
    normalized, supported = normalize_ticker(ticker)
    return supported and not normalized.upper().endswith(LSE_SUFFIX)
