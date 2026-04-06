"""Pydantic schemas for insider trading data.

Defines all request/response models for the insider trading dashboard,
supporting Forms 3, 4, and 5 from the SEC EDGAR edgartools API.
Also defines schemas for the 13F-HR institutional holdings tab.
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


class OwnershipChangeRecord(BaseModel):
    """One row per Form 4 filing showing an insider's ownership change.

    shares_before is computed as remaining_shares - net_change. It is None
    when remaining_shares is not available in the filing.
    shares_after mirrors remaining_shares as reported to the SEC.
    """

    filing_date: str
    accession_no: str
    insider_name: str
    position: str
    shares_before: int | None = None
    shares_after: int | None = None
    net_change: int
    form_type: str


class OwnershipChangesResponse(BaseModel):
    """Top-level response for the ownership changes endpoint.

    records are ordered by filing_date ascending (oldest first) for chart rendering.
    insiders is a deduplicated list sorted by activity count (most active first),
    limited to top 10, used by the frontend to choose which lines to render.
    skipped_count reports how many filings failed to parse.
    """

    ticker: str
    records: list[OwnershipChangeRecord]
    insiders: list[str]
    total: int
    skipped_count: int = 0


class GrantRecord(BaseModel):
    """One row per derivative trade (grant, exercise, or conversion) from a Form 4 filing.

    Maps to a single row in the form4.derivative_trades DataFrame.
    Optional fields default to None when the filing does not include those columns.
    """

    filing_date: str
    accession_no: str
    insider_name: str
    position: str
    transaction_type: str
    security_title: str
    exercise_price: float | None = None
    expiration_date: str | None = None
    shares: int | None = None
    underlying_security: str | None = None
    acquired_disposed: str
    code: str


class GrantsResponse(BaseModel):
    """Top-level response for the grants & exercises endpoint.

    records is a flat list of derivative trade rows across all processed filings.
    skipped_count reports how many filings failed to parse.
    """

    ticker: str
    records: list[GrantRecord]
    total: int
    skipped_count: int = 0


class ThirteenFFilingListItem(BaseModel):
    """Lightweight filing entry for the paginated 13-F listing.

    Populated from PyArrow-backed Filings index attributes only — no
    ``filing.obj()`` call is made, keeping the listing endpoint fast.
    """

    filing_date: str
    accession_no: str
    company: str
    cik: int
    form: str


class ThirteenFListResponse(BaseModel):
    """Paginated response for GET /insider/thirteenf.

    has_more signals whether additional pages exist beyond the current offset.
    skipped_count reports filings that could not be parsed during extraction.
    """

    filings: list[ThirteenFFilingListItem]
    total: int
    has_more: bool
    skipped_count: int = 0


class CompareHoldingsRecord(BaseModel):
    """One row from the compare_holdings() DataFrame for quarter-over-quarter diff.

    All numeric fields are optional because a filing's first appearance has no
    previous quarter values (status='NEW') and a closed position has no current
    quarter values (status='CLOSED').
    """

    cusip: str
    ticker: str | None = None
    issuer: str
    shares: int | None = None
    prev_shares: int | None = None
    value: int | None = None
    prev_value: int | None = None
    share_change: int | None = None
    share_change_pct: float | None = None
    value_change: int | None = None
    value_change_pct: float | None = None
    status: str


class CompareHoldingsResponse(BaseModel):
    """Response for GET /insider/thirteenf/compare.

    Returns quarter-over-quarter holding comparison for a single filing
    identified by accession_no.
    """

    accession_no: str
    current_period: str
    previous_period: str
    manager_name: str
    records: list[CompareHoldingsRecord]
    total: int


class HoldingHistoryRecord(BaseModel):
    """One row from the holding_history() DataFrame for multi-period view.

    periods_data maps period date strings (e.g. '2025-12-31') to share counts
    or None when the holding was absent in that period. Using a nested dict
    avoids top-level dynamic keys and provides clean TypeScript typing.
    """

    cusip: str
    ticker: str | None = None
    issuer: str
    periods_data: dict[str, int | None]


class HoldingHistoryResponse(BaseModel):
    """Response for GET /insider/thirteenf/history.

    periods lists the date strings used as keys in each record's periods_data,
    ordered oldest-to-newest, enabling the frontend to render ordered columns.
    """

    accession_no: str
    manager_name: str
    periods: list[str]
    records: list[HoldingHistoryRecord]
    total: int
