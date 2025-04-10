from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field, validator
from datetime import datetime

# Greek models
class Greeks(BaseModel):
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0

# Leg model
class Leg(BaseModel):
    id: str
    description: str
    type: str  # option, future, stock, future's option
    multiplier: float = 1.0
    open_date: str
    DTE: int
    put: int = 0  # +1 for long put, -1 for short put, 0 for not a put
    call: int = 0  # +1 for long call, -1 for short call, 0 for not a call
    expiry: Optional[str] = None
    strike: Optional[float] = None
    cost_basis: float  # positive for long, negative for short
    greeks: Greeks = Field(default_factory=Greeks)

# Risk profile model
class RiskProfile(BaseModel):
    risk_category: str  # defined vs undefined
    margin: float = 0.0  # margin required for the strategy
    expected_value: float = 0.0  # theroretical implied expected value of the strategy (EV = pop*premium + (1-pop)*average theoretical loss conditioned on the strategy being a loser)
    pop: float = 0.0  # probability of profit
    expected_delta_move: float = 0.0  # delta_risk = delta * expected daily price change
    expected_convexity_move: float = 0.0  # convexity_risk = theta-gamma * (expected daily price change)^2
    CVaR: float = 0.0  # Daily Conditional Value at Risk at 95% confidence level
    marginal_contribution_to_risk: float = 0.0  # Contribution of this strategy to the overall portfolio risk
    survival_probability_10: float = 0.0  # probability that the startegy hits 10% of profit before hitting max loss
    survival_probability_25: float = 0.0  # probability that the startegy hits 25% of profit before hitting max loss
    survival_probability_50: float = 0.0  # probability that the startegy hits 50% of profit before hitting max loss

# Strategy assumptions
class Assumptions(BaseModel):
    underlying_direction: Literal["neutral", "long", "short"] = "neutral"
    volatility_direction: Literal["neutral", "long", "short"] = "neutral"

# Strategy model
class Strategy(BaseModel):
    ticker: str
    asset_class: str  # equity, commodity, fixed_income, currency
    description: str
    open_date: str
    days_in_trade: int
    beta: float = 1.0  # Correlation of the stock to SPX (1.0 means moves exactly with SPX)
    risk_profile: RiskProfile = Field(default_factory=RiskProfile)
    premium: float = 0.0  # premium of the strategy, negative for long, positive for short
    assumptions: Assumptions = Field(default_factory=Assumptions)
    price: float = 0.0  # current price of the underlying
    ivr: float = 0.0  # current IVR of the underlying
    number_of_contracts: int = 0
    number_of_legs: int = 0
    leg_positions: List[int] = Field(default_factory=list)  # list of positions for each leg
    legs: List[Leg] = Field(default_factory=list)
    pnl: float = 0.0  # Current P&L of the strategy
    pnl_percent: float = 0.0  # P&L as a percentage of the initial investment
    pnl_history: Dict[str, float] = Field(default_factory=dict)  # Historical P&L by date
    
    def __getitem__(self, index):
        """Allow access to legs by index"""
        return self.legs[index]

# Expected daily move model
class ExpectedDailyMove(BaseModel):
    directional_exposure: float = 0.0  # beta_delta * expected daily price change
    convexity_exposure: float = 0.0  # gamma * (expected daily price change)^2
    time_decay: float = 0.0  # theta
    volatility_exposure: float = 0.0  # vega * expected daily vol change
    total_exposure: float = 0.0  # sum of all exposures

# Portfolio model
class Portfolio(BaseModel):
    net_liquidation_value: float = 0.0
    cash: float = 0.0
    margin_used: float = 0.0
    max_margin: float = 0.0  # maximum margin allowed
    total_beta_weighted_delta: float = 0.0  # sum of all beta-weighted deltas across strategies
    theta: float = 0.0 # sum of all theta across strategies
    total_beta_weighted_gamma: float = 0.0 # sum of all beta-weighted gamma across strategies
    expected_daily_move: ExpectedDailyMove = Field(default_factory=ExpectedDailyMove)
    CVaR: float = 0.0  # Conditional Value at Risk at 95% confidence level
    pnl: float = 0.0  # Current total P&L of the portfolio
    pnl_percent: float = 0.0  # P&L as a percentage of the portfolio value
    pnl_history: Dict[str, float] = Field(default_factory=dict)  # Historical P&L by date
    strategies: List[Strategy] = Field(default_factory=list)
    
    def strategy(self, index):
        """Get strategy by index"""
        if 0 <= index < len(self.strategies):
            return self.strategies[index]
        raise IndexError(f"Strategy index {index} out of range")

# Market conditions model
class MarketConditions(BaseModel):
    spx: float = 0.0
    vix: float = 0.0
    vix_1d: float = 0.0  # 1-day expected move in VIX
    vvix: float = 0.0
    expected_daily_move: float = Field(0.0, alias="1day_expected_move")

# User profile model
class Profile(BaseModel):
    max_daily_drawdown: float = 0.0
    max_size_position: float = 0.0  # % of net liquidation value
    management_style: int = 2  # 1:conservative, 2:moderate, 3:aggressive

# Main data model
class OptionPal(BaseModel):
    date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    watchlist: List[str] = Field(default_factory=list)
    profile: Profile = Field(default_factory=Profile)
    analyst_signals: Dict[str, Any] = Field(default_factory=dict)
    market_conditions: MarketConditions = Field(default_factory=MarketConditions)
    portfolio: Portfolio = Field(default_factory=Portfolio)
    
    class Config:
        allow_population_by_field_name = True
