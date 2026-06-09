"""Watchlist service: CRUD + scheduled batch sentiment analysis.

Each WatchlistItem stores the latest snapshot of its earnings sentiment
analysis. The batch job re-runs analysis (cached 6h via earnings_service)
and persists the latest delta_direction so the earnings_sentiment_shift
alert rule can detect direction flips.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.backend.database import SessionLocal
from app.backend.database.models import AppSetting, WatchlistItem
from app.backend.models.watchlist_schemas import (
    BatchRunResponse,
    WatchlistItemResponse,
    WatchlistListResponse,
)
from app.backend.services.api_key_service import ApiKeyService

logger = logging.getLogger(__name__)


_DEFAULT_LLM_NAME = "qwen3:latest"
_DEFAULT_LLM_PROVIDER = "Ollama"


def _get_setting(db: Session, key: str) -> str | None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else None


def _to_response(item: WatchlistItem) -> WatchlistItemResponse:
    return WatchlistItemResponse(
        id=item.id,
        ticker=item.ticker,
        notes=item.notes,
        added_at=item.added_at.isoformat() if isinstance(item.added_at, datetime) else str(item.added_at or ""),
        last_analyzed_at=item.last_analyzed_at.isoformat() if isinstance(item.last_analyzed_at, datetime) else None,
        last_overall_sentiment=item.last_overall_sentiment,
        last_delta_direction=item.last_delta_direction,
        last_management_tone=item.last_management_tone,
        last_payload=item.last_payload,
        last_error=item.last_error,
    )


def add_ticker(db: Session, ticker: str, notes: str | None = None) -> WatchlistItemResponse:
    sym = ticker.strip().upper()
    if not sym:
        raise ValueError("Ticker cannot be empty")

    existing = db.query(WatchlistItem).filter(WatchlistItem.ticker == sym).first()
    if existing:
        if notes is not None:
            existing.notes = notes
            db.commit()
            db.refresh(existing)
        return _to_response(existing)

    item = WatchlistItem(ticker=sym, notes=notes)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_response(item)


def remove_ticker(db: Session, ticker: str) -> bool:
    sym = ticker.strip().upper()
    deleted = db.query(WatchlistItem).filter(WatchlistItem.ticker == sym).delete()
    db.commit()
    return deleted > 0


def update_notes(db: Session, ticker: str, notes: str | None) -> WatchlistItemResponse | None:
    sym = ticker.strip().upper()
    item = db.query(WatchlistItem).filter(WatchlistItem.ticker == sym).first()
    if not item:
        return None
    item.notes = notes
    db.commit()
    db.refresh(item)
    return _to_response(item)


def is_watched(db: Session, ticker: str) -> bool:
    sym = ticker.strip().upper()
    return db.query(WatchlistItem).filter(WatchlistItem.ticker == sym).first() is not None


def list_tickers(db: Session) -> WatchlistListResponse:
    rows = db.query(WatchlistItem).order_by(WatchlistItem.ticker.asc()).all()
    return WatchlistListResponse(
        items=[_to_response(r) for r in rows],
        total=len(rows),
    )


async def list_tickers_with_returns(db: Session) -> WatchlistListResponse:
    """Return watchlist items enriched with period return + SPY alpha.

    Issued as a separate function so the synchronous `list_tickers` remains
    available for callers (scheduler, batch job) that don't need the slow
    yfinance roundtrip. Routes that serve the UI should use this variant.
    """
    from app.backend.services.pricing_service import compute_alpha_batch
    from app.backend.services.whale_entry_service import get_distance_batch

    rows = db.query(WatchlistItem).order_by(WatchlistItem.ticker.asc()).all()
    items = [_to_response(r) for r in rows]

    pairs: list[tuple[str, datetime]] = []
    for r in rows:
        if r.added_at and isinstance(r.added_at, datetime):
            pairs.append((r.ticker, r.added_at))

    if not pairs:
        return WatchlistListResponse(items=items, total=len(items))

    metrics_by_ticker, whale_dist_by_ticker = await asyncio.gather(
        compute_alpha_batch(pairs),
        get_distance_batch([t for t, _ in pairs]),
    )
    by_ticker = {item.ticker.upper(): item for item in items}
    for ticker_upper, metrics in metrics_by_ticker.items():
        target = by_ticker.get(ticker_upper)
        if target is None or metrics is None:
            continue
        target.return_pct_since_added = metrics.period_return_pct
        target.alpha_pct_vs_spy = metrics.alpha_pct

    for ticker_upper, distance in whale_dist_by_ticker.items():
        target = by_ticker.get(ticker_upper)
        if target is None:
            continue
        target.distance_from_whale_entry_pct = distance

    return WatchlistListResponse(items=items, total=len(items))


async def _analyze_one(ticker: str, model_name: str, model_provider: str, api_keys: dict) -> tuple[bool, dict[str, Any]]:
    """Run earnings analysis for a single ticker. Returns (success, snapshot_or_error)."""
    from app.backend.services.earnings_service import get_earnings_analysis

    try:
        result = await get_earnings_analysis(ticker, model_name, model_provider, api_keys)
    except Exception as exc:
        return False, {"error": str(exc)}

    delta = result.delta
    current = delta.current if delta else (result.transcripts[0] if result.transcripts else None)

    snapshot: dict[str, Any] = {
        "overall_sentiment": current.analysis.overall_sentiment if current else None,
        "delta_direction": delta.delta_direction if delta else None,
        "delta_magnitude": delta.delta_magnitude if delta else None,
        "management_tone": current.analysis.management_tone if current else None,
        "key_themes": current.analysis.key_themes if current else [],
        "forward_guidance": current.analysis.forward_guidance if current else None,
        "quarter": current.quarter if current else None,
        "year": current.year if current else None,
    }
    return True, snapshot


async def run_batch_analysis() -> BatchRunResponse:
    """Re-run earnings sentiment for every watched ticker; persist latest snapshot."""
    db = SessionLocal()
    try:
        items = db.query(WatchlistItem).all()
        tickers = [item.ticker for item in items]
        model_name = _get_setting(db, "llm_model_name") or _DEFAULT_LLM_NAME
        model_provider = _get_setting(db, "llm_model_provider") or _DEFAULT_LLM_PROVIDER
        api_keys = ApiKeyService(db).get_api_keys_dict()
    finally:
        db.close()

    if not tickers:
        return BatchRunResponse(analyzed=0, succeeded=0, failed=0, skipped_no_earnings=0)

    # Smart-skip: if the earnings calendar is available (FINNHUB_API_KEY),
    # only re-analyze tickers with earnings in the next 7 days. Saves LLM
    # calls dramatically since transcripts don't change between earnings.
    skip_set: set[str] = set()
    skipped_no_earnings = 0
    try:
        from app.backend.services.earnings_calendar_service import (
            get_tickers_reporting_soon,
            is_calendar_available,
        )
        if is_calendar_available():
            reporting = await get_tickers_reporting_soon(tickers, days=7)
            if reporting:  # non-empty result means calendar is working
                skip_set = {t.upper() for t in tickers} - reporting
                if skip_set:
                    logger.info(
                        "Smart-batch: skipping %d tickers without earnings in next 7d: %s",
                        len(skip_set), sorted(skip_set),
                    )
    except Exception as exc:
        logger.warning("Smart-batch calendar check failed; analyzing all tickers: %s", exc)

    succeeded = 0
    failed = 0

    for ticker in tickers:
        if ticker.upper() in skip_set:
            # Touch last_analyzed_at without re-running LLM
            db = SessionLocal()
            try:
                item = db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker).first()
                if item is not None:
                    item.last_analyzed_at = datetime.now(timezone.utc)
                    db.commit()
            finally:
                db.close()
            skipped_no_earnings += 1
            continue

        success, snapshot = await _analyze_one(ticker, model_name, model_provider, api_keys)

        # Persist snapshot back to DB (open fresh session per item to avoid long-held tx)
        db = SessionLocal()
        try:
            item = db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker).first()
            if item is None:
                continue  # got removed mid-batch
            item.last_analyzed_at = datetime.now(timezone.utc)
            if success:
                item.last_overall_sentiment = snapshot.get("overall_sentiment")
                item.last_delta_direction = snapshot.get("delta_direction")
                item.last_management_tone = snapshot.get("management_tone")
                item.last_payload = snapshot
                item.last_error = None
                succeeded += 1
            else:
                item.last_error = snapshot.get("error", "Unknown error")
                failed += 1
            db.commit()
        finally:
            db.close()

    return BatchRunResponse(
        analyzed=len(tickers),
        succeeded=succeeded,
        failed=failed,
        skipped_no_earnings=skipped_no_earnings,
    )


async def refresh_one(ticker: str) -> WatchlistItemResponse:
    """Manually re-run analysis for one ticker, persist, return updated snapshot."""
    sym = ticker.strip().upper()
    db = SessionLocal()
    try:
        item = db.query(WatchlistItem).filter(WatchlistItem.ticker == sym).first()
        if item is None:
            raise ValueError(f"{sym} is not in the watchlist")
        model_name = _get_setting(db, "llm_model_name") or _DEFAULT_LLM_NAME
        model_provider = _get_setting(db, "llm_model_provider") or _DEFAULT_LLM_PROVIDER
        api_keys = ApiKeyService(db).get_api_keys_dict()
    finally:
        db.close()

    success, snapshot = await _analyze_one(sym, model_name, model_provider, api_keys)

    db = SessionLocal()
    try:
        item = db.query(WatchlistItem).filter(WatchlistItem.ticker == sym).first()
        if item is None:
            raise ValueError(f"{sym} disappeared during refresh")
        item.last_analyzed_at = datetime.now(timezone.utc)
        if success:
            item.last_overall_sentiment = snapshot.get("overall_sentiment")
            item.last_delta_direction = snapshot.get("delta_direction")
            item.last_management_tone = snapshot.get("management_tone")
            item.last_payload = snapshot
            item.last_error = None
        else:
            item.last_error = snapshot.get("error", "Unknown error")
        db.commit()
        db.refresh(item)
        return _to_response(item)
    finally:
        db.close()


__all__ = [
    "add_ticker",
    "remove_ticker",
    "update_notes",
    "is_watched",
    "list_tickers",
    "run_batch_analysis",
    "refresh_one",
]
