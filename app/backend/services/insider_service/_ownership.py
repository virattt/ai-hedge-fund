"""Ownership changes fetch worker."""
import logging
from collections import Counter

from app.backend.models.insider_schemas import OwnershipChangeRecord, OwnershipChangesResponse
from app.backend.services.insider_service._helpers import (
    TransactionSummaryProtocol,
    _coerce_int,
    _ensure_identity,
)

logger = logging.getLogger(__name__)

_TOP_INSIDERS_LIMIT = 10


def _fetch_ownership_changes(ticker: str, form_type: str, limit: int, offset: int) -> OwnershipChangesResponse:
    """Synchronous worker: iterate Form 4 filings and build per-filing ownership records.

    For each filing, computes shares_before = remaining_shares - net_change.
    When remaining_shares is None, both shares_before and shares_after are None.
    Returns records ordered by filing_date ascending (oldest first for chart rendering).
    The insiders list is sorted by activity count descending, capped at top 10.
    Filings that raise during obj() or get_ownership_summary() are skipped and
    increment skipped_count without aborting the response.
    """
    from edgar import Company

    _ensure_identity()
    company = Company(ticker)
    filings_iter = company.get_filings(form=form_type)

    records: list[OwnershipChangeRecord] = []
    skipped_count = 0
    processed = 0
    skipped_offset = 0

    for filing in filings_iter:
        if skipped_offset < offset:
            skipped_offset += 1
            continue
        if processed >= limit:
            break

        accession_no = str(filing.accession_no)
        filing_date = str(filing.filing_date)

        try:
            ownership = filing.obj()
            summary = ownership.get_ownership_summary()
            if not isinstance(summary, TransactionSummaryProtocol):
                processed += 1
                continue

            remaining = _coerce_int(summary.remaining_shares)
            net_change = int(summary.net_change or 0)
            shares_before = (remaining - net_change) if remaining is not None else None

            records.append(OwnershipChangeRecord(
                filing_date=filing_date,
                accession_no=accession_no,
                insider_name=summary.insider_name,
                position=summary.position,
                shares_before=shares_before,
                shares_after=remaining,
                net_change=net_change,
                form_type=form_type,
            ))
            processed += 1
        except Exception as exc:
            logger.warning("Skipping ownership filing %s for %s: %s", accession_no, ticker, exc)
            skipped_count += 1

    records.sort(key=lambda r: r.filing_date)

    activity_counts: Counter[str] = Counter(r.insider_name for r in records)
    insiders = [name for name, _ in activity_counts.most_common(_TOP_INSIDERS_LIMIT)]

    return OwnershipChangesResponse(
        ticker=ticker.upper(),
        records=records,
        insiders=insiders,
        total=len(records),
        skipped_count=skipped_count,
    )
