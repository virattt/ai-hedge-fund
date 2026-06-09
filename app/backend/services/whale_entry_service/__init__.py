"""Whale entry computation — walks 13F history to find the quarter each whale
opened each position, then approximates entry price via yfinance VWAP over
that quarter.

Cache strategy: persist to whale_entry_cache table; rows older than 7 days
are stale (13F filings only update quarterly anyway). Lookups are pure DB
reads. Refresh is explicit via refresh_whale(whale_cik) or refresh_all().
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import yfinance as yf
from sqlalchemy.orm import Session

from app.backend.database import SessionLocal
from app.backend.database.models import WhaleEntryCache, WhaleFund

logger = logging.getLogger(__name__)

_LOOKBACK_QUARTERS = 12
_CACHE_TTL_DAYS = 7


@dataclass
class _QuarterBounds:
    start: date
    end: date
    label: str


@dataclass
class WhaleEntrySummary:
    """One whale's entry for one ticker — flat DTO for API + UI consumption."""
    whale_cik: int
    whale_name: str
    ticker: str
    entry_quarter_label: str | None
    entry_period_start: str | None
    entry_period_end: str | None
    entry_vwap: float | None
    entry_low: float | None
    entry_high: float | None
    share_count_at_entry: float | None
    is_pre_lookback: bool
    computed_at: str | None


@dataclass
class TickerWhaleSummary:
    """Aggregate summary of all whales' entries for one ticker."""
    ticker: str
    current_price: float | None
    best_entry_vwap: float | None
    best_entry_whale_cik: int | None
    best_entry_whale_name: str | None
    distance_from_best_entry_pct: float | None
    whale_count: int
    entries: list[WhaleEntrySummary]


def _quarter_bounds(period_end_iso: str) -> _QuarterBounds:
    """From a 13F period_end (YYYY-MM-DD), return calendar-quarter span + label."""
    end_d = date.fromisoformat(period_end_iso)
    month = end_d.month
    if month <= 3:
        return _QuarterBounds(date(end_d.year, 1, 1), date(end_d.year, 3, 31), f"Q1 {end_d.year}")
    if month <= 6:
        return _QuarterBounds(date(end_d.year, 4, 1), date(end_d.year, 6, 30), f"Q2 {end_d.year}")
    if month <= 9:
        return _QuarterBounds(date(end_d.year, 7, 1), date(end_d.year, 9, 30), f"Q3 {end_d.year}")
    return _QuarterBounds(date(end_d.year, 10, 1), date(end_d.year, 12, 31), f"Q4 {end_d.year}")


def _compute_quarter_vwap_sync(ticker: str, start_d: date, end_d: date) -> dict[str, float] | None:
    """Synchronous yfinance fetch + volume-weighted typical-price computation."""
    try:
        history = yf.Ticker(ticker.upper()).history(
            start=start_d.isoformat(),
            end=(end_d + timedelta(days=1)).isoformat(),
            auto_adjust=True,
        )
    except Exception as exc:
        logger.debug("whale_entry yfinance failed for %s in %s..%s: %s", ticker, start_d, end_d, exc)
        return None
    if history is None or history.empty:
        return None

    try:
        typical = (history["High"] + history["Low"] + history["Close"]) / 3
        volume = history["Volume"]
        vol_sum = float(volume.sum())
        if vol_sum > 0:
            vwap = float((typical * volume).sum() / vol_sum)
        else:
            vwap = float(typical.mean())
        return {
            "vwap": vwap,
            "low": float(history["Low"].min()),
            "high": float(history["High"].max()),
        }
    except (KeyError, ValueError, TypeError):
        return None


async def _compute_quarter_vwap(ticker: str, start_d: date, end_d: date) -> dict[str, float] | None:
    return await asyncio.to_thread(_compute_quarter_vwap_sync, ticker, start_d, end_d)


def _get_whale_latest_filing_sync(whale_cik: int) -> str | None:
    from app.backend.services.insider_service._thirteenf import _fetch_thirteenf_filings

    try:
        resp = _fetch_thirteenf_filings(
            limit=1, offset=0, year=None, quarter=None, cik_list=[whale_cik],
        )
    except Exception as exc:
        logger.warning("whale_entry: failed to fetch latest 13F for CIK %d: %s", whale_cik, exc)
        return None
    if not resp.filings:
        return None
    return resp.filings[0].accession_no


