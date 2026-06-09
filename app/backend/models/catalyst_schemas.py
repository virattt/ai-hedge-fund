"""Pydantic schemas for Catalysts (spin-offs, IPOs, M&A, etc.)."""

from pydantic import BaseModel


class SpinoffFilingItem(BaseModel):
    accession_no: str
    cik: int
    company: str
    form: str
    filing_date: str
    primary_doc_url: str | None = None
    primary_doc_description: str | None = None


class SpinoffListResponse(BaseModel):
    filings: list[SpinoffFilingItem]
    total: int
    cached: bool


class InsiderPurchase(BaseModel):
    filing_date: str
    accession_no: str
    insider_name: str
    insider_title: str | None = None
    shares: float | None = None
    price_per_share: float | None = None
    value: float | None = None


class SpinoffInsiderSummary(BaseModel):
    cik: int
    purchase_count: int
    total_value: float
    purchases: list[InsiderPurchase]
    cached: bool
