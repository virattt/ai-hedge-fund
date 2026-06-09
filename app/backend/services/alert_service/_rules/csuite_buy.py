"""csuite_buy rule — fires when CEO/CFO/COO/President buys >= min_value at a spin-off entity.

Universe: CIKs in the spinoff_filings table. Reuses fetch_insider_purchases_by_cik()
which already scopes filings to >= the spin-off filing date and silences edgar noise.
"""

import asyncio
import logging

from app.backend.database import SessionLocal
from app.backend.database.models import SpinoffFiling
from app.backend.services.alert_service._types import AlertCandidate
from app.backend.services.catalyst_service._insiders import fetch_insider_purchases_by_cik

logger = logging.getLogger(__name__)

_CSUITE_TITLE_TOKENS = (
    "ceo",
    "cfo",
    "coo",
    "president",
    "chief executive",
    "chief financial",
    "chief operating",
)


async def evaluate(thresholds: dict) -> list[AlertCandidate]:
    min_value = float(thresholds.get("min_value", 250_000.0))

    db = SessionLocal()
    try:
        rows = db.query(SpinoffFiling.cik, SpinoffFiling.filing_date).all()
    finally:
        db.close()

    # One CIK can have multiple Form 10 amendments; keep the earliest filing date
    cik_since: dict[int, str] = {}
    for cik, fd in rows:
        if cik not in cik_since or (fd and fd < cik_since[cik]):
            cik_since[cik] = fd

    out: list[AlertCandidate] = []
    for cik, since_date in cik_since.items():
        try:
            # Sync EDGAR call — wrap in to_thread to avoid blocking the event loop
            summary = await asyncio.to_thread(
                fetch_insider_purchases_by_cik, cik, since_date, 30
            )
        except Exception as exc:
            logger.debug("csuite_buy: failed to fetch insiders for CIK %s: %s", cik, exc)
            continue

        for p in summary.purchases:
            if (p.value or 0) < min_value:
                continue
            title_lc = (p.insider_title or "").lower()
            if not any(tok in title_lc for tok in _CSUITE_TITLE_TOKENS):
                continue

            # de-dupe key: cik + accession_no truncated to 20 chars (column limit)
            ticker_key = f"{cik}:{p.accession_no}"[:20]

            out.append(AlertCandidate(
                rule_type="csuite_buy",
                ticker=ticker_key,
                title=f"C-level buy: CIK {cik} · ${(p.value or 0):,.0f}",
                message=(
                    f"{p.insider_name} ({p.insider_title or '?'}) bought "
                    f"{(p.shares or 0):,.0f} shares "
                    f"@ ${(p.price_per_share or 0):.2f} = ${(p.value or 0):,.0f}\n"
                    f"Filed: {p.filing_date}\n"
                    f"CIK {cik} (recent spin-off entity)"
                ),
                payload={
                    "cik": cik,
                    "insider_name": p.insider_name,
                    "insider_title": p.insider_title,
                    "shares": p.shares,
                    "price_per_share": p.price_per_share,
                    "value": p.value,
                    "filing_date": p.filing_date,
                    "accession_no": p.accession_no,
                },
                severity="critical" if (p.value or 0) >= 1_000_000 else "warning",
            ))
    return out
