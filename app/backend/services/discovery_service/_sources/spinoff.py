"""Discovery source: spin-off filings from the past 90 days.

Each spin-off contributes +20 to its CIK's score. Keyed by `cik:N` because
spin-off entities don't have public tickers yet.
"""

import logging
from datetime import date, timedelta

from app.backend.database import SessionLocal
from app.backend.database.models import SpinoffFiling
from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)


async def fetch() -> list[tuple[str, IdeaSignal]]:
    cutoff = (date.today() - timedelta(days=90)).isoformat()

    db = SessionLocal()
    try:
        rows = (
            db.query(SpinoffFiling)
            .filter(SpinoffFiling.filing_date >= cutoff)
            .order_by(SpinoffFiling.filing_date.desc())
            .limit(100)
            .all()
        )
    finally:
        db.close()

    out: list[tuple[str, IdeaSignal]] = []
    for r in rows:
        key = f"cik:{r.cik}"
        signal = IdeaSignal(
            source="spinoff",
            score=20.0,
            label=f"{r.form} filed {r.filing_date}",
            detail={
                "company": r.company,
                "form": r.form,
                "filing_date": r.filing_date,
                "cik": r.cik,
                "primary_doc_url": r.primary_doc_url,
            },
        )
        out.append((key, signal))
    return out
