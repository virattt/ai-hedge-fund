"""Pydantic schemas for the Discovery (aggregated ideas) feature."""

from typing import Any

from pydantic import BaseModel


class IdeaSignal(BaseModel):
    source: str            # "spinoff" | "csuite_buy" | "squeeze" (extensible)
    score: float           # contribution to total score
    label: str             # human-readable, e.g. "CEO bought $1.5M"
    detail: dict[str, Any] | None = None  # source-specific metadata
    kill_filter: bool = False  # if True, the engine drops this ticker entirely


class DiscoveryIdea(BaseModel):
    ticker: str            # ticker symbol or CIK string (when no ticker yet)
    company: str | None = None
    cik: int | None = None
    score: float
    signals: list[IdeaSignal]
    is_ticker: bool = True  # False if `ticker` field actually holds a CIK
    return_30d_pct: float | None = None
    alpha_30d_pct: float | None = None
    distance_from_whale_entry_pct: float | None = None


class DiscoveryResponse(BaseModel):
    ideas: list[DiscoveryIdea]
    total: int
    cached: bool
    generated_at: str  # ISO timestamp


class DiscoverySnapshotItem(BaseModel):
    """One historical snapshot of a ticker's Discovery score."""
    ticker: str
    cik: int | None = None
    company: str | None = None
    score: float
    distinct_sources: int
    snapshot_at: str  # ISO timestamp


class DiscoveryHistoryResponse(BaseModel):
    """Time series of snapshots for a single ticker."""
    ticker: str
    snapshots: list[DiscoverySnapshotItem]
    total: int


class DiscoveryMover(BaseModel):
    """A ticker whose Discovery score changed materially over the lookback window."""
    ticker: str
    cik: int | None = None
    company: str | None = None
    score_now: float
    score_before: float
    delta: float
    snapshot_at_now: str
    snapshot_at_before: str


class DiscoveryMoversResponse(BaseModel):
    movers: list[DiscoveryMover]
    days: int
    total: int
