"""Pydantic schemas for Political & Policy data (USA Spending + House Stock Watcher)."""

from pydantic import BaseModel


class GovContract(BaseModel):
    award_id: str | None = None
    recipient_name: str | None = None
    award_amount: float | None = None
    awarding_agency: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class GovContractsResponse(BaseModel):
    contracts: list[GovContract]
    total: int
    cached: bool


class CongressTrade(BaseModel):
    representative: str | None = None
    ticker: str | None = None
    transaction_type: str | None = None
    amount: str | None = None
    transaction_date: str | None = None
    disclosure_date: str | None = None
    district: str | None = None
    ptr_link: str | None = None


class CongressTradesResponse(BaseModel):
    trades: list[CongressTrade]
    total: int
    source_available: bool
    cached: bool
