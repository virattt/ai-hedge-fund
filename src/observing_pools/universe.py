"""Candidate universe ingestion (PRD v4 §9.4).

Loads a seed CSV, validates + de-duplicates tickers, rejects malformed rows
(loudly, recording the reason), and upserts ``CandidateSecurity`` rows. The CSV
carries an optional ``platforms`` column (``;``-separated curated labels) consumed
by the classifier.
"""

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from src.storage.models import CandidateSecurity

# Conservative ticker whitelist: leading letter, then letters/digits/.-, up to 10 chars.
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")

_EXPECTED_COLUMNS = {"ticker", "name", "exchange", "sector", "industry", "platforms"}


@dataclass(frozen=True)
class SeedRow:
    ticker: str
    name: str | None
    exchange: str | None
    sector: str | None
    industry: str | None
    platforms: list[str] = field(default_factory=list)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip()
    return v or None


def load_seed_csv(path: str | Path) -> tuple[list[SeedRow], dict[str, str]]:
    """Parse + validate a seed CSV. Returns (valid rows, {raw_ticker: reject_reason}).

    De-duplicates by ticker (first occurrence wins; later ones rejected).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"seed universe not found: {path}")

    valid: list[SeedRow] = []
    rejected: dict[str, str] = {}
    seen: set[str] = set()

    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = _EXPECTED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"seed CSV {path} missing columns: {sorted(missing)}")

        for lineno, raw in enumerate(reader, start=2):
            ticker = (raw.get("ticker") or "").strip().upper()
            if not ticker:
                rejected[f"<line {lineno}>"] = "empty ticker"
                continue
            if not _TICKER_RE.match(ticker):
                rejected[ticker] = f"invalid ticker format (line {lineno})"
                continue
            if ticker in seen:
                rejected[ticker] = f"duplicate ticker (line {lineno})"
                continue
            seen.add(ticker)

            platforms_raw = _clean(raw.get("platforms")) or ""
            platforms = [p.strip() for p in platforms_raw.split(";") if p.strip()]

            valid.append(
                SeedRow(
                    ticker=ticker,
                    name=_clean(raw.get("name")),
                    exchange=_clean(raw.get("exchange")),
                    sector=_clean(raw.get("sector")),
                    industry=_clean(raw.get("industry")),
                    platforms=platforms,
                )
            )

    return valid, rejected


def upsert_candidates(session: Session, rows: list[SeedRow], *, source: str = "seed") -> dict[str, CandidateSecurity]:
    """Idempotently upsert candidate securities. Returns {ticker: CandidateSecurity}."""
    out: dict[str, CandidateSecurity] = {}
    for row in rows:
        existing = session.query(CandidateSecurity).filter_by(ticker=row.ticker).one_or_none()
        if existing is None:
            existing = CandidateSecurity(ticker=row.ticker, source=source)
            session.add(existing)
        existing.name = row.name
        existing.exchange = row.exchange
        existing.sector = row.sector
        existing.industry = row.industry
        out[row.ticker] = existing
    session.flush()
    return out
