"""Pydantic schemas for insider trading data.

Defines all request/response models for the insider trading dashboard,
supporting Forms 3, 4, and 5 from the SEC EDGAR edgartools API.
"""
from pydantic import BaseModel


class ActivityByDate(BaseModel):
    """Monthly buy/sell activity entry for chart data."""

    date: str
    purchases: int = 0
    sales: int = 0
    purchase_value: float = 0.0
    sale_value: float = 0.0


class InsiderFilingSummary(BaseModel):
    """One row per filing from get_ownership_summary().

    Uses accession_no as the stable SEC filing identifier instead of a
    positional filing_index, which can shift as new filings are added.
    """

    filing_date: str
    accession_no: str
    insider_name: str
    position: str
    primary_activity: str
    net_change: int
    net_value: float | None = None
    remaining_shares: int | None = None
    has_10b5_1_plan: bool | None = None
    transaction_types: list[str] = []
    transaction_count: int = 0
    form_type: str

    # Form 3 (InitialOwnershipSummary) specific fields
    total_holdings: int | None = None
    has_derivatives: bool | None = None


class InsiderAggregates(BaseModel):
    """Computed dashboard-level statistics across all processed filings."""

    total_filings: int
    total_purchases: int
    total_sales: int
    total_other: int
    net_sentiment: int
    largest_transaction_value: float | None = None
    largest_transaction_insider: str | None = None
    plan_10b5_1_count: int = 0
    plan_10b5_1_ratio: float = 0.0
    activity_by_date: list[ActivityByDate] = []


class InsiderSummaryResponse(BaseModel):
    """Top-level response for the summary endpoint.

    Includes filings list, dashboard aggregates, and skipped_count to
    report how many filings failed to parse.
    """

    ticker: str
    form_type: str
    filings: list[InsiderFilingSummary]
    aggregates: InsiderAggregates
    total: int
    skipped_count: int = 0


class InsiderTransactionDetail(BaseModel):
    """One row per transaction from get_transaction_activities()."""

    transaction_type: str
    code: str
    description: str | None = None
    shares: float | None = None
    price_per_share: float | None = None
    value: float | None = None
    security_type: str | None = None
    security_title: str | None = None
    is_10b5_1_plan: bool | None = None
    is_derivative: bool = False


class InsiderDetailResponse(BaseModel):
    """Response for the per-filing detail endpoint.

    Keyed by accession_no which is the stable SEC filing identifier.
    """

    ticker: str
    filing_date: str
    accession_no: str
    insider_name: str
    position: str
    form_type: str
    transactions: list[InsiderTransactionDetail]
    market_trades_count: int = 0
    derivative_trades_count: int = 0
