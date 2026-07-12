from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List


class PriceEstimateResponse(BaseModel):
    """Experimental next-session price estimate. Educational only."""
    estimated_next_price: float
    expected_low: float
    expected_high: float
    estimate_confidence: str  # "Low", "Moderate", "High"
    estimate_reason: str


class AnalysisResultResponse(BaseModel):
    id: int
    holding_id: Optional[int] = None
    watchlist_id: Optional[int] = None
    ticker: str
    analysis_ticker: str
    final_action: str
    confidence: float
    technical_summary: Optional[str] = None
    fundamental_summary: Optional[str] = None
    sentiment_summary: Optional[str] = None
    valuation_summary: Optional[str] = None
    risk_summary: Optional[str] = None
    portfolio_manager_summary: Optional[str] = None
    positive_factors: List[str] = []
    risk_factors: List[str] = []
    uncertainties: List[str] = []
    price_estimate: Optional[PriceEstimateResponse] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AnalyzeRequest(BaseModel):
    holding_ids: Optional[List[int]] = None
    model_name: str = Field(default="gpt-4o-mini")
    model_provider: str = Field(default="OpenAI")
    analysis_mode: str = Field(default="quick_scan")


class WatchlistAnalyzeRequest(BaseModel):
    watchlist_ids: Optional[List[int]] = None
    model_name: str = Field(default="gpt-4o-mini")
    model_provider: str = Field(default="OpenAI")
    analysis_mode: str = Field(default="quick_scan")


class AnalysisJobResponse(BaseModel):
    job_id: int
    status: str
    job_type: str
    total_tickers: Optional[int] = None
    completed_tickers: Optional[int] = None
    error_message: Optional[str] = None
    results: Optional[List[AnalysisResultResponse]] = None
    created_at: Optional[datetime] = None
    analysis_mode: Optional[str] = None
    model_name: Optional[str] = None
    agent_count: Optional[int] = None
    estimated_tokens: Optional[int] = None
    elapsed_seconds: Optional[float] = None

    class Config:
        from_attributes = True
