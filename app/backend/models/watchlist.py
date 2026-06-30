from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class WatchlistCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)
    investment_name: Optional[str] = Field(None, max_length=300)
    notes: Optional[str] = None


class WatchlistResponse(BaseModel):
    id: int
    ticker: str
    investment_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
