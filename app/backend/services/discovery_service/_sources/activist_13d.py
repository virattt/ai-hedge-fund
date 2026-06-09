"""Discovery source: fresh activist 13D / 13G filings.

When an investor crosses 5% ownership of a public company they file Schedule
13D (active intent to influence) or 13G (passive). Filed within 10 days of
crossing the threshold — much fresher than 13F (quarterly, 45-day lag).

Pulls recent Schedule 13D / 13G filings via edgartools, extracts the target
company's ticker, emits a signal per (subject_ticker, filer) pair in the
lookback window.

Score:
  - +20 base for a passive 13G
  - +30 base for an active 13D
  - +10 bump if the filer is in the tracked whale_funds table

Cached 6h since 13D/G filings come in spurts.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol, cast

from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)

_LOOKBACK_DAYS = 30
_CACHE_TTL_SECONDS = 6 * 3600.0
_MAX_FILINGS_PER_FORM = 200

_SCORE_13G_BASE = 20.0
_SCORE_13D_BASE = 30.0
_SCORE_WHALE_BUMP = 10.0


class _FilingProto(Protocol):
    """Stable subset of the edgartools Filing surface we rely on."""
    filing_date: object
    cik: object
    company: object
    accession_no: object


class _EntitySurface(Protocol):
    """Loose union of attributes seen across edgartools entity versions.

    Not all attributes are guaranteed present on every instance — runtime
    AttributeError is expected and caught. The Protocol just narrows static
    types so we can drop type-ignore noise.
    """
    ticker: object
    tickers: object
    name: object
    company: object


@dataclass
class _SubjectInfo:
    ticker: str | None
    company: str | None


@dataclass
class _ActivistFiling:
    subject_ticker: str
    subject_company: str | None
    filer_name: str
    filer_cik: int | None
    form_type: str
    filing_date: str
    accession_no: str | None


def _is_active_filing(form_type: str) -> bool:
    return "13D" in form_type.upper()


def _coerce_subject(candidate: object) -> _SubjectInfo:
    """Extract ticker + name from an edgartools entity candidate.

    edgartools entity attribute surface drifts across versions, so each
    attribute access is wrapped in try/except AttributeError. The Protocol
    cast satisfies the static checker.
    """
    if candidate is None:
        return _SubjectInfo(None, None)

    entity = cast(_EntitySurface, candidate)

    ticker_val: object | None = None
    try:
        ticker_val = entity.ticker
    except AttributeError:
        try:
            tickers = entity.tickers
            if isinstance(tickers, list) and tickers:
                ticker_val = tickers[0]
        except AttributeError:
            pass

    name_val: object | None = None
    try:
        name_val = entity.name
    except AttributeError:
        try:
            name_val = entity.company
        except AttributeError:
            pass

    ticker_str = str(ticker_val).upper().strip() if ticker_val else None
    if ticker_str in (None, "", "NONE"):
        ticker_str = None
    name_str = str(name_val) if name_val else None
    return _SubjectInfo(ticker_str, name_str)


class _SubjectAttrSurface(Protocol):
    """Subject-of-filing attribute names that vary across edgartools versions."""
    subject_company: object
    related_companies: object
    entities: object


def _probe_subject_attr(filing: object, attr_name: str) -> object | None:
    """Read one polymorphic subject-of-filing attribute via __getattribute__."""
    surface = cast(_SubjectAttrSurface, filing)
    try:
        raw: object = surface.__getattribute__(attr_name)
    except AttributeError:
        return None
    if callable(raw):
        try:
            return raw()
        except Exception:
            return None
    return raw


def _extract_subject(filing: object) -> _SubjectInfo:
    """Return the subject (target) company of a 13D/13G filing if exposed."""
    for attr in ("subject_company", "related_companies", "entities"):
        value = _probe_subject_attr(filing, attr)
        if value is None:
            continue
        candidates = value if isinstance(value, list) else [value]
        for c in candidates:
            info = _coerce_subject(c)
            if info.ticker:
                return info
    return _SubjectInfo(None, None)


def _stringy(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _intish(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _fetch_form_sync(form: str, since: date) -> list[_ActivistFiling]:
    from edgar import get_filings
    from app.backend.services.insider_service._helpers import _ensure_identity

    _ensure_identity()
    out: list[_ActivistFiling] = []
    try:
        filings = get_filings(form=form)
    except ValueError as exc:
        # EDGAR sometimes returns an empty body when throttled; edgartools
        # raises ValueError ("Expecting value: line 1 column 1") trying to
        # JSON-decode it. Transient, expected — log at INFO so it stays out
        # of the WARNING channel.
        logger.info("activist_13d: get_filings(form=%s) returned empty body (likely EDGAR throttle): %s", form, exc)
        return out
    except Exception as exc:
        logger.warning("activist_13d: get_filings(form=%s) failed: %s", form, exc)
        return out

    count = 0
    for filing in filings:
        if count >= _MAX_FILINGS_PER_FORM:
            break
        count += 1
        try:
            f = cast(_FilingProto, filing)
            fd_str = _stringy(f.filing_date)[:10]
            if not fd_str:
                continue
            try:
                fd = date.fromisoformat(fd_str)
            except ValueError:
                continue
            if fd < since:
                # Filings iterate newest-first; once below the cutoff we're done
                break

            subject = _extract_subject(filing)
            if not subject.ticker:
                continue

            accession = _stringy(f.accession_no) or None
            out.append(_ActivistFiling(
                subject_ticker=subject.ticker,
                subject_company=subject.company,
                filer_name=_stringy(f.company),
                filer_cik=_intish(f.cik),
                form_type=form,
                filing_date=fd_str,
                accession_no=accession,
            ))
        except Exception as exc:
            logger.debug("activist_13d: skipping malformed filing: %s", exc)
            continue
    return out


def _whale_ciks() -> set[int]:
    from app.backend.database import SessionLocal
    from app.backend.database.models import WhaleFund

    db = SessionLocal()
    try:
        return {row[0] for row in db.query(WhaleFund.cik).all()}
    finally:
        db.close()


_cache: list[_ActivistFiling] | None = None
_cache_ts: float = 0.0


async def fetch() -> list[tuple[str, IdeaSignal]]:
    global _cache, _cache_ts

    now = time.monotonic()
    if _cache is not None and (now - _cache_ts) <= _CACHE_TTL_SECONDS:
        cached_filings = _cache
    else:
        since = date.today() - timedelta(days=_LOOKBACK_DAYS)
        forms = ("SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A")
        # Serialize the EDGAR fetches with a small inter-call delay — firing
        # 4 parallel get_filings() requests reliably triggers EDGAR's
        # throttle, which returns empty bodies and surfaces as JSON-decode
        # errors. Sequential with 1.5s gap is well under EDGAR's 10 req/sec
        # limit and reuses the same hourly cache.
        collected: list[_ActivistFiling] = []
        for idx, f in enumerate(forms):
            if idx > 0:
                await asyncio.sleep(1.5)
            try:
                rows = await asyncio.to_thread(_fetch_form_sync, f, since)
            except Exception as exc:
                logger.warning("activist_13d: form fetch failed for %s: %s", f, exc)
                continue
            collected.extend(rows)
        _cache = collected
        _cache_ts = now
        cached_filings = collected

    if not cached_filings:
        return []

    whales = _whale_ciks()

    out: list[tuple[str, IdeaSignal]] = []
    for af in cached_filings:
        base = _SCORE_13D_BASE if _is_active_filing(af.form_type) else _SCORE_13G_BASE
        is_whale = af.filer_cik is not None and af.filer_cik in whales
        score = base + (_SCORE_WHALE_BUMP if is_whale else 0.0)

        label_filer = af.filer_name[:40] if af.filer_name else f"CIK {af.filer_cik}"
        whale_tag = " (whale)" if is_whale else ""
        label = f"{label_filer}{whale_tag} filed {af.form_type}"

        out.append((af.subject_ticker, IdeaSignal(
            source="activist_13d",
            score=score,
            label=label,
            detail={
                "ticker": af.subject_ticker,
                "company": af.subject_company,
                "filer_name": af.filer_name,
                "filer_cik": af.filer_cik,
                "filer_is_whale": is_whale,
                "form_type": af.form_type,
                "filing_date": af.filing_date,
                "accession_no": af.accession_no,
            },
        )))
    return out
