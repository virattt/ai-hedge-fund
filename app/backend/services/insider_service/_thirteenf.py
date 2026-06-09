"""13F-HR institutional holdings — shared types and filings listing.

Protocols for edgartools objects, enrichment helper, edgar shims, and the
paginated filing listing worker live here. Company list functions are in
_thirteenf_companies.py; compare/history detail workers are in
_thirteenf_detail.py.
"""
import logging
from typing import Protocol

import pandas as pd

from app.backend.models.insider_schemas import (
    ThirteenFFilingListItem,
    ThirteenFListResponse,
)
from app.backend.services.insider_service._helpers import _ensure_identity

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
    def filter(self, *, cik: object = None) -> "_FilingsProto": ...
    def find(self, name: str) -> "_FilingsProto": ...


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

    @property
    def signer(self) -> str | None: ...
    @property
    def filing_signer_title(self) -> str | None: ...
    @property
    def total_value(self) -> object: ...
    @property
    def total_holdings(self) -> int | None: ...

    def compare_holdings(self) -> "_HoldingsComparisonProto | None": ...
    def holding_history(self, periods: int) -> "_HoldingsHistoryProto | None": ...


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
# Enrichment helper
# ---------------------------------------------------------------------------


def _enrich_filing_item(filing: _FilingProto) -> ThirteenFFilingListItem:
    """Build a ThirteenFFilingListItem, attempting to enrich with report data."""
    item = ThirteenFFilingListItem(
        filing_date=str(filing.filing_date),
        accession_no=str(filing.accession_no),
        company=str(filing.company),
        cik=int(filing.cik),
        form=str(filing.form),
    )
    try:
        report: _ThirteenFProto = filing.obj()
        item.signer_name = report.signer
        item.signer_title = report.filing_signer_title
        tv = report.total_value
        item.total_value = float(tv) if tv is not None else None
        item.total_holdings = report.total_holdings
    except Exception:
        logger.debug("Could not enrich filing %s", filing.accession_no, exc_info=True)
    return item


# ---------------------------------------------------------------------------
# Worker: paginated listing
# ---------------------------------------------------------------------------


def _fetch_thirteenf_filings(
    limit: int,
    offset: int,
    year: int | None,
    quarter: int | None,
    company_name: str | None = None,
    cik_list: list[int] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> ThirteenFListResponse:
    """Fetch a paginated slice of 13F-HR filings from SEC EDGAR."""
    logger.debug("Fetching 13F-HR filings limit=%d offset=%d year=%s quarter=%s company_name=%s", limit, offset, year, quarter, company_name)
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

    # Apply date range filter before any other filtering/pagination
    if date_from or date_to:
        filtered = []
        for filing in filings:
            fd = str(filing.filing_date)[:10]
            if date_from and fd < date_from:
                continue
            if date_to and fd > date_to:
                continue
            filtered.append(filing)
        filings = filtered

    if company_name is not None:
        try:
            found = filings.find(company_name)
        except Exception as exc:
            raise RuntimeError(
                f"SEC company search error for '{company_name}': {exc}"
            ) from exc

        if len(found) > 0:
            filings = found
        else:
            query_lower = company_name.lower()
            matched: list[ThirteenFFilingListItem] = []
            for filing in filings:
                if query_lower in str(filing.company).lower():
                    matched.append(_enrich_filing_item(filing))
            total_matched = len(matched)
            return ThirteenFListResponse(
                filings=matched[offset: offset + limit],
                total=total_matched,
                has_more=(offset + limit) < total_matched,
                skipped_count=0,
            )

    if cik_list:
        cik_set = set(cik_list)
        matched_items: list[ThirteenFFilingListItem] = []
        for filing in filings:
            if int(filing.cik) in cik_set:
                matched_items.append(_enrich_filing_item(filing))
        total_matched = len(matched_items)
        return ThirteenFListResponse(
            filings=matched_items[offset: offset + limit],
            total=total_matched,
            has_more=(offset + limit) < total_matched,
            skipped_count=0,
        )

    total = len(filings)
    page = filings[offset: offset + limit]
    has_more = (offset + limit) < total
    items = [_enrich_filing_item(filing) for filing in page]

    return ThirteenFListResponse(
        filings=items,
        total=total,
        has_more=has_more,
        skipped_count=0,
    )
