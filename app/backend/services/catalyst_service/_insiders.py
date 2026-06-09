"""Fetch Form 4 purchases for a given CIK (used to validate spin-off setups).

Queries SEC EDGAR via edgartools `Company(cik).get_filings(form="4")`. Filters
the parsed `market_trades` DataFrame for code == "P" (open-market purchases).

When `since_date` is provided, iteration stops as soon as we hit a Form 4 older
than that date — spin-off entities may share a CIK with an old shell that has
years of irrelevant pre-spin filings (e.g. CIK 96664 went back to 2001).
"""

import logging

import pandas as pd

from app.backend.models.catalyst_schemas import InsiderPurchase, SpinoffInsiderSummary
from app.backend.services.insider_service._helpers import (
    InitialOwnershipSummary,
    TransactionSummary,
    _coerce_float,
    _ensure_identity,
)

logger = logging.getLogger(__name__)


def _extract_owner(ownership) -> tuple[str, str | None]:
    """Pull insider name + title from a Form 4 ownership object, with fallbacks."""
    name = ""
    title: str | None = None
    try:
        summary = ownership.get_ownership_summary()
        if isinstance(summary, (TransactionSummary, InitialOwnershipSummary)):
            name = summary.insider_name or ""
            title = summary.position or None
    except Exception:
        pass
    if not name:
        try:
            ro = getattr(ownership, "reporting_owner", None)
            if ro is not None:
                name = str(getattr(ro, "name", "")) or ""
        except Exception:
            pass
    return name, title


def fetch_insider_purchases_by_cik(
    cik: int,
    since_date: str | None = None,
    max_filings: int = 50,
) -> SpinoffInsiderSummary:
    """Query EDGAR for Form 4 filings by CIK, filter to purchases (code='P').

    Args:
        cik: SEC central index key for the spin-off entity.
        since_date: ISO date (YYYY-MM-DD). Stop iterating once filings are
            older than this — typically the spin-off Form 10 filing date.
            Form 4s before the spin-off are noise from a prior shell entity.
        max_filings: hard cap on filings scanned even within the window.
    """
    _ensure_identity()
    from edgar import Company

    purchases: list[InsiderPurchase] = []
    total_value = 0.0

    # Suppress the noisy edgar.core warnings from per-filing parsing
    edgar_logger = logging.getLogger("edgar.core")
    prev_level = edgar_logger.level
    edgar_logger.setLevel(logging.ERROR)

    try:
        try:
            company = Company(str(cik))
            filings_iter = company.get_filings(form="4")
        except Exception as exc:
            logger.warning("Could not load Form 4 filings for CIK %s: %s", cik, exc)
            return SpinoffInsiderSummary(cik=cik, purchase_count=0, total_value=0.0, purchases=[], cached=False)

        scanned = 0
        for filing in filings_iter:
            if scanned >= max_filings:
                break

            try:
                filing_date = str(filing.filing_date)[:10]
            except Exception:
                continue

            # Stop once we cross the spin-off date — pre-spin filings aren't relevant
            if since_date and filing_date < since_date:
                break

            scanned += 1

            try:
                ownership = filing.obj()
            except Exception:
                continue

            df = getattr(ownership, "market_trades", None)
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue

            insider_name, insider_title = _extract_owner(ownership)
            accession_no = str(filing.accession_no)

            for _, row in df.iterrows():
                code = str(row.get("Code") or "").upper()
                if code != "P":
                    continue
                shares = _coerce_float(row.get("Shares"))
                price = _coerce_float(row.get("Price"))
                value = round(shares * price, 2) if shares is not None and price is not None else None
                purchases.append(InsiderPurchase(
                    filing_date=filing_date,
                    accession_no=accession_no,
                    insider_name=insider_name or "Unknown",
                    insider_title=insider_title,
                    shares=shares,
                    price_per_share=price,
                    value=value,
                ))
                if value:
                    total_value += value
    finally:
        edgar_logger.setLevel(prev_level)

    purchases.sort(key=lambda p: p.filing_date, reverse=True)

    return SpinoffInsiderSummary(
        cik=cik,
        purchase_count=len(purchases),
        total_value=round(total_value, 2),
        purchases=purchases,
        cached=False,
    )
