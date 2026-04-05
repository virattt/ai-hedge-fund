"""Grants & exercises fetch worker for Form 4 derivative trades."""
import logging

import pandas as pd

from app.backend.models.insider_schemas import GrantRecord, GrantsResponse
from app.backend.services.insider_service._helpers import (
    TransactionSummary,
    _classify_transaction_type,
    _coerce_float,
    _coerce_int,
    _iter_parsed_filings,
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
    records: list[GrantRecord] = []
    skipped: list[int] = [0]

    for form4, filing_date, accession_no in _iter_parsed_filings(ticker, form_type, limit, offset, skipped):
        try:
            # Resolve insider identity from ownership summary when available.
            insider_name = ""
            position = ""
            try:
                summary = form4.get_ownership_summary()
                if isinstance(summary, TransactionSummary):
                    insider_name = str(summary.insider_name) if isinstance(summary.insider_name, str) else ""
                    position = str(summary.position) if isinstance(summary.position, str) else ""
            except Exception as exc:
                logger.debug("Could not extract insider identity for %s: %s", accession_no, exc)

            derivative_df = form4.derivative_trades
            if not isinstance(derivative_df, pd.DataFrame) or derivative_df.empty:
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

        except Exception as exc:
            logger.warning("Skipping grants filing %s for %s: %s", accession_no, ticker, exc)
            skipped[0] += 1

    return GrantsResponse(
        ticker=ticker.upper(),
        records=records,
        total=len(records),
        skipped_count=skipped[0],
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
