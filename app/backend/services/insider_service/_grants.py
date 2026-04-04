"""Grants & exercises fetch worker for Form 4 derivative trades."""
import logging

import pandas as pd

from app.backend.models.insider_schemas import GrantRecord, GrantsResponse
from app.backend.services.insider_service._helpers import (
    TransactionSummaryProtocol,
    _classify_transaction_type,
    _coerce_float,
    _coerce_int,
    _ensure_identity,
)

logger = logging.getLogger(__name__)


def _fetch_grants(ticker: str, form_type: str, limit: int, offset: int) -> GrantsResponse:
    """Synchronous worker: iterate Form 4 filings and build per-trade grant records.

    For each filing, parses form4.derivative_trades into GrantRecord rows.
    Insider name and position are sourced from get_ownership_summary() when available,
    falling back to empty strings on failure. Per-filing errors increment skipped_count
    without aborting the response.

    Args:
        ticker: Stock ticker symbol.
        form_type: SEC form type string (e.g. '4').
        limit: Maximum number of filings to process.
        offset: Number of filings to skip before processing.

    Returns:
        GrantsResponse with all parsed records, total count, and skipped_count.
    """
    from edgar import Company

    _ensure_identity()
    company = Company(ticker)
    filings_iter = company.get_filings(form=form_type)

    records: list[GrantRecord] = []
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
            form4 = filing.obj()

            # Resolve insider identity from ownership summary when available.
            insider_name = ""
            position = ""
            try:
                summary = form4.get_ownership_summary()
                if isinstance(summary, TransactionSummaryProtocol):
                    insider_name = str(summary.insider_name) if isinstance(summary.insider_name, str) else ""
                    position = str(summary.position) if isinstance(summary.position, str) else ""
            except Exception:
                pass  # Identity unavailable; leave empty strings.

            derivative_df = form4.derivative_trades
            if not isinstance(derivative_df, pd.DataFrame) or derivative_df.empty:
                processed += 1
                continue

            for _, row in derivative_df.iterrows():
                code = str(row.get("Code") or "")
                acquired_disposed = str(row.get("AcquiredDisposed") or "")
                transaction_type = _classify_transaction_type(code, acquired_disposed)

                records.append(GrantRecord(
                    filing_date=filing_date,
                    accession_no=accession_no,
                    insider_name=insider_name,
                    position=position,
                    transaction_type=transaction_type,
                    security_title=str(row.get("Security") or ""),
                    exercise_price=_coerce_float(row.get("ExercisePrice")),
                    expiration_date=_safe_date_str(row.get("ExpirationDate")),
                    shares=_coerce_int(row.get("Shares")),
                    underlying_security=_safe_str(row.get("UnderlyingSecurity")),
                    acquired_disposed=acquired_disposed,
                    code=code,
                ))

            processed += 1
        except Exception as exc:
            logger.warning("Skipping grants filing %s for %s: %s", accession_no, ticker, exc)
            skipped_count += 1

    return GrantsResponse(
        ticker=ticker.upper(),
        records=records,
        total=len(records),
        skipped_count=skipped_count,
    )


def _safe_str(value: object) -> str | None:
    """Return str(value) if non-empty, else None."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _safe_date_str(value: object) -> str | None:
    """Return string representation of a date/datetime cell, or None."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s and s.lower() not in ("nat", "none", "nan") else None
