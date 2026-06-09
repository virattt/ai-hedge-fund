"""Discovery service public API — get_ideas() with 1h cache + snapshot history.

On fresh compute (cache miss):
  1. Persist a DiscoverySnapshot row per idea (enables historical score tracking).
  2. If any ticker has high-confluence (>= 4 distinct signal sources AND score
     >= 80), the high_confluence alert rule is triggered immediately —
     bypassing the 4h AlertScheduler.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.backend.database import SessionLocal
from app.backend.database.models import DiscoverySnapshot
from app.backend.models.discovery_schemas import (
    DiscoveryHistoryResponse,
    DiscoveryMover,
    DiscoveryMoversResponse,
    DiscoveryResponse,
    DiscoverySnapshotItem,
)
from app.backend.services.discovery_service._engine import aggregate_ideas

logger = logging.getLogger(__name__)

_HIGH_CONFLUENCE_MIN_SOURCES: int = 4
_HIGH_CONFLUENCE_MIN_SCORE: float = 80.0

# Single-flight de-dup: when two requests arrive while a compute is in
# progress, the second one awaits the first task instead of starting a
# parallel fanout. The dict key is always "discovery:{limit}".
_inflight_refreshes: dict[str, asyncio.Task] = {}


def _has_high_confluence(response: DiscoveryResponse) -> bool:
    """True if any idea has >= 4 distinct signal sources AND score >= 80."""
    for idea in response.ideas:
        distinct_sources = len({s.source for s in idea.signals})
        if distinct_sources >= _HIGH_CONFLUENCE_MIN_SOURCES and idea.score >= _HIGH_CONFLUENCE_MIN_SCORE:
            return True
    return False


def _trigger_high_confluence_alert_in_background() -> None:
    """Fire-and-forget the immediate high_confluence alert evaluation.

    Wrapped in a background task so a slow Telegram send doesn't block the
    Discovery API response. Errors are logged but never raised.
    """
    async def _runner() -> None:
        try:
            # Deferred import: alert_service imports from discovery_service in
            # the high_confluence rule body, so a top-level import would create
            # a circular dependency at module load time.
            from app.backend.services.alert_service import trigger_rule_immediately
            created = await trigger_rule_immediately("high_confluence")
            if created > 0:
                logger.info("high_confluence: %d immediate alert(s) created", created)
        except Exception as exc:
            logger.warning("high_confluence immediate trigger failed: %s", exc)

    try:
        asyncio.create_task(_runner())
    except RuntimeError:
        logger.debug("No event loop; skipping immediate high_confluence trigger")


def _persist_snapshots(response: DiscoveryResponse) -> None:
    """Persist one DiscoverySnapshot row per idea. Runs synchronously inside
    the get_ideas flow. Best-effort — DB errors are logged, never raised.
    """
    db: Session = SessionLocal()
    try:
        for idea in response.ideas:
            distinct_sources = len({s.source for s in idea.signals})
            signals_json = [
                {"source": s.source, "score": s.score, "label": s.label}
                for s in idea.signals
            ]
            db.add(DiscoverySnapshot(
                ticker=idea.ticker[:20],
                cik=idea.cik,
                is_ticker=idea.is_ticker,
                company=idea.company,
                score=idea.score,
                distinct_sources=distinct_sources,
                signals=signals_json,
            ))
        db.commit()
    except Exception as exc:
        logger.warning("Discovery snapshot persistence failed: %s", exc)
        db.rollback()
    finally:
        db.close()


async def _enrich_top_with_alpha(ideas: list, max_enrich: int, days: int) -> None:
    """Mutate the first `max_enrich` ticker-keyed ideas in place with N-day
    return %, SPY-relative alpha, distance_from_whale_entry_pct, and a
    company-name fallback when no contributing signal supplied one.

    The company-name lookup piggybacks on `get_company_metrics_batch`, which
    most of the quality sources have already populated for these tickers.
    Within the 24h fundamentals cache the call is essentially free.
    """
    from datetime import date, timedelta

    from app.backend.services.fundamentals_service import get_company_metrics_batch
    from app.backend.services.pricing_service import compute_alpha_batch
    from app.backend.services.whale_entry_service import get_distance_batch

    since = date.today() - timedelta(days=days)
    targets = [i for i in ideas[:max_enrich] if i.is_ticker and i.ticker]
    if not targets:
        return

    pairs: list[tuple[str, date]] = [(i.ticker, since) for i in targets]
    ticker_symbols = [i.ticker for i in targets]
    metrics_by_ticker, whale_dist_by_ticker, company_metrics_by_ticker = await asyncio.gather(
        compute_alpha_batch(pairs),
        get_distance_batch(ticker_symbols),
        get_company_metrics_batch(ticker_symbols),
    )
    for idea in targets:
        ticker_upper = idea.ticker.upper()
        m = metrics_by_ticker.get(ticker_upper)
        if m is not None:
            idea.return_30d_pct = m.period_return_pct
            idea.alpha_30d_pct = m.alpha_pct
        idea.distance_from_whale_entry_pct = whale_dist_by_ticker.get(ticker_upper)

        if not idea.company:
            cm = company_metrics_by_ticker.get(ticker_upper)
            if cm is not None and cm.long_name:
                idea.company = cm.long_name


async def _compute_fresh(limit: int) -> DiscoveryResponse:
    all_ideas = await aggregate_ideas()
    capped = all_ideas[:limit]
    await _enrich_top_with_alpha(capped, max_enrich=50, days=30)
    response = DiscoveryResponse(
        ideas=capped,
        total=len(all_ideas),
        cached=False,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    _persist_snapshots(response)
    if _has_high_confluence(response):
        _trigger_high_confluence_alert_in_background()

    return response


def _key(limit: int) -> str:
    return f"discovery:{limit}"


async def get_ideas(limit: int = 50) -> DiscoveryResponse:
    """Compute Discovery ideas fresh on every call.

    No in-memory cache, no DB-snapshot hydration — every request runs the
    full source fanout. Concurrent requests with the same limit share one
    compute via the inflight-task dedup.
    """
    key = _key(limit)

    inflight = _inflight_refreshes.get(key)
    if inflight is not None and not inflight.done():
        return await asyncio.shield(inflight)

    async def _run() -> DiscoveryResponse:
        try:
            return await _compute_fresh(limit)
        finally:
            _inflight_refreshes.pop(key, None)

    task = asyncio.create_task(_run())
    _inflight_refreshes[key] = task
    return await task


def _to_snapshot_item(row: DiscoverySnapshot) -> DiscoverySnapshotItem:
    snapshot_at_iso = (
        row.snapshot_at.isoformat() if isinstance(row.snapshot_at, datetime) else str(row.snapshot_at or "")
    )
    return DiscoverySnapshotItem(
        ticker=row.ticker,
        cik=row.cik,
        company=row.company,
        score=row.score,
        distinct_sources=row.distinct_sources,
        snapshot_at=snapshot_at_iso,
    )


def get_history(ticker: str, days: int = 30, limit: int = 200) -> DiscoveryHistoryResponse:
    """Return snapshot time series for a ticker over the last N days."""
    sym = ticker.strip().upper()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    db: Session = SessionLocal()
    try:
        rows = (
            db.query(DiscoverySnapshot)
            .filter(
                DiscoverySnapshot.ticker == sym,
                DiscoverySnapshot.snapshot_at >= cutoff,
            )
            .order_by(DiscoverySnapshot.snapshot_at.asc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()

    items = [_to_snapshot_item(r) for r in rows]
    return DiscoveryHistoryResponse(
        ticker=sym,
        snapshots=items,
        total=len(items),
    )


def get_movers(days: int = 7, limit: int = 20, min_abs_delta: float = 20.0) -> DiscoveryMoversResponse:
    """Return tickers whose Discovery score moved by >= ``min_abs_delta`` over the window.

    For each ticker with snapshots in the lookback window, compares latest snapshot
    score to the oldest one in-window and reports the absolute delta. Sorted
    largest absolute movement first.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    db: Session = SessionLocal()
    try:
        rows = (
            db.query(DiscoverySnapshot)
            .filter(DiscoverySnapshot.snapshot_at >= cutoff)
            .order_by(DiscoverySnapshot.snapshot_at.asc())
            .all()
        )
    finally:
        db.close()

    by_ticker: dict[str, list[DiscoverySnapshot]] = {}
    for r in rows:
        by_ticker.setdefault(r.ticker, []).append(r)

    movers: list[DiscoveryMover] = []
    for ticker, snapshots in by_ticker.items():
        if len(snapshots) < 2:
            continue
        before = snapshots[0]
        now = snapshots[-1]
        delta = now.score - before.score
        if abs(delta) < min_abs_delta:
            continue
        movers.append(DiscoveryMover(
            ticker=ticker,
            cik=now.cik,
            company=now.company,
            score_now=now.score,
            score_before=before.score,
            delta=delta,
            snapshot_at_now=now.snapshot_at.isoformat() if isinstance(now.snapshot_at, datetime) else str(now.snapshot_at or ""),
            snapshot_at_before=before.snapshot_at.isoformat() if isinstance(before.snapshot_at, datetime) else str(before.snapshot_at or ""),
        ))

    movers.sort(key=lambda m: -abs(m.delta))
    movers = movers[:limit]
    return DiscoveryMoversResponse(movers=movers, days=days, total=len(movers))
