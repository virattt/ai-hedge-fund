"""Shared fixtures and helpers for insider service tests."""
from unittest.mock import MagicMock

from edgar.ownership.ownershipforms import (
    InitialOwnershipSummary,
    SecurityHolding,
    TransactionActivity,
    TransactionSummary,
)


def make_transaction_summary(
    *,
    insider_name: str = "Tim Cook",
    position: str = "CEO",
    net_change: int = -50000,
    net_value: float | None = 8_750_000.0,
    remaining_shares: int | None = 3_280_000,
    transaction_count: int = 2,
    primary_activity: str = "Sale",
    transaction_types: list[str] | None = None,
    has_10b5_1_plan: bool | None = True,
) -> TransactionSummary:
    """Build a real edgartools TransactionSummary for testing.

    Creates TransactionActivity objects that produce the desired computed properties.
    The ``primary_activity``, ``net_change``, ``net_value``, ``has_10b5_1_plan``, and
    ``transaction_types`` are all computed properties on TransactionSummary derived
    from the ``transactions`` list.
    """
    # Determine transaction_type string from primary_activity
    if "sale" in primary_activity.lower() or "sell" in primary_activity.lower():
        tx_type = "sale"
    elif "purchase" in primary_activity.lower() or "buy" in primary_activity.lower():
        tx_type = "purchase"
    elif "exercise" in primary_activity.lower():
        tx_type = "exercise"
    elif "award" in primary_activity.lower() or "grant" in primary_activity.lower():
        tx_type = "award"
    elif "tax" in primary_activity.lower():
        tx_type = "tax"
    elif "conversion" in primary_activity.lower():
        tx_type = "conversion"
    elif "mixed" in primary_activity.lower():
        tx_type = "purchase"  # will add a sale too
    else:
        tx_type = "sale"

    footnotes = "Pursuant to a Rule 10b5-1 trading plan" if has_10b5_1_plan is True else ""

    transactions: list[TransactionActivity] = []
    abs_shares = abs(net_change) if net_change else 0
    abs_value = abs(net_value) if net_value else 0
    price = (abs_value / abs_shares) if abs_shares and abs_value else None

    if primary_activity.lower() == "mixed transactions":
        # Create both purchase and sale
        half = abs_shares // 2 or 1
        transactions.append(TransactionActivity(
            transaction_type="purchase", code="P", shares=half, value=abs_value / 2 if abs_value else 0,
            price_per_share=price, security_title="Common Stock", footnotes_text=footnotes,
        ))
        transactions.append(TransactionActivity(
            transaction_type="sale", code="S", shares=half, value=abs_value / 2 if abs_value else 0,
            price_per_share=price, security_title="Common Stock", footnotes_text=footnotes,
        ))
    elif abs_shares > 0 or abs_value > 0:
        transactions.append(TransactionActivity(
            transaction_type=tx_type, code="S" if tx_type == "sale" else "P",
            shares=abs_shares, value=abs_value,
            price_per_share=price, security_title="Common Stock", footnotes_text=footnotes,
        ))

    # Add filler transactions to reach count
    for _ in range(max(0, transaction_count - len(transactions))):
        transactions.append(TransactionActivity(
            transaction_type=tx_type, code="S" if tx_type == "sale" else "P",
            shares=0, value=0, security_title="Common Stock", footnotes_text=footnotes,
        ))

    return TransactionSummary(
        reporting_date="2024-03-15",
        issuer_name="Apple Inc.",
        issuer_ticker="AAPL",
        insider_name=insider_name,
        position=position,
        form_type="4",
        transactions=transactions,
        remaining_shares=remaining_shares,
    )


def make_initial_ownership_summary(
    *,
    insider_name: str = "New Director",
    position: str = "Director",
    total_shares: int = 5000,
    has_derivatives: bool = False,
) -> InitialOwnershipSummary:
    """Build a real edgartools InitialOwnershipSummary (Form 3) for testing."""
    holdings: list[SecurityHolding] = []
    if total_shares > 0:
        holdings.append(SecurityHolding(
            security_type="non-derivative",
            security_title="Common Stock",
            shares=total_shares,
            direct_ownership=True,
        ))
    if has_derivatives:
        holdings.append(SecurityHolding(
            security_type="derivative",
            security_title="Stock Option",
            shares=1000,
            direct_ownership=True,
            exercise_price=150.0,
            expiration_date="2025-12-31",
        ))
    return InitialOwnershipSummary(
        reporting_date="2024-01-10",
        issuer_name="Apple Inc.",
        issuer_ticker="AAPL",
        insider_name=insider_name,
        position=position,
        form_type="3",
        holdings=holdings,
    )


def make_filing(
    *,
    accession_no: str = "0000320193-24-000081",
    filing_date: str = "2024-03-15",
    summary_result: TransactionSummary | InitialOwnershipSummary | None = None,
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
