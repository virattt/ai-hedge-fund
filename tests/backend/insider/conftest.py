"""Shared fixtures and helpers for insider service tests."""
from types import SimpleNamespace
from unittest.mock import MagicMock


def make_transaction_summary(
    *,
    insider_name: str = "Tim Cook",
    position: str = "CEO",
    primary_activity: str = "Sale",
    net_change: int = -50000,
    net_value: float | None = 8_750_000.0,
    remaining_shares: int | None = 3_280_000,
    has_10b5_1_plan: bool | None = True,
    transaction_types: list[str] | None = None,
    transaction_count: int = 2,
) -> SimpleNamespace:
    """Build a fake edgartools TransactionSummary with only the declared attributes.

    Uses SimpleNamespace instead of MagicMock so that runtime_checkable Protocol
    isinstance checks correctly distinguish TransactionSummary from
    InitialOwnershipSummary (MagicMock satisfies every Protocol indiscriminately).
    """
    return SimpleNamespace(
        insider_name=insider_name,
        position=position,
        primary_activity=primary_activity,
        net_change=net_change,
        net_value=net_value,
        remaining_shares=remaining_shares,
        has_10b5_1_plan=has_10b5_1_plan,
        transaction_types=transaction_types if transaction_types is not None else ["Sale"],
        transaction_count=transaction_count,
    )


def make_initial_ownership_summary(
    *,
    insider_name: str = "New Director",
    position: str = "Director",
    total_holdings: int = 5000,
    has_derivatives: bool = False,
) -> SimpleNamespace:
    """Build a fake edgartools InitialOwnershipSummary (Form 3).

    Uses SimpleNamespace so the object only has Form-3 attributes, enabling
    correct Protocol dispatch in _build_filing_summary().
    """
    return SimpleNamespace(
        insider_name=insider_name,
        position=position,
        total_holdings=total_holdings,
        has_derivatives=has_derivatives,
    )


def make_filing(
    *,
    accession_no: str = "0000320193-24-000081",
    filing_date: str = "2024-03-15",
    summary_result: SimpleNamespace | None = None,
    raise_on_obj: Exception | None = None,
) -> MagicMock:
    """Build a mock edgartools Filing object."""
    filing = MagicMock()
    filing.accession_no = accession_no
    filing.filing_date = filing_date

    if raise_on_obj is not None:
        filing.obj.side_effect = raise_on_obj
    else:
        ownership = MagicMock()
        ownership.get_ownership_summary.return_value = summary_result
        filing.obj.return_value = ownership

    return filing
