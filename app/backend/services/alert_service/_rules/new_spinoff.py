"""new_spinoff rule — fires once per new Form 10/10-12B filing in spinoff_filings.

Reads from the local DB (populated by the Catalysts page sync). The framework's
de-dupe on (rule_type, ticker) within 3 days handles "new vs already-seen" — we
just emit a candidate per row and let the engine drop repeats.
"""

import logging

from app.backend.database import SessionLocal
from app.backend.database.models import SpinoffFiling
from app.backend.services.alert_service._types import AlertCandidate

logger = logging.getLogger(__name__)


async def evaluate(_thresholds: dict) -> list[AlertCandidate]:
    db = SessionLocal()
    try:
        rows = (
            db.query(SpinoffFiling)
            .order_by(SpinoffFiling.filing_date.desc())
            .limit(50)
            .all()
        )
    finally:
        db.close()

    out: list[AlertCandidate] = []
    for r in rows:
        out.append(AlertCandidate(
            rule_type="new_spinoff",
            ticker=str(r.cik),  # de-dupe key: once per CIK
            title=f"New spin-off filing: {r.company}",
            message=(
                f"{r.company} (CIK {r.cik}) filed a {r.form} on {r.filing_date}.\n"
                f"This is a registration statement — likely a spin-off, IPO, or new public entity.\n"
                f"View: {r.primary_doc_url or 'sec.gov'}"
            ),
            payload={
                "cik": r.cik,
                "company": r.company,
                "form": r.form,
                "filing_date": r.filing_date,
                "primary_doc_url": r.primary_doc_url,
            },
            severity="warning",
        ))
    return out
