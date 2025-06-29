from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Literal, Union
from enum import Enum


class Price(BaseModel):
    open: float
    close: float
    high: float
    low: float
    volume: int
    time: str


class PriceResponse(BaseModel):
    ticker: str
    prices: list[Price]


class FinancialMetrics(BaseModel):
    ticker: str
    report_period: str
    period: str
    currency: str
    market_cap: float | None
    enterprise_value: float | None
    price_to_earnings_ratio: float | None
    price_to_book_ratio: float | None
    price_to_sales_ratio: float | None
    enterprise_value_to_ebitda_ratio: float | None
    enterprise_value_to_revenue_ratio: float | None
    free_cash_flow_yield: float | None
    peg_ratio: float | None
    gross_margin: float | None
    operating_margin: float | None
    net_margin: float | None
    return_on_equity: float | None
    return_on_assets: float | None
    return_on_invested_capital: float | None
    asset_turnover: float | None
    inventory_turnover: float | None
    receivables_turnover: float | None
    days_sales_outstanding: float | None
    operating_cycle: float | None
    working_capital_turnover: float | None
    current_ratio: float | None
    quick_ratio: float | None
    cash_ratio: float | None
    operating_cash_flow_ratio: float | None
    debt_to_equity: float | None
    debt_to_assets: float | None
    interest_coverage: float | None
    revenue_growth: float | None
    earnings_growth: float | None
    book_value_growth: float | None
    earnings_per_share_growth: float | None
    free_cash_flow_growth: float | None
    operating_income_growth: float | None
    ebitda_growth: float | None
    payout_ratio: float | None
    earnings_per_share: float | None
    book_value_per_share: float | None
    free_cash_flow_per_share: float | None


class FinancialMetricsResponse(BaseModel):
    financial_metrics: list[FinancialMetrics]


class LineItem(BaseModel):
    ticker: str
    report_period: str
    period: str
    currency: str

    # Allow additional fields dynamically
    model_config = {"extra": "allow"}


class LineItemResponse(BaseModel):
    search_results: list[LineItem]


class InsiderTrade(BaseModel):
    ticker: str
    issuer: str | None
    name: str | None
    title: str | None
    is_board_director: bool | None
    transaction_date: str | None
    transaction_shares: float | None
    transaction_price_per_share: float | None
    transaction_value: float | None
    shares_owned_before_transaction: float | None
    shares_owned_after_transaction: float | None
    security_title: str | None
    filing_date: str


class InsiderTradeResponse(BaseModel):
    insider_trades: list[InsiderTrade]


class CompanyNews(BaseModel):
    ticker: str
    title: str
    author: str
    source: str
    date: str
    url: str
    sentiment: str | None = None


class CompanyNewsResponse(BaseModel):
    news: list[CompanyNews]


class CompanyFacts(BaseModel):
    ticker: str
    name: str
    cik: str | None = None
    industry: str | None = None
    sector: str | None = None
    category: str | None = None
    exchange: str | None = None
    is_active: bool | None = None
    listing_date: str | None = None
    location: str | None = None
    market_cap: float | None = None
    number_of_employees: int | None = None
    sec_filings_url: str | None = None
    sic_code: str | None = None
    sic_industry: str | None = None
    sic_sector: str | None = None
    website_url: str | None = None
    weighted_average_shares: int | None = None


class CompanyFactsResponse(BaseModel):
    company_facts: CompanyFacts


class PositionType(str, Enum):
    LONG = "long"
    SHORT = "short"
    CALL = "call"
    PUT = "put"

class Greeks(BaseModel):
    """Options Greeks"""
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float

class Position(BaseModel):
    cash: float = 0.0
    shares: int = 0
    ticker: str
    position_type: PositionType = PositionType.LONG
    cost_basis: float = 0.0
    margin_requirement: float = 0.0  # Margin required for short positions
    option_type: Optional[Literal["call", "put"]] = None
    strike_price: Optional[float] = None
    expiration_date: Optional[date] = None
    greeks: Optional[Greeks] = None


