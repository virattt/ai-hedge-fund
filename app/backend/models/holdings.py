from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List


class HoldingCreate(BaseModel):
    portfolio_name: str = Field(default="Default", max_length=200)
    account_id: Optional[int] = None
    ticker: str = Field(..., min_length=1, max_length=20)
    investment_name: str = Field(..., min_length=1, max_length=300)
    quantity: float = Field(..., gt=0)
    buy_price: float = Field(..., gt=0)
    cost_basis: Optional[float] = None
    currency: str = Field(default="GBP", max_length=10)
    sector: Optional[str] = Field(None, max_length=200)


class HoldingUpdate(BaseModel):
    portfolio_name: Optional[str] = Field(None, max_length=200)
    account_id: Optional[int] = None
    ticker: Optional[str] = Field(None, max_length=20)
    investment_name: Optional[str] = Field(None, max_length=300)
    quantity: Optional[float] = Field(None, gt=0)
    buy_price: Optional[float] = Field(None, gt=0)
    cost_basis: Optional[float] = None
    currency: Optional[str] = Field(None, max_length=10)
    sector: Optional[str] = Field(None, max_length=200)


class HoldingResponse(BaseModel):
    id: int
    portfolio_name: str
    account_id: Optional[int] = None
    ticker: str
    investment_name: str
    quantity: float
    buy_price: float
    cost_basis: Optional[float]
    currency: str
    sector: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class HoldingImportRow(BaseModel):
    ticker: str
    investment_name: str
    quantity: float
    buy_price: float
    cost_basis: Optional[float] = None
    currency: str = "GBP"
    portfolio: Optional[str] = None


class HoldingImportRequest(BaseModel):
    portfolio_name: str = Field(default="Default", max_length=200)
    csv_text: str = Field(..., min_length=1)


class HoldingImportResponse(BaseModel):
    imported: int
    errors: List[str]


class DashboardHolding(BaseModel):
    id: int
    portfolio_name: str
    account_id: Optional[int] = None
    account_label: Optional[str] = None
    ticker: str
    investment_name: str
    quantity: float
    buy_price: float
    cost_basis: float
    currency: str
    sector: Optional[str] = None
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    profit_loss: Optional[float] = None
    profit_loss_pct: Optional[float] = None
    rsi_14: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    trend: Optional[str] = None
    action_label: str = "WATCH"
    risk_score: Optional[int] = None  # 1-10 scale


class AllocationItem(BaseModel):
    label: str
    value: float
    percentage: float


class AccountSummaryItem(BaseModel):
    account_id: int
    label: str
    owner_name: str
    total_cost: float
    total_value: float
    profit_loss: float
    profit_loss_pct: Optional[float] = None
    holdings_count: int


class DashboardResponse(BaseModel):
    holdings: List[DashboardHolding]
    total_cost: float
    total_value: float
    total_profit_loss: float
    total_profit_loss_pct: Optional[float] = None
    overall_risk_score: Optional[int] = None  # 1-10 scale
    allocation_by_sector: List[AllocationItem] = []
    allocation_by_account: List[AllocationItem] = []
    account_summaries: List[AccountSummaryItem] = []
