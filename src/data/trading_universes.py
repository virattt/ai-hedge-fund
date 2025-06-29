"""
Predefined trading universes for the AI hedge fund.
Defines various investment universes with specific criteria and constraints.
"""

from typing import Dict, List
from .models import TradingUniverse, AssetClass, Sector, MarketCapCategory


# S&P 500 Universe
SP500_UNIVERSE = TradingUniverse(
    name="S&P 500 Universe",
    description="S&P 500 companies with high liquidity and options availability",
    asset_classes=[AssetClass.EQUITY],
    sectors=None,  # All sectors allowed
    market_cap_categories=[MarketCapCategory.MEGA_CAP, MarketCapCategory.LARGE_CAP],
    min_market_cap=2.0,  # $2B minimum
    min_daily_volume=1_000_000,  # 1M shares
    min_avg_volume=500_000,  # 500K average
    indices=["SPY"],
    max_positions=50,
    rebalance_frequency="daily",
    liquidity_threshold=0.8,
    excluded_tickers=[]  # Can exclude specific tickers if needed
)

# High-Volume Tech Stocks Universe
TECH_UNIVERSE = TradingUniverse(
    name="High-Volume Tech Stocks",
    description="Technology sector stocks with high volume and options liquidity",
    asset_classes=[AssetClass.EQUITY],
    sectors=[
        Sector.TECHNOLOGY,
        Sector.COMMUNICATION,
        Sector.CONSUMER_DISCRETIONARY  # For tech-adjacent companies like TSLA, AMZN
    ],
    market_cap_categories=[MarketCapCategory.MEGA_CAP, MarketCapCategory.LARGE_CAP],
    min_market_cap=10.0,  # $10B minimum for tech focus
    min_daily_volume=2_000_000,  # 2M shares for high volume requirement
    min_avg_volume=1_000_000,  # 1M average
    indices=["QQQ", "XLK"],  # NASDAQ-100 and Tech Select Sector SPDR
    max_positions=30,
    rebalance_frequency="daily",
    liquidity_threshold=0.9,  # Higher liquidity requirement for tech
    included_tickers=[
        # Force include major tech names
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "NFLX", "CRM", "ORCL"
    ]
)

# Sector ETFs Universe
SECTOR_ETF_UNIVERSE = TradingUniverse(
    name="Sector ETFs",
    description="Sector-based ETFs for broad market exposure and sector rotation strategies",
    asset_classes=[AssetClass.ETF],
    sectors=None,  # ETFs cover all sectors
    market_cap_categories=None,  # Not applicable for ETFs
    min_market_cap=None,
    min_daily_volume=1_000_000,  # 1M shares
    min_avg_volume=500_000,
    indices=[],
    max_positions=15,  # Limited to avoid over-diversification
    rebalance_frequency="weekly",  # Less frequent for ETF strategies
    liquidity_threshold=0.8,
    included_tickers=[
        # SPDR Sector ETFs
        "XLK",  # Technology
        "XLF",  # Financial
        "XLV",  # Health Care
        "XLI",  # Industrial
        "XLY",  # Consumer Discretionary
        "XLP",  # Consumer Staples
        "XLE",  # Energy
        "XLU",  # Utilities
        "XLB",  # Materials
        "XLRE", # Real Estate
        "XLC",  # Communication Services
        # Additional broad market ETFs
        "SPY",  # S&P 500
        "QQQ",  # NASDAQ-100
        "IWM",  # Russell 2000 (Small Cap)
        "VTI"   # Total Stock Market
    ]
)

# Options-Focused Universe
OPTIONS_UNIVERSE = TradingUniverse(
    name="Options Trading Universe",
    description="Stocks and ETFs with liquid options markets for complex strategies",
    asset_classes=[AssetClass.EQUITY, AssetClass.ETF, AssetClass.OPTION],
    sectors=None,
    market_cap_categories=[MarketCapCategory.MEGA_CAP, MarketCapCategory.LARGE_CAP],
    min_market_cap=5.0,  # $5B minimum for options liquidity
    min_daily_volume=1_500_000,  # 1.5M shares
    min_avg_volume=750_000,
    indices=["SPY", "QQQ"],
    max_positions=25,
    rebalance_frequency="daily",
    liquidity_threshold=0.9,  # High liquidity requirement for options
    included_tickers=[
        # High options volume stocks
        "SPY", "QQQ", "AAPL", "TSLA", "NVDA", "AMZN", "MSFT", "GOOGL",
        "META", "AMD", "NFLX", "IWM", "XLF", "XLK", "EEM", "GLD"
    ]
)

