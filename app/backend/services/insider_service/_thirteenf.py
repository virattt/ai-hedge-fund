"""13F-HR institutional holdings worker functions.

Provides three worker functions for fetching 13F-HR filing data from the
SEC EDGAR API via edgartools:

- _fetch_thirteenf_filings: paginated listing of all 13F-HR filings
- _fetch_compare_holdings: quarter-over-quarter holding comparison for a filing
- _fetch_holding_history: multi-period holding history for a filing

A shared _load_thirteenf_report helper (LRU-cached) handles the
find() -> filing.obj() lookup so that both detail functions avoid
duplicate XML parsing for the same accession number.
"""
import logging
from functools import lru_cache
from typing import Protocol

import pandas as pd

from app.backend.models.insider_schemas import (
    CompareHoldingsRecord,
    CompareHoldingsResponse,
    HoldingHistoryRecord,
    HoldingHistoryResponse,
    ThirteenFFilingListItem,
    ThirteenFListResponse,
)
from app.backend.services.insider_service._helpers import (
    _ensure_identity,
    _sanitize_dataframe_records,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocols for edgartools objects (avoids type: ignore on attribute access)
# ---------------------------------------------------------------------------


class _FilingProto(Protocol):
    """Minimal structural type for an edgartools Filing object."""

    company: str
    cik: int
    filing_date: str
    accession_no: str
    form: str

    def obj(self) -> "_ThirteenFProto": ...


class _FilingsProto(Protocol):
    """Minimal structural type for an edgartools Filings collection."""

    def __len__(self) -> int: ...
    def __iter__(self) -> "_FilingsIterProto": ...
    def __getitem__(self, s: slice) -> "_FilingsProto": ...


class _FilingsIterProto(Protocol):
    def __next__(self) -> _FilingProto: ...
    def __iter__(self) -> "_FilingsIterProto": ...


class _HoldingsComparisonProto(Protocol):
    data: pd.DataFrame
    current_period: str
    previous_period: str
    manager_name: str


class _HoldingsHistoryProto(Protocol):
    data: pd.DataFrame
    periods: list[str]
    manager_name: str


class _ThirteenFProto(Protocol):
    """Minimal structural type for an edgartools ThirteenF report object."""

    def compare_holdings(self) -> "_HoldingsComparisonProto | None": ...
    def holding_history(self, periods: int) -> "_HoldingsHistoryProto | None": ...


# ---------------------------------------------------------------------------
# Fixed column names used in history DataFrame from edgartools
# ---------------------------------------------------------------------------

_HISTORY_FIXED_COLS = ("Cusip", "Ticker", "Issuer")


# ---------------------------------------------------------------------------
# Module-level edgar shims — patched in tests via patch.object(_thirteenf, ...)
# ---------------------------------------------------------------------------


def _get_filings(**kwargs: object) -> _FilingsProto:
    """Thin wrapper around edgar.get_filings so tests can patch it."""
    from edgar import get_filings
    result: _FilingsProto = get_filings(**kwargs)
    return result


def _find_filing(accession_no: str) -> _FilingProto | None:
    """Thin wrapper around edgar.find so tests can patch it."""
    from edgar import find
    result: _FilingProto | None = find(accession_no)
    return result


# ---------------------------------------------------------------------------
# Shared helper: load a parsed ThirteenF report object (LRU-cached)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=32)
def _load_thirteenf_report(accession_no: str) -> _ThirteenFProto:
    """Return a parsed ThirteenF report object for the given accession number.

    Calls _ensure_identity() first, then resolves the filing via
    edgar.find() and parses it with filing.obj(). Results are cached by
    accession number (maxsize=32) to avoid duplicate XML parsing when both
    compare and history are requested for the same filing.

    Args:
        accession_no: SEC accession number in ``NNNNNNNNNN-YY-NNNNNN`` format.

    Returns:
        Parsed ThirteenF report object from edgartools.

    Raises:
        ValueError: If no filing is found for the given accession number.
        RuntimeError: If the SEC API raises an unexpected error during find().
    """
    _ensure_identity()
    try:
        filing = _find_filing(accession_no)
    except Exception as exc:
        raise RuntimeError(
            f"SEC API error while looking up filing {accession_no}: {exc}"
        ) from exc

    if filing is None:
        raise ValueError(f"Filing {accession_no} not found in EDGAR")

    return filing.obj()


# ---------------------------------------------------------------------------
# Worker: paginated listing
# ---------------------------------------------------------------------------


def _fetch_thirteenf_filings(
    limit: int,
    offset: int,
    year: int | None,
    quarter: int | None,
) -> ThirteenFListResponse:
    """Fetch a paginated slice of 13F-HR filings from SEC EDGAR.

    Calls _ensure_identity() first, then invokes edgar.get_filings() with
    ``form="13F-HR"`` and optional year/quarter filters. Slices the PyArrow-
    backed Filings index directly — no filing.obj() calls — keeping this
    function fast for listing purposes.

    Args:
        limit: Maximum number of filings to return (page size).
        offset: Number of filings to skip before the current page.
        year: Optional filing year filter; passed to get_filings() when not None.
        quarter: Optional filing quarter filter (1–4); passed when not None.

    Returns:
        ThirteenFListResponse with lightweight filing entries, total count,
        has_more flag, and skipped_count (always 0 for this endpoint).

    Raises:
        RuntimeError: If edgar.get_filings() raises an unexpected SEC API error.
    """
    logger.debug("Fetching 13F-HR filings limit=%d offset=%d year=%s quarter=%s", limit, offset, year, quarter)
    _ensure_identity()

    kwargs: dict[str, object] = {"form": "13F-HR"}
    if year is not None:
        kwargs["year"] = year
    if quarter is not None:
        kwargs["quarter"] = quarter

    try:
        filings = _get_filings(**kwargs)
    except Exception as exc:
        raise RuntimeError(
            f"SEC API error while fetching 13F-HR filings: {exc}"
        ) from exc

    total = len(filings)
    logger.debug("13F-HR filings total=%d returning slice offset=%d limit=%d", total, offset, limit)
    page = filings[offset: offset + limit]
    has_more = (offset + limit) < total

    items: list[ThirteenFFilingListItem] = []
    for filing in page:
        items.append(
            ThirteenFFilingListItem(
                filing_date=str(filing.filing_date),
                accession_no=str(filing.accession_no),
                company=str(filing.company),
                cik=int(filing.cik),
                form=str(filing.form),
            )
        )

    return ThirteenFListResponse(
        filings=items,
        total=total,
        has_more=has_more,
        skipped_count=0,
    )


# ---------------------------------------------------------------------------
# Worker: compare holdings
# ---------------------------------------------------------------------------


def _fetch_compare_holdings(accession_no: str) -> CompareHoldingsResponse:
    """Return quarter-over-quarter holding comparison for a single 13F-HR filing.

    Loads the report via _load_thirteenf_report (LRU-cached), calls
    compare_holdings() on the ThirteenF object, then sanitizes the resulting
    DataFrame with _sanitize_dataframe_records() before constructing the
    response.

    Args:
        accession_no: SEC accession number in ``NNNNNNNNNN-YY-NNNNNN`` format.

    Returns:
        CompareHoldingsResponse with records, period metadata, and total count.

    Raises:
        ValueError: If _load_thirteenf_report raises (filing not found) or if
            compare_holdings() returns None (no previous quarter available).
        RuntimeError: Propagated from _load_thirteenf_report on SEC API errors.
    """
    logger.debug("Fetching compare holdings for filing %s", accession_no)
    report = _load_thirteenf_report(accession_no)
    comparison = report.compare_holdings()

    if comparison is None:
        logger.warning("compare_holdings() returned None for filing %s (no previous quarter available)", accession_no)
        raise ValueError(
            f"No comparison data available for filing {accession_no} (no previous quarter found)"
        )

    raw_records = _sanitize_dataframe_records(comparison.data)
    records: list[CompareHoldingsRecord] = [
        CompareHoldingsRecord(
            cusip=str(row.get("Cusip", "")),
            ticker=row.get("Ticker") or None,
            issuer=str(row.get("Issuer", "")),
            shares=row.get("Shares"),
            prev_shares=row.get("Prev_Shares"),
            value=row.get("Value"),
            prev_value=row.get("Prev_Value"),
            share_change=row.get("Share_Change"),
            share_change_pct=row.get("Share_Change_Pct"),
            value_change=row.get("Value_Change"),
            value_change_pct=row.get("Value_Change_Pct"),
            status=str(row.get("Status", "")),
        )
        for row in raw_records
    ]

    logger.debug("compare_holdings built %d records for filing %s (%s vs %s)", len(records), accession_no, comparison.current_period, comparison.previous_period)
    return CompareHoldingsResponse(
        accession_no=accession_no,
        current_period=str(comparison.current_period),
        previous_period=str(comparison.previous_period),
        manager_name=str(comparison.manager_name),
        records=records,
        total=len(records),
    )


# ---------------------------------------------------------------------------
# Worker: holding history
# ---------------------------------------------------------------------------


def _fetch_holding_history(accession_no: str, periods: int) -> HoldingHistoryResponse:
    """Return multi-period holding history for a single 13F-HR filing.

    Loads the report via _load_thirteenf_report (LRU-cached), calls
    holding_history(periods=periods), then transforms the DataFrame so that
    dynamic period columns (date strings) are nested into a ``periods_data``
    dict per record instead of being top-level keys.

    The fixed columns (Cusip, Ticker, Issuer) are extracted first; all
    remaining column names are treated as period date strings.

    Args:
        accession_no: SEC accession number in ``NNNNNNNNNN-YY-NNNNNN`` format.
        periods: Number of historical periods to include (passed to edgartools).

    Returns:
        HoldingHistoryResponse with records, ordered period list, and total count.

    Raises:
        ValueError: If _load_thirteenf_report raises (filing not found) or if
            holding_history() returns None.
        RuntimeError: Propagated from _load_thirteenf_report on SEC API errors.
    """
    logger.debug("Fetching holding history for filing %s periods=%d", accession_no, periods)
    report = _load_thirteenf_report(accession_no)
    history = report.holding_history(periods=periods)

    if history is None:
        logger.warning("holding_history() returned None for filing %s", accession_no)
        raise ValueError(
            f"No holding history available for filing {accession_no}"
        )

    df = history.data
    # Identify period columns: all columns not in the fixed set
    all_cols: list[str] = list(df.columns)
    period_cols = [c for c in all_cols if c not in _HISTORY_FIXED_COLS]

    raw_records = _sanitize_dataframe_records(df)
    records: list[HoldingHistoryRecord] = [
        HoldingHistoryRecord(
            cusip=str(row.get("Cusip", "")),
            ticker=row.get("Ticker") or None,
            issuer=str(row.get("Issuer", "")),
            periods_data={col: row.get(col) for col in period_cols},
        )
        for row in raw_records
    ]

    logger.debug("holding_history built %d records across %d periods for filing %s", len(records), len(period_cols), accession_no)
    return HoldingHistoryResponse(
        accession_no=accession_no,
        manager_name=str(history.manager_name),
        periods=period_cols,
        records=records,
        total=len(records),
    )
