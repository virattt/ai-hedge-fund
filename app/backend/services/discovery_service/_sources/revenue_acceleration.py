"""Discovery source: tickers with QoQ revenue growth rate ACCELERATING.

This is the fundamental confirmation signal. While the other 13 sources read
insider behavior / Wall Street positioning / price action / news, this one
reads what's actually happening at the *business* — revenue ramping faster
each quarter, the textbook setup that often shows up *before* insiders
finish accumulating and price breaks out.

Universe: watchlist tickers + tickers in the most recent DiscoverySnapshot
batch. We don't scan the whole market because yfinance fundamental fetches
are expensive — we restrict to names that already have *some* other reason
to be interesting.

Score:
  - +20 base: 2 consecutive accelerating quarters
  - +30:    3 or more consecutive accelerating quarters
  - +5 bonus if latest QoQ growth > 20% (high-velocity acceleration)
  - Skips: revenue shrinking in the latest quarter (don't flag declining names)
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.backend.database import SessionLocal
from app.backend.database.models import DiscoverySnapshot, WatchlistItem
from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)

_MIN_CONSECUTIVE = 2
_STRONG_CONSECUTIVE = 3
_HIGH_VELOCITY_THRESHOLD_PCT = 20.0
_UNIVERSE_LOOKBACK_HOURS = 48
_MAX_UNIVERSE_SIZE = 25  # bounds yfinance fundamental fetches per refresh


def _gather_universe() -> list[str]:
    """Watchlist + recently-seen Discovery tickers, deduped + capped."""
    db = SessionLocal()
    try:
        watchlist_tickers = {row[0].upper() for row in db.query(WatchlistItem.ticker).all() if row[0]}

        cutoff = datetime.now(timezone.utc) - timedelta(hours=_UNIVERSE_LOOKBACK_HOURS)
        snapshot_tickers = {
            row[0].upper()
            for row in (
                db.query(DiscoverySnapshot.ticker)
                .filter(DiscoverySnapshot.snapshot_at >= cutoff)
                .filter(DiscoverySnapshot.is_ticker == True)  # noqa: E712
                .group_by(DiscoverySnapshot.ticker)
                .order_by(func.max(DiscoverySnapshot.score).desc())
                .limit(_MAX_UNIVERSE_SIZE)
                .all()
            )
            if row[0]
        }
    finally:
        db.close()

    combined = watchlist_tickers | snapshot_tickers
    return sorted(combined)[:_MAX_UNIVERSE_SIZE]


async def fetch() -> list[tuple[str, IdeaSignal]]:
    from app.backend.services.fundamentals_service import get_revenue_growth_batch

    universe = _gather_universe()
    if not universe:
        return []

    analyses = await get_revenue_growth_batch(universe)

    out: list[tuple[str, IdeaSignal]] = []
    for ticker, analysis in analyses.items():
        if analysis is None or not analysis.has_data:
            continue
        if analysis.is_shrinking:
            continue
        if analysis.consecutive_accelerating < _MIN_CONSECUTIVE:
            continue

        score = 30.0 if analysis.consecutive_accelerating >= _STRONG_CONSECUTIVE else 20.0
        if (analysis.latest_qoq_growth_pct or 0) >= _HIGH_VELOCITY_THRESHOLD_PCT:
            score += 5.0

        latest_growth = analysis.latest_qoq_growth_pct or 0
        latest_period = analysis.quarters[-1].period_end if analysis.quarters else None
        label = (
            f"{analysis.consecutive_accelerating}q accelerating · "
            f"latest QoQ {latest_growth:+.0f}%"
        )

        out.append((ticker, IdeaSignal(
            source="revenue_acceleration",
            score=score,
            label=label,
            detail={
                "ticker": ticker,
                "consecutive_accelerating_quarters": analysis.consecutive_accelerating,
                "latest_qoq_growth_pct": analysis.latest_qoq_growth_pct,
                "qoq_growth_pcts": analysis.qoq_growth_pcts,
                "latest_period_end": latest_period,
                "quarters_analyzed": len(analysis.quarters),
            },
        )))

    return out
