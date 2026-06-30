"""Fallback sector classification for known tickers.

Used when holdings have no sector set in the database.
"""

TICKER_SECTOR_MAP: dict[str, str] = {
    # US Equities
    "NVDA": "Technology / Semiconductors",
    "AAPL": "Technology / Consumer Electronics",
    "MSFT": "Technology / Software",
    "GOOGL": "Technology / Internet",
    "GOOG": "Technology / Internet",
    "AMZN": "Technology / E-Commerce",
    "META": "Technology / Social Media",
    "TSLA": "Consumer Discretionary / Automotive",
    "BRK-B": "Financials / Conglomerate",
    "BRK.B": "Financials / Conglomerate",
    "BRK-A": "Financials / Conglomerate",
    "BRK.A": "Financials / Conglomerate",
    "RKLB": "Industrials / Aerospace",
    "SCCO": "Materials / Copper",
    "PLTR": "Technology / Software",

    # UK-listed
    "LGEN": "Financials / Insurance",
    "LGEN.L": "Financials / Insurance",

    # ETFs
    "ISF": "ETF / UK Equity Index",
    "ISF.L": "ETF / UK Equity Index",
    "VWRL": "ETF / Global Equity",
    "VWRL.L": "ETF / Global Equity",
    "VMID": "ETF / UK Mid-Cap",
    "VMID.L": "ETF / UK Mid-Cap",
    "VUSA": "ETF / US Equity (S&P 500)",
    "VUSA.L": "ETF / US Equity (S&P 500)",
    "CSP1": "ETF / US Equity (S&P 500)",
    "CSP1.L": "ETF / US Equity (S&P 500)",
    "IITU": "ETF / US Technology",
    "IITU.L": "ETF / US Technology",
    "EQQQ": "ETF / US Technology (Nasdaq)",
    "EQQQ.L": "ETF / US Technology (Nasdaq)",

    # Commodities
    "SGLN": "Commodity / Gold",
    "SGLN.L": "Commodity / Gold",
    "SSLN": "Commodity / Silver",
    "SSLN.L": "Commodity / Silver",

    # Funds / SEDOLs
    "B523MH2": "Fund / UK Equity",
}


def get_sector_fallback(ticker: str) -> str:
    """Return a sector classification for a ticker, or 'Unclassified' if unknown."""
    upper = ticker.strip().upper()
    return TICKER_SECTOR_MAP.get(upper, "Unclassified")