def _get_holding_history_sync(accession_no: str, periods: int):
    from app.backend.services.insider_service._thirteenf_detail import _fetch_holding_history

    try:
        return _fetch_holding_history(accession_no, periods)
    except Exception as exc:
        logger.warning("whale_entry: failed to fetch holding history for %s: %s", accession_no, exc)
        return None


def _coerce_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


async def refresh_whale(whale_cik: int, force: bool = False) -> int:
    """Recompute and persist entries for all positions held by one whale.

    Skips work if cached rows are <7 days old unless force=True. Returns
    number of (ticker → entry) rows written.
    """
    db = SessionLocal()
    try:
        if not force:
            recent = (
                db.query(WhaleEntryCache)
                .filter(WhaleEntryCache.whale_cik == whale_cik)
                .order_by(WhaleEntryCache.computed_at.desc())
                .first()
            )
            if recent is not None and recent.computed_at:
                age = datetime.now(timezone.utc) - _coerce_aware(recent.computed_at)
                if age < timedelta(days=_CACHE_TTL_DAYS):
                    return 0
    finally:
        db.close()

    latest_accession = await asyncio.to_thread(_get_whale_latest_filing_sync, whale_cik)
    if latest_accession is None:
        logger.info("whale_entry: no 13F filings found for CIK %d", whale_cik)
        return 0

    history = await asyncio.to_thread(_get_holding_history_sync, latest_accession, _LOOKBACK_QUARTERS)
    if history is None:
        return 0

    periods_sorted = sorted(history.periods)
    if not periods_sorted:
        return 0

    @dataclass
    class _Pending:
        ticker: str
        period_end: str
        share_count: float
        is_pre_lookback: bool
        bounds: _QuarterBounds

    pending: list[_Pending] = []
    for record in history.records:
        if not record.ticker:
            continue
        entry_period = None
        share_count = None
        for p in periods_sorted:
            shares = record.periods_data.get(p)
            if shares is not None and shares > 0:
                entry_period = p
                share_count = float(shares)
                break
        if entry_period is None:
            continue
        pending.append(_Pending(
            ticker=record.ticker.upper(),
            period_end=entry_period,
            share_count=share_count,
            is_pre_lookback=(entry_period == periods_sorted[0]),
            bounds=_quarter_bounds(entry_period),
        ))

    # Dedupe by ticker — 13F holdings can list the same ticker under multiple
    # CUSIPs (different share classes, post-split rows). Keep the earliest
    # entry_period since that's the true first-seen quarter.
    by_ticker: dict[str, _Pending] = {}
    for p in pending:
        existing = by_ticker.get(p.ticker)
        if existing is None or p.period_end < existing.period_end:
            by_ticker[p.ticker] = p
    pending = list(by_ticker.values())

    if not pending:
        return 0

    vwap_results = await asyncio.gather(
        *[_compute_quarter_vwap(p.ticker, p.bounds.start, p.bounds.end) for p in pending],
        return_exceptions=True,
    )

    written = 0
    db = SessionLocal()
    try:
        for entry, vwap_data in zip(pending, vwap_results, strict=True):
            if isinstance(vwap_data, BaseException):
                vwap_data = None
            existing = (
                db.query(WhaleEntryCache)
                .filter(WhaleEntryCache.whale_cik == whale_cik, WhaleEntryCache.ticker == entry.ticker)
                .first()
            )
            now = datetime.now(timezone.utc)
            if existing is None:
                existing = WhaleEntryCache(whale_cik=whale_cik, ticker=entry.ticker)
                db.add(existing)
            existing.entry_quarter_label = entry.bounds.label
            existing.entry_period_start = entry.bounds.start.isoformat()
            existing.entry_period_end = entry.period_end
            existing.entry_vwap = vwap_data.get("vwap") if vwap_data else None
            existing.entry_low = vwap_data.get("low") if vwap_data else None
            existing.entry_high = vwap_data.get("high") if vwap_data else None
            existing.share_count_at_entry = entry.share_count
            existing.is_pre_lookback = entry.is_pre_lookback
            existing.computed_at = now
            written += 1
        db.commit()
    except Exception as exc:
        logger.warning("whale_entry: DB write failed for CIK %d: %s", whale_cik, exc)
        db.rollback()
    finally:
        db.close()

    return written


async def refresh_all(force: bool = False) -> dict[int, int]:
    """Refresh entries for every whale in whale_funds. Returns {cik → rows_written}."""
    db = SessionLocal()
    try:
        ciks = [row[0] for row in db.query(WhaleFund.cik).all()]
    finally:
        db.close()
    if not ciks:
        return {}
    results = await asyncio.gather(*(refresh_whale(c, force=force) for c in ciks), return_exceptions=True)
    out: dict[int, int] = {}
    for cik, res in zip(ciks, results, strict=True):
        out[cik] = res if isinstance(res, int) else 0
    return out


