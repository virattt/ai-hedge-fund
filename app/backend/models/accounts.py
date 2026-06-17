from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class AccountCreate(BaseModel):
    owner_name: str = Field(..., min_length=1, max_length=200)
    account_type: str = Field(default="ISA", max_length=100)
    provider: str = Field(default="AJ Bell", max_length=200)
    label: Optional[str] = Field(None, max_length=300)


class AccountUpdate(BaseModel):
    owner_name: Optional[str] = Field(None, max_length=200)
    account_type: Optional[str] = Field(None, max_length=100)
    provider: Optional[str] = Field(None, max_length=200)
    label: Optional[str] = Field(None, max_length=300)


class AccountResponse(BaseModel):
    id: int
    owner_name: str
    account_type: str
    provider: str
    label: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class AccountSummary(BaseModel):
    id: int
    owner_name: str
    account_type: str
    provider: str
    label: Optional[str]
    total_holdings: int
    total_cost: float
    total_value: Optional[float]
    profit_loss: Optional[float]
    profit_loss_pct: Optional[float]
