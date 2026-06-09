"""Whale funds service — CRUD + seed of well-known investors.

The whale universe is user-curated: the seed list below provides reasonable
defaults at first run, but the settings UI can add/remove entries at any time.
CIKs resolved via fuzzy name match against the cached ThirteenFCompany table
(populated by insider_service._thirteenf_companies).
"""

import logging
from dataclasses import dataclass

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.backend.database import SessionLocal
from app.backend.database.models import ThirteenFCompany, WhaleFund

logger = logging.getLogger(__name__)


# Curated seed list — name keywords used for fuzzy match against 13F company
# table. First match wins. User can edit afterwards.
_SEED_NAME_PATTERNS: list[tuple[str, str]] = [
    ("BERKSHIRE HATHAWAY", "Warren Buffett — Berkshire Hathaway"),
    ("SCION ASSET MANAGEMENT", "Michael Burry — Scion Asset Management"),
    ("APPALOOSA", "David Tepper — Appaloosa Management"),
    ("PERSHING SQUARE", "Bill Ackman — Pershing Square"),
    ("THIRD POINT", "Dan Loeb — Third Point"),
    ("BAUPOST GROUP", "Seth Klarman — Baupost Group"),
    ("PABRAI INVESTMENT", "Mohnish Pabrai — Pabrai Investments"),
    ("GREENLIGHT CAPITAL", "David Einhorn — Greenlight Capital"),
    ("DUQUESNE FAMILY", "Stanley Druckenmiller — Duquesne Family Office"),
    ("GOTHAM ASSET", "Joel Greenblatt — Gotham Asset Management"),
]


@dataclass
class WhaleFundDTO:
    id: int
    cik: int
    name: str
    notes: str | None
    added_at: str | None


def _to_dto(row: WhaleFund) -> WhaleFundDTO:
    return WhaleFundDTO(
        id=row.id,
        cik=row.cik,
        name=row.name,
        notes=row.notes,
        added_at=row.added_at.isoformat() if row.added_at else None,
    )


def _lookup_cik_by_name(db: Session, keyword: str) -> tuple[int, str] | None:
    """Fuzzy match a single keyword against ThirteenFCompany.company. Returns
    (cik, full_company_name) of the first hit, or None if no match exists.
    """
    row = (
        db.query(ThirteenFCompany)
        .filter(ThirteenFCompany.company.ilike(f"%{keyword}%"))
        .order_by(ThirteenFCompany.company.asc())
        .first()
    )
    if row is None:
        return None
    return (row.cik, row.company)


def list_whales(db: Session) -> list[WhaleFundDTO]:
    rows = db.query(WhaleFund).order_by(WhaleFund.name.asc()).all()
    return [_to_dto(r) for r in rows]


def get_whale_ciks(db: Session) -> list[int]:
    rows = db.query(WhaleFund.cik).all()
    return [r[0] for r in rows]


def add_whale(db: Session, cik: int, name: str, notes: str | None = None) -> WhaleFundDTO:
    if cik <= 0:
        raise ValueError("CIK must be positive")
    name_clean = (name or "").strip()
    if not name_clean:
        raise ValueError("Name cannot be empty")

    existing = db.query(WhaleFund).filter(WhaleFund.cik == cik).first()
    if existing is not None:
        if notes is not None:
            existing.notes = notes
            db.commit()
            db.refresh(existing)
        return _to_dto(existing)

    new = WhaleFund(cik=cik, name=name_clean, notes=notes)
    db.add(new)
    db.commit()
    db.refresh(new)
    return _to_dto(new)


def remove_whale(db: Session, cik: int) -> bool:
    row = db.query(WhaleFund).filter(WhaleFund.cik == cik).first()
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def find_candidates_by_name(db: Session, query: str, limit: int = 10) -> list[tuple[int, str]]:
    """Return up to `limit` (cik, company) tuples matching the query."""
    q = (query or "").strip()
    if not q:
        return []
    rows = (
        db.query(ThirteenFCompany)
        .filter(or_(
            ThirteenFCompany.company.ilike(f"%{q}%"),
        ))
        .order_by(ThirteenFCompany.company.asc())
        .limit(limit)
        .all()
    )
    return [(r.cik, r.company) for r in rows]


def seed_default_whales(db: Session | None = None) -> int:
    """Insert any missing seed whales by fuzzy-matching name keywords to
    ThirteenFCompany. Returns the number of seeds inserted (skips entries
    already present in whale_funds and entries with no name match).
    """
    own_session = db is None
    db = db or SessionLocal()
    inserted = 0
    try:
        existing_ciks = {row[0] for row in db.query(WhaleFund.cik).all()}
        for keyword, display_name in _SEED_NAME_PATTERNS:
            match = _lookup_cik_by_name(db, keyword)
            if match is None:
                logger.info("seed_default_whales: no 13F match for '%s'", keyword)
                continue
            cik, full_name = match
            if cik in existing_ciks:
                continue
            db.add(WhaleFund(cik=cik, name=display_name, notes=f"Auto-seeded ({full_name})"))
            existing_ciks.add(cik)
            inserted += 1
        db.commit()
    except Exception as exc:
        logger.warning("seed_default_whales failed: %s", exc)
        db.rollback()
    finally:
        if own_session:
            db.close()
    return inserted