def _row_to_summary(row: WhaleEntryCache, whale_name: str) -> WhaleEntrySummary:
    return WhaleEntrySummary(
        whale_cik=row.whale_cik,
        whale_name=whale_name,
        ticker=row.ticker,
        entry_quarter_label=row.entry_quarter_label,
        entry_period_start=row.entry_period_start,
        entry_period_end=row.entry_period_end,
        entry_vwap=row.entry_vwap,
        entry_low=row.entry_low,
        entry_high=row.entry_high,
        share_count_at_entry=row.share_count_at_entry,
        is_pre_lookback=row.is_pre_lookback,
        computed_at=row.computed_at.isoformat() if row.computed_at else None,
    )


def get_entries_for_ticker(db: Session, ticker: str) -> list[WhaleEntrySummary]:
    """Return all whale entries for one ticker, sorted by VWAP ascending."""
    sym = ticker.upper().strip()
    if not sym:
        return []
    rows = (
        db.query(WhaleEntryCache, WhaleFund)
        .join(WhaleFund, WhaleFund.cik == WhaleEntryCache.whale_cik)
        .filter(WhaleEntryCache.ticker == sym)
        .all()
    )
    summaries = [_row_to_summary(row, fund.name) for row, fund in rows]
    summaries.sort(key=lambda s: (s.entry_vwap if s.entry_vwap is not None else float("inf")))
    return summaries


async def _get_current_price(ticker: str) -> float | None:
    from app.backend.services.pricing_service import get_period_return

    end_d = date.today()
    start_d = end_d - timedelta(days=7)
    result = await get_period_return(ticker, start_d)
    if result is None:
        return None
    return result.end_price


async def get_ticker_summary(ticker: str) -> TickerWhaleSummary:
    """Aggregate summary for one ticker: best whale entry, distance from current."""
    db = SessionLocal()
    try:
        entries = get_entries_for_ticker(db, ticker)
    finally:
        db.close()

    summary = TickerWhaleSummary(
        ticker=ticker.upper(),
        current_price=None,
        best_entry_vwap=None,
        best_entry_whale_cik=None,
        best_entry_whale_name=None,
        distance_from_best_entry_pct=None,
        whale_count=len(entries),
        entries=entries,
    )

    if not entries:
        return summary

    best = next((e for e in entries if e.entry_vwap is not None), None)
    if best is not None:
        summary.best_entry_vwap = best.entry_vwap
        summary.best_entry_whale_cik = best.whale_cik
        summary.best_entry_whale_name = best.whale_name

    current_price = await _get_current_price(ticker)
    summary.current_price = current_price
    if current_price is not None and summary.best_entry_vwap and summary.best_entry_vwap > 0:
        summary.distance_from_best_entry_pct = (current_price / summary.best_entry_vwap - 1.0) * 100.0

    return summary


async def get_distance_batch(tickers: list[str]) -> dict[str, float | None]:
    """For each ticker, return distance % from its best whale entry.

    Pure DB lookup + one pricing_service call per ticker (parallel). Returns
    None for tickers with no whale entries OR no current price.
    """
    if not tickers:
        return {}
    upper = [t.upper() for t in tickers]

    db = SessionLocal()
    try:
        rows = (
            db.query(WhaleEntryCache)
            .filter(WhaleEntryCache.ticker.in_(upper), WhaleEntryCache.entry_vwap.isnot(None))
            .all()
        )
    finally:
        db.close()

    best_entry_by_ticker: dict[str, float] = {}
    for r in rows:
        if r.entry_vwap is None:
            continue
        cur = best_entry_by_ticker.get(r.ticker)
        if cur is None or r.entry_vwap < cur:
            best_entry_by_ticker[r.ticker] = r.entry_vwap

    if not best_entry_by_ticker:
        return {t: None for t in upper}

    price_tasks = [_get_current_price(t) for t in best_entry_by_ticker.keys()]
    price_results = await asyncio.gather(*price_tasks, return_exceptions=True)

    out: dict[str, float | None] = {t: None for t in upper}
    for ticker, price in zip(best_entry_by_ticker.keys(), price_results, strict=True):
        if isinstance(price, BaseException) or price is None:
            continue
        entry = best_entry_by_ticker[ticker]
        if entry <= 0:
            continue
        out[ticker] = (price / entry - 1.0) * 100.0
    return out
