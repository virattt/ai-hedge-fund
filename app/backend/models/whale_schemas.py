"""Pydantic schemas for the whale-tracking feature (whale funds + entries)."""

from pydantic import BaseModel


class WhaleFundResponse(BaseModel):
    id: int
    cik: int
    name: str
    notes: str | None = None
    added_at: str | None = None


class WhaleFundListResponse(BaseModel):
    items: list[WhaleFundResponse]
    total: int


class WhaleFundAddRequest(BaseModel):
    cik: int
    name: str
    notes: str | None = None


class WhaleFundCandidate(BaseModel):
    cik: int
    company: str


class WhaleFundCandidatesResponse(BaseModel):
    candidates: list[WhaleFundCandidate]


class WhaleEntryResponse(BaseModel):
    whale_cik: int
    whale_name: str
    ticker: str
    entry_quarter_label: str | None = None
    entry_period_start: str | None = None
    entry_period_end: str | None = None
    entry_vwap: float | None = None
    entry_low: float | None = None
    entry_high: float | None = None
    share_count_at_entry: float | None = None
    is_pre_lookback: bool = False
    computed_at: str | None = None


class TickerWhaleSummaryResponse(BaseModel):
    ticker: str
    current_price: float | None = None
    best_entry_vwap: float | None = None
    best_entry_whale_cik: int | None = None
    best_entry_whale_name: str | None = None
    distance_from_best_entry_pct: float | None = None
    whale_count: int
    entries: list[WhaleEntryResponse]


class WhaleRefreshResponse(BaseModel):
    refreshed: dict[int, int]
    total_rows_written: int
