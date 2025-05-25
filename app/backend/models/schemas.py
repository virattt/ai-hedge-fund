from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from src.llm.models import ModelProvider


class HedgeFundResponse(BaseModel):
    decisions: List["TradingDecision"]
    portfolio_snapshot: "PortfolioSnapshot"
    analyst_signals: Dict[str, Dict[str, Any]]  # ticker -> analyst signals


class ErrorResponse(BaseModel):
    detail: str


class HedgeFundRequest(BaseModel):
    tickers: List[str] = Field(..., description="List of stock tickers to analyze")
    selected_agents: List[str] = Field(..., description="List of agent names to use")
    initial_cash: float = Field(..., description="Initial cash amount")
    margin_requirement: float = Field(..., description="Margin requirement as a decimal")
    start_date: Optional[datetime] = Field(None, description="Optional start date for analysis")
    end_date: Optional[datetime] = Field(None, description="Optional end date for analysis")
    model_name: str = Field("gpt-4", description="Name of the LLM model to use")
    model_provider: str = Field("OpenAI", description="Provider of the LLM model")
    show_reasoning: bool = Field(False, description="Whether to show agent reasoning")

    def get_start_date(self) -> str:
        """Calculate start date if not provided"""
        if self.start_date:
            return self.start_date.strftime("%Y-%m-%d")
        return (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")


class AgentInfo(BaseModel):
    name: str
    description: str


class ProgressUpdate(BaseModel):
    agent: str
    ticker: str
    status: str
    analysis: Optional[str] = None
    timestamp: datetime


class TradingDecision(BaseModel):
    ticker: str
    action: str  # "BUY", "SELL", or "HOLD"
    quantity: Optional[int] = None
    price: Optional[float] = None
    reasoning: str
    confidence: float
    timestamp: datetime


class PortfolioSnapshot(BaseModel):
    cash: float
    positions: Dict[str, Dict[str, Any]]  # ticker -> position details
    total_value: float
    timestamp: datetime
