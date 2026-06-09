"""score_movement alert rule — fires when a watchlist ticker's Discovery score
changes by >= ``min_abs_delta`` over the lookback window.

Reads from the persisted ``DiscoverySnapshot`` history (built by the Discovery
service on each fresh compute). Universe is restricted to the user's watchlist
to keep the signal actionable; non-watchlist score movers are already covered
by the high_confluence rule.

Severity:
  - warning: score moved up by threshold (positive momentum)
  - critical: score moved down by threshold (deterioration on a watched name)
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.backend.database import SessionLocal
from app.backend.database.models import DiscoverySnapshot, WatchlistItem
from app.backend.services.alert_service._types import AlertCandidate

logger = logging.getLogger(__name__)

_DEFAULT_LOOKBACK_DAYS: int = 7
_DEFAULT_MIN_ABS_DELTA: float = 30.0


async def evaluate(thresholds: dict) -> list[AlertCandidate]:
    """Compare each watchlist ticker's latest score to its oldest in-window score."""
    lookback_days: int = int(thresholds.get("lookback_days", _DEFAULT_LOOKBACK_DAYS))
    min_abs_delta: float = float(thresholds.get("min_abs_delta", _DEFAULT_MIN_ABS_DELTA))

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    db: Session = SessionLocal()
    try:
        watched = {
            row[0].upper()
            for row in db.query(WatchlistItem.ticker).all()
            if row[0]
        }
        if not watched:
            return []

        snapshots = (
            db.query(DiscoverySnapshot)
            .filter(
                DiscoverySnapshot.snapshot_at >= cutoff,
                DiscoverySnapshot.ticker.in_(watched),
            )
            .order_by(DiscoverySnapshot.snapshot_at.asc())
            .all()
        )
    finally:
        db.close()

    by_ticker: dict[str, list[DiscoverySnapshot]] = {}
    for s in snapshots:
        by_ticker.setdefault(s.ticker.upper(), []).append(s)

    out: list[AlertCandidate] = []
    for ticker, history in by_ticker.items():
        if len(history) < 2:
            continue
        before = history[0]
        now = history[-1]
        delta: float = now.score - before.score
        if abs(delta) < min_abs_delta:
            continue

        direction = "up" if delta > 0 else "down"
        emoji = "🚀" if delta > 0 else "📉"
        severity = "warning" if delta > 0 else "critical"
        # De-dupe key encodes direction so a flip-back fires a fresh alert.
        ticker_key = f"{ticker}:{direction}"[:20]

        out.append(AlertCandidate(
            rule_type="score_movement",
            ticker=ticker_key,
            title=f"{emoji} {ticker}: score {direction} {abs(delta):.0f} pts ({lookback_days}d)",
            message=(
                f"{ticker} Discovery score moved from {before.score:.0f} to {now.score:.0f} "
                f"over the last {lookback_days} days "
                f"(delta {delta:+.1f}).\n"
                f"Distinct sources now: {now.distinct_sources}.\n"
                f"From: {before.snapshot_at}\n"
                f"To:   {now.snapshot_at}"
            ),
            payload={
                "ticker": ticker,
                "direction": direction,
                "delta": round(delta, 2),
                "score_now": now.score,
                "score_before": before.score,
                "snapshot_at_now": now.snapshot_at.isoformat() if isinstance(now.snapshot_at, datetime) else str(now.snapshot_at or ""),
                "snapshot_at_before": before.snapshot_at.isoformat() if isinstance(before.snapshot_at, datetime) else str(before.snapshot_at or ""),
                "lookback_days": lookback_days,
            },
            severity=severity,
        ))
    return out
