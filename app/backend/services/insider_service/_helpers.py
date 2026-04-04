"""Shared helpers: edgartools protocols, identity, type coercions, transaction classifier."""
import os
import logging
from collections.abc import Generator
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

_identity_set = False


# ---------------------------------------------------------------------------
# Protocols for edgartools ownership summary objects
# ---------------------------------------------------------------------------


@runtime_checkable
class TransactionSummaryProtocol(Protocol):
    """Protocol for edgartools TransactionSummary (Form 4 / Form 5)."""

    insider_name: str
    position: str
    primary_activity: str
    net_change: int | float
    net_value: float | None
    remaining_shares: int | None
    has_10b5_1_plan: bool | None
    transaction_types: list[str]
    transaction_count: int


@runtime_checkable
class InitialOwnershipSummaryProtocol(Protocol):
    """Protocol for edgartools InitialOwnershipSummary (Form 3)."""

    insider_name: str
    position: str
    total_holdings: int | None
    has_derivatives: bool | None


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def _ensure_identity() -> None:
    """Set SEC EDGAR identity (required before any edgartools call)."""
    global _identity_set
    if _identity_set:
        return
    from edgar import set_identity
    identity = os.environ.get("EDGAR_IDENTITY", "AIHedgeFund user@example.com")
    set_identity(identity)
    _identity_set = True


# ---------------------------------------------------------------------------
# Type coercion helpers
# ---------------------------------------------------------------------------


def _coerce_float(value: object) -> float | None:
    """Safely coerce an opaque edgartools value to float, returning None on failure.

    The ``object`` parameter type is intentional: edgartools returns untyped
    DataFrame cell values (numpy scalars, strings, None) that cannot be narrowed
    statically. We handle all failure modes via try/except.
    """
    if value is None:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _coerce_int(value: object) -> int | None:
    """Safely coerce an opaque edgartools value to int, returning None on failure.

    See _coerce_float for rationale on ``object`` parameter type.
    """
    if value is None:
        return None
    try:
        return int(str(value).split(".")[0])
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Transaction classifier
# ---------------------------------------------------------------------------


def _classify_transaction_type(code: str, acquired_disposed: str) -> str:
    """Map transaction code and A/D indicator to a human-readable type."""
    if acquired_disposed == "D":
        return "Sale"
    if code == "P":
        return "Purchase"
    if code in ("A", "G"):
        return "Grant"
    if code in ("M", "X"):
        return "Exercise"
    if code == "C":
        return "Conversion"
    return code or "Unknown"


# ---------------------------------------------------------------------------
# Shared filing iteration helper
# ---------------------------------------------------------------------------


def _iter_parsed_filings(
    ticker: str,
    form_type: str,
    limit: int,
    offset: int,
    skipped: list[int],
) -> Generator[tuple[object, str, str], None, None]:
    """Yield (ownership_obj, filing_date, accession_no) tuples, skipping failures.

    Iterates company filings of *form_type* for *ticker*, skipping the first
    *offset* entries and stopping after *limit* successfully processed filings.
    Filings that raise during ``filing.obj()`` are skipped; each failure
    increments ``skipped[0]`` so callers can report a ``skipped_count`` without
    managing the iteration boilerplate themselves.

    The *skipped* argument must be a single-element list, e.g. ``[0]``. Using
    a mutable container allows the generator to communicate the skip count back
    to the caller without requiring a wrapper class or a second pass.

    Args:
        ticker: Stock ticker symbol.
        form_type: SEC form type string (e.g. ``'4'``).
        limit: Maximum number of *successfully parsed* filings to yield.
        offset: Number of filings to skip before processing.
        skipped: Single-element list used as a mutable counter for failures.

    Yields:
        3-tuples of (ownership_obj, filing_date, accession_no).
    """
    from edgar import Company

    _ensure_identity()
    company = Company(ticker)
    filings_iter = company.get_filings(form=form_type)

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
            yield ownership, filing_date, accession_no
            processed += 1
        except Exception as exc:
            logger.warning("Skipping filing %s for %s: %s", accession_no, ticker, exc)
            skipped[0] += 1
