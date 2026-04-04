"""Shared helpers: edgartools protocols, identity, type coercions, transaction classifier."""
import os
import logging
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
