"""Pydantic schemas for the watchlist + nightly batch."""

from typing import Any

from pydantic import BaseModel


class WatchlistItemResponse(BaseModel):
    id: int
    ticker: str
    notes: str | None = None
    added_at: str
    last_analyzed_at: str | None = None
    last_overall_sentiment: str | None = None
    last_delta_direction: str | None = None
    last_management_tone: str | None = None
    last_payload: dict[str, Any] | None = None
    last_error: str | None = None
    return_pct_since_added: float | None = None
    alpha_pct_vs_spy: float | None = None
    distance_from_whale_entry_pct: float | None = None


class WatchlistListResponse(BaseModel):
    items: list[WatchlistItemResponse]
    total: int


class WatchlistAddRequest(BaseModel):
    ticker: str
    notes: str | None = None


class WatchlistNotesUpdateRequest(BaseModel):
    notes: str | None = None


class IsWatchedResponse(BaseModel):
    ticker: str
    is_watched: bool


class BatchRunResponse(BaseModel):
    analyzed: int
    succeeded: int
    failed: int
    skipped_no_earnings: int = 0
