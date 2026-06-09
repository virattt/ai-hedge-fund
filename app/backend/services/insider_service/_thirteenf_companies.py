"""13F-HR company list worker functions (DB-cached).

Provides functions for managing the cached list of 13F-HR company names + CIKs:

- _fetch_thirteenf_companies: slow path — iterates all filings from edgartools
- _read_companies_from_db: fast path — reads cached data from SQLite
- _sync_companies_to_db: fetches from edgartools and upserts into SQLite
"""
import logging

from app.backend.models.insider_schemas import (
    ThirteenFCompaniesResponse,
    ThirteenFCompanyItem,
)
from app.backend.services.insider_service._helpers import _ensure_identity
from app.backend.services.insider_service._thirteenf import _get_filings

logger = logging.getLogger(__name__)


def _fetch_thirteenf_companies() -> ThirteenFCompaniesResponse:
    """Return deduplicated company names + CIKs from all 13F-HR filings (slow — hits edgartools)."""
    _ensure_identity()
    filings = _get_filings(form="13F-HR")
    seen: dict[int, str] = {}  # CIK → company name (deduplicate by CIK)
    for filing in filings:
        cik = int(filing.cik)
        if cik not in seen:
            seen[cik] = str(filing.company)
    items = sorted(
        [ThirteenFCompanyItem(company=name, cik=cik) for cik, name in seen.items()],
        key=lambda x: x.company,
    )
    return ThirteenFCompaniesResponse(companies=items, total=len(items))


def _read_companies_from_db() -> ThirteenFCompaniesResponse:
    """Read cached company list from SQLite. Returns empty response if table is empty."""
    from app.backend.database.connection import SessionLocal
    from app.backend.database.models import ThirteenFCompany

    db = SessionLocal()
    try:
        rows = db.query(ThirteenFCompany).order_by(ThirteenFCompany.company).all()
        items = [ThirteenFCompanyItem(company=r.company, cik=r.cik) for r in rows]
        return ThirteenFCompaniesResponse(companies=items, total=len(items))
    finally:
        db.close()


def _sync_companies_to_db() -> int:
    """Fetch companies from edgartools and upsert into SQLite. Returns count synced."""
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    from app.backend.database.connection import SessionLocal
    from app.backend.database.models import ThirteenFCompany

    logger.info("Starting 13F company sync from edgartools...")
    result = _fetch_thirteenf_companies()
    db = SessionLocal()
    try:
        for item in result.companies:
            stmt = sqlite_insert(ThirteenFCompany).values(company=item.company, cik=item.cik)
            stmt = stmt.on_conflict_do_update(index_elements=["cik"], set_={"company": item.company})
            db.execute(stmt)
        db.commit()
        logger.info("13F company sync complete: %d companies", result.total)
        return result.total
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
