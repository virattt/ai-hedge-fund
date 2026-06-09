"""Pydantic schemas for the earnings calendar."""

from pydantic import BaseModel


class EarningsCalendarItem(BaseModel):
    date: str  # YYYY-MM-DD
    ticker: str
    company: str | None = None
    eps_estimate: float | None = None
    eps_actual: float | None = None
    revenue_estimate: float | None = None
    revenue_actual: float | None = None
    hour: str | None = None  # "bmo" | "amc" | "dmh" | None
    quarter: int | None = None
    fiscal_year: int | None = None


class EarningsCalendarResponse(BaseModel):
    items: list[EarningsCalendarItem]
    date_from: str
    date_to: str
    total: int
    cached: bool
