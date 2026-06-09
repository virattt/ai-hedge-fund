"""Fetch SEC Form 10 / 10-12B filings + sync to local DB.

Uses SEC EDGAR's full-text search API (efts.sec.gov) which is designed for
cross-company filing queries. The edgartools `get_filings(form=...)` bulk-index
approach 403s without per-file authenticated downloads, so we use the public
search endpoint instead.
"""

import logging
import os
from datetime import date, timedelta

import httpx
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.backend.database import SessionLocal
from app.backend.database.models import SpinoffFiling
from app.backend.models.catalyst_schemas import SpinoffFilingItem

logger = logging.getLogger(__name__)


class SpinoffFetchError(Exception):
    pass


_SPINOFF_FORMS = ["10-12B", "10-12B/A", "10"]
_EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
_EDGAR_DOC_BASE = "https://www.sec.gov/Archives/edgar/data"


def _user_agent() -> str:
    """SEC requires a User-Agent identifying the requester."""
    return os.environ.get("EDGAR_IDENTITY", "AI Hedge Fund research@local")


def _doc_url(cik: int, accession_no: str, primary_doc: str | None) -> str:
    acc_clean = accession_no.replace("-", "")
    if primary_doc:
        return f"{_EDGAR_DOC_BASE}/{cik}/{acc_clean}/{primary_doc}"
    return f"{_EDGAR_DOC_BASE}/{cik}/{acc_clean}/"


def _search_filings(form: str, date_from: str, date_to: str) -> list[dict]:
    """Hit EDGAR full-text search for a given form type in a date range."""
    headers = {
        "User-Agent": _user_agent(),
        "Accept": "application/json",
    }
    params = {
        "q": "",
        "dateRange": "custom",
        "startdt": date_from,
        "enddt": date_to,
        "forms": form,
    }
    out: list[dict] = []
    try:
        with httpx.Client(timeout=30.0, headers=headers) as client:
            resp = client.get(_EDGAR_SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("EDGAR search failed for form=%s: %s", form, exc)
        return out

    hits = (data.get("hits") or {}).get("hits") or []
    for hit in hits:
        src = hit.get("_source") or {}
        adsh = src.get("adsh")
        if not adsh:
            continue
        ciks = src.get("ciks") or []
        cik = int(ciks[0]) if ciks else 0
        display_names = src.get("display_names") or []
        company = display_names[0] if display_names else "Unknown"
        if " (CIK " in company:
            company = company.split(" (CIK ")[0]
        primary_doc = (src.get("xsl") or src.get("file_type"))
        # The actual primary doc filename is in the `id` field of the hit
        hit_id = hit.get("_id", "")
        primary_doc_name = hit_id.split(":")[-1] if ":" in hit_id else None
        out.append({
            "accession_no": adsh,
            "cik": cik,
            "company": company,
            "form": (src.get("form") or form).strip(),
            "filing_date": (src.get("file_date") or "")[:10],
            "primary_doc_url": _doc_url(cik, adsh, primary_doc_name),
            "primary_doc_description": src.get("display_names_pf") or None,
        })
    return out


def fetch_recent_spinoffs(days_back: int = 90) -> int:
    """Query SEC EDGAR full-text search for recent Form 10/10-12B filings.

    Upserts into `spinoff_filings` table. Returns count synced.
    """
    today = date.today()
    date_from = (today - timedelta(days=days_back)).isoformat()
    date_to = today.isoformat()

    all_filings: list[dict] = []
    for form in _SPINOFF_FORMS:
        all_filings.extend(_search_filings(form, date_from, date_to))

    if not all_filings:
        return 0

    db = SessionLocal()
    synced = 0
    try:
        for values in all_filings:
            if not values.get("accession_no") or not values.get("filing_date"):
                continue
            stmt = sqlite_insert(SpinoffFiling).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["accession_no"],
                set_={k: v for k, v in values.items() if k != "accession_no"},
            )
            db.execute(stmt)
            synced += 1
        db.commit()
    finally:
        db.close()

    return synced


def read_filings_from_db(
    date_from: str | None,
    date_to: str | None,
    limit: int,
    offset: int,
) -> tuple[list[SpinoffFilingItem], int]:
    """Read paginated filings from DB with optional date filters."""
    db = SessionLocal()
    try:
        query = db.query(SpinoffFiling)
        if date_from:
            query = query.filter(SpinoffFiling.filing_date >= date_from)
        if date_to:
            query = query.filter(SpinoffFiling.filing_date <= date_to)
        total = query.count()
        rows = (
            query.order_by(SpinoffFiling.filing_date.desc(), SpinoffFiling.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        items = [
            SpinoffFilingItem(
                accession_no=r.accession_no,
                cik=r.cik,
                company=r.company,
                form=r.form,
                filing_date=r.filing_date,
                primary_doc_url=r.primary_doc_url,
                primary_doc_description=r.primary_doc_description,
            )
            for r in rows
        ]
        return items, total
    finally:
        db.close()