# Conservative Large Cap Universe
CONSERVATIVE_LARGE_CAP = TradingUniverse(
    name="Conservative Large Cap",
    description="Blue-chip stocks with stable fundamentals and dividend history",
    asset_classes=[AssetClass.EQUITY],
    sectors=[
        Sector.CONSUMER_STAPLES,
        Sector.UTILITIES,
        Sector.HEALTHCARE,
        Sector.FINANCIALS
    ],
    market_cap_categories=[MarketCapCategory.MEGA_CAP, MarketCapCategory.LARGE_CAP],
    min_market_cap=20.0,  # $20B minimum for blue chips
    min_daily_volume=500_000,
    min_avg_volume=300_000,
    indices=["SPY"],
    max_positions=40,
    rebalance_frequency="monthly",  # Less frequent for conservative approach
    liquidity_threshold=0.7,
    included_tickers=[
        # Dividend aristocrats and blue chips
        "JNJ", "PG", "KO", "PEP", "WMT", "HD", "UNH", "V", "MA", "JPM"
    ]
)

# All available trading universes
TRADING_UNIVERSES: Dict[str, TradingUniverse] = {
    "sp500": SP500_UNIVERSE,
    "tech": TECH_UNIVERSE,
    "sector_etf": SECTOR_ETF_UNIVERSE,
    "options": OPTIONS_UNIVERSE,
    "conservative": CONSERVATIVE_LARGE_CAP
}

def get_trading_universe(name: str) -> TradingUniverse:
    """Get a trading universe by name"""
    if name not in TRADING_UNIVERSES:
        raise ValueError(f"Unknown trading universe: {name}. Available: {list(TRADING_UNIVERSES.keys())}")
    return TRADING_UNIVERSES[name]

def list_trading_universes() -> List[str]:
    """List all available trading universe names"""
    return list(TRADING_UNIVERSES.keys())

def create_combined_universe(universes: List[str], name: str, description: str) -> TradingUniverse:
    """Combine multiple trading universes into one"""
    if not universes:
        raise ValueError("At least one universe must be specified")
    
    base_universe = get_trading_universe(universes[0])
    combined_tickers = set(base_universe.included_tickers)
    combined_indices = set(base_universe.indices)
    combined_asset_classes = set(base_universe.asset_classes)
    combined_sectors = set(base_universe.sectors or [])
    
    # Merge all universes
    for universe_name in universes[1:]:
        universe = get_trading_universe(universe_name)
        combined_tickers.update(universe.included_tickers)
        combined_indices.update(universe.indices)
        combined_asset_classes.update(universe.asset_classes)
        if universe.sectors:
            combined_sectors.update(universe.sectors)
    
    return TradingUniverse(
        name=name,
        description=description,
        asset_classes=list(combined_asset_classes),
        sectors=list(combined_sectors) if combined_sectors else None,
        market_cap_categories=base_universe.market_cap_categories,
        min_market_cap=base_universe.min_market_cap,
        min_daily_volume=base_universe.min_daily_volume,
        min_avg_volume=base_universe.min_avg_volume,
        included_tickers=list(combined_tickers),
        indices=list(combined_indices),
        max_positions=sum(get_trading_universe(u).max_positions or 50 for u in universes),
        rebalance_frequency=base_universe.rebalance_frequency,
        liquidity_threshold=base_universe.liquidity_threshold
    )

# Pre-configured combined universes
AGGRESSIVE_GROWTH = create_combined_universe(
    ["tech", "options"],
    "Aggressive Growth",
    "High-growth tech stocks with options strategies for maximum returns"
)

BALANCED_PORTFOLIO = create_combined_universe(
    ["sp500", "sector_etf"],
    "Balanced Portfolio",
    "Diversified portfolio combining S&P 500 stocks and sector ETFs"
)

TRADING_UNIVERSES.update({
    "aggressive_growth": AGGRESSIVE_GROWTH,
    "balanced": BALANCED_PORTFOLIO
})