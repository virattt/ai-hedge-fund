"""Pydantic schemas for Finnhub API responses."""

from pydantic import BaseModel


class ShortInterestData(BaseModel):
    """Short interest metrics for a single ticker from Finnhub stock/metric endpoint."""
    symbol: str
    short_pct_float: float | None = None   # shortPercentOfFloat — the squeeze %
    days_to_cover: float | None = None      # shortRatio — how trapped shorts are
    shares_short: int | None = None         # sharesShort
    float_shares: float | None = None       # floatByCompany


class ShortInterestResponse(BaseModel):
    symbol: str
    data: ShortInterestData | None = None
    cached: bool


class SqueezeCandidate(BaseModel):
    ticker: str
    company_name: str
    short_pct_float: float | None = None
    days_to_cover: float | None = None
    shares_short: int | None = None
    insider_buy_count: int = 0
    insider_buy_value: float = 0.0
    latest_insider_buy_date: str | None = None


class SqueezeScreenerResponse(BaseModel):
    candidates: list[SqueezeCandidate]
    total: int
