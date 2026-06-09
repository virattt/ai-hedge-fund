"""Discovery source: C-suite Form 4 purchases at spin-off entities.

Universe = CIKs in spinoff_filings (bounded, fast). For each CIK, queries
Form 4 filings since the spin-off date and emits an IdeaSignal per qualifying
purchase (CEO/CFO/COO/President buying ≥ $250K). Score: 30 base, 50 if ≥ $1M.

Reuses the same fetcher as the csuite_buy alert rule.
"""

import asyncio
import logging

from app.backend.database import SessionLocal
from app.backend.database.models import SpinoffFiling
from app.backend.models.discovery_schemas import IdeaSignal
from app.backend.services.catalyst_service._insiders import fetch_insider_purchases_by_cik

logger = logging.getLogger(__name__)

_CSUITE_TITLE_TOKENS = (
    "ceo", "cfo", "coo", "president",
    "chief executive", "chief financial", "chief operating",
)
_MIN_VALUE = 250_000.0
_BIG_VALUE = 1_000_000.0


async def fetch() -> list[tuple[str, IdeaSignal]]:
    db = SessionLocal()
    try:
        rows = db.query(SpinoffFiling.cik, SpinoffFiling.filing_date).all()
    finally:
        db.close()

    # one CIK can appear multiple times across filings — keep earliest as floor
    cik_since: dict[int, str] = {}
    for cik, fd in rows:
        if cik not in cik_since or (fd and fd < cik_since[cik]):
            cik_since[cik] = fd

    out: list[tuple[str, IdeaSignal]] = []
    for cik, since_date in cik_since.items():
        try:
            summary = await asyncio.to_thread(
                fetch_insider_purchases_by_cik, cik, since_date, 15
            )
        except Exception as exc:
            logger.debug("csuite_buy source: skip CIK %s (%s)", cik, exc)
            continue

        for p in summary.purchases:
            value = p.value or 0
            if value < _MIN_VALUE:
                continue
            title_lc = (p.insider_title or "").lower()
            if not any(tok in title_lc for tok in _CSUITE_TITLE_TOKENS):
                continue

            score = 50.0 if value >= _BIG_VALUE else 30.0
            label = f"{p.insider_title or 'C-level'} bought ${value:,.0f}"

            out.append((
                f"cik:{cik}",
                IdeaSignal(
                    source="csuite_buy",
                    score=score,
                    label=label,
                    detail={
                        "cik": cik,
                        "insider_name": p.insider_name,
                        "insider_title": p.insider_title,
                        "shares": p.shares,
                        "price_per_share": p.price_per_share,
                        "value": value,
                        "filing_date": p.filing_date,
                        "accession_no": p.accession_no,
                    },
                ),
            ))
    return out