class Portfolio(BaseModel):
    positions: dict[str, Position]  # ticker -> Position mapping
    total_cash: float = 0.0


class AnalystSignal(BaseModel):
    signal: str | None = None
    confidence: float | None = None
    reasoning: dict | str | None = None
    max_position_size: float | None = None  # For risk management signals


class TickerAnalysis(BaseModel):
    ticker: str
    analyst_signals: dict[str, AnalystSignal]  # agent_name -> signal mapping
    security_info: Optional["SecurityInfo"] = None


class AgentStateData(BaseModel):
    tickers: list[str]
    portfolio: Portfolio
    start_date: str
    end_date: str
    ticker_analyses: dict[str, TickerAnalysis]  # ticker -> analysis mapping
    trading_universe: Optional["TradingUniverse"] = None
    options_data: Dict[str, List["OptionsInfo"]] = Field(default_factory=dict)  # ticker -> options chain


class AssetClass(str, Enum):
    EQUITY = "equity"
    ETF = "etf"
    OPTION = "option"
    FUTURES = "futures"
    BONDS = "bonds"
    COMMODITIES = "commodities"

class MarketCapCategory(str, Enum):
    MEGA_CAP = "mega_cap"  # >$200B
    LARGE_CAP = "large_cap"  # $10B-$200B
    MID_CAP = "mid_cap"  # $2B-$10B
    SMALL_CAP = "small_cap"  # $300M-$2B
    MICRO_CAP = "micro_cap"  # <$300M

class Sector(str, Enum):
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    FINANCIALS = "financials"
    CONSUMER_DISCRETIONARY = "consumer_discretionary"
    INDUSTRIALS = "industrials"
    COMMUNICATION = "communication"
    CONSUMER_STAPLES = "consumer_staples"
    ENERGY = "energy"
    UTILITIES = "utilities"
    REAL_ESTATE = "real_estate"
    MATERIALS = "materials"

class TradingUniverse(BaseModel):
    """Defines the trading universe with filters and constraints"""
    name: str
    description: str
    asset_classes: List[AssetClass]
    sectors: Optional[List[Sector]] = None
    market_cap_categories: Optional[List[MarketCapCategory]] = None
    min_market_cap: Optional[float] = None  # Minimum market cap in billions
    min_daily_volume: Optional[float] = None  # Minimum daily volume in shares
    min_avg_volume: Optional[float] = None  # Minimum 30-day average volume
    excluded_tickers: List[str] = Field(default_factory=list)
    included_tickers: List[str] = Field(default_factory=list)  # Force include specific tickers
    indices: List[str] = Field(default_factory=list)  # SPY, QQQ, etc.
    max_positions: Optional[int] = None  # Maximum number of positions
    rebalance_frequency: str = "daily"  # daily, weekly, monthly
    liquidity_threshold: Optional[float] = None  # Minimum liquidity score
    
class SecurityInfo(BaseModel):
    """Extended security information"""
    ticker: str
    name: str
    asset_class: AssetClass
    sector: Optional[Sector] = None
    market_cap: Optional[float] = None  # Market cap in billions
    market_cap_category: Optional[MarketCapCategory] = None
    average_volume_30d: Optional[float] = None
    beta: Optional[float] = None
    is_sp500: bool = False
    is_nasdaq100: bool = False
    is_dow: bool = False
    options_available: bool = False
    min_tick_size: float = 0.01
    lot_size: int = 1
    trading_hours_extended: bool = True
    last_updated: datetime = Field(default_factory=datetime.utcnow)

class OptionsInfo(BaseModel):
    """Options chain information"""
    underlying_ticker: str
    strike: float
    expiration: date
    option_type: Literal["call", "put"]
    bid: Optional[float] = None
    ask: Optional[float] = None
    last_price: Optional[float] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    implied_volatility: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None
    days_to_expiration: Optional[int] = None
    option_symbol: str  # Full option symbol
    
class AgentStateMetadata(BaseModel):
    show_reasoning: bool = False
    model_config = {"extra": "allow"}
