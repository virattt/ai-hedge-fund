"""Discovery source: high return on invested capital (ROIC) — the Buffett filter.

ROIC measures how efficiently a company turns invested capital (debt +
equity) into operating profit. Sustained ROIC above the cost of capital
(roughly 10%) is the cleanest indicator of a durable competitive advantage
— a moat. ROIC ≥ 15% AND increasing for 3 years is the textbook
"wonderful business" signature.

Universe: watchlist + recent DiscoverySnapshot tickers, capped at 25.

Score:
  - +20 base: latest ROIC ≥ 15%
  - +30:      latest ROIC ≥ 25% (top-decile capital efficiency)
  - +35:      either tier above PLUS strict 3-year monotonic increase
              (capital efficiency *improving*, not just high)
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.backend.database import SessionLocal
from app.backend.database.models import DiscoverySnapshot, WatchlistItem
from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)

_HIGH_ROIC_PCT = 15.0
_TOP_DECILE_ROIC_PCT = 25.0

_UNIVERSE_LOOKBACK_HOURS = 48
_MAX_UNIVERSE_SIZE = 25


def _gather_universe() -> list[str]:
    db = SessionLocal()
    try:
        watchlist = {row[0].upper() for row in db.query(WatchlistItem.ticker).all() if row[0]}
        cutoff = datetime.now(timezone.utc) - timedelta(hours=_UNIVERSE_LOOKBACK_HOURS)
        snapshots = {
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
    return sorted(watchlist | snapshots)[:_MAX_UNIVERSE_SIZE]


async def fetch() -> list[tuple[str, IdeaSignal]]:
    from app.backend.services.fundamentals_service import get_roic_history_batch

    universe = _gather_universe()
    if not universe:
        return []

    history_by_ticker = await get_roic_history_batch(universe)

    out: list[tuple[str, IdeaSignal]] = []
    for ticker, history in history_by_ticker.items():
        if history is None or not history.has_data:
            continue
        latest = history.latest_roic_pct
        if latest is None or latest < _HIGH_ROIC_PCT:
            continue

        if latest >= _TOP_DECILE_ROIC_PCT:
            base = 30.0
            tier = "top-decile ROIC"
        else:
            base = 20.0
            tier = "high ROIC"

        if history.is_increasing_3y:
            score = max(base, 35.0)
            tier += " + improving 3y"
        else:
            score = base

        recent_str = ", ".join(f"{y.roic_pct:.0f}%" for y in history.years[-3:])
        label = f"{tier}: latest {latest:.0f}% (3y: {recent_str})"

        out.append((ticker, IdeaSignal(
            source="high_roic",
            score=score,
            label=label,
            detail={
                "ticker": ticker,
                "latest_roic_pct": latest,
                "is_increasing_3y": history.is_increasing_3y,
                "roic_history": [
                    {"period_end": y.period_end, "roic_pct": y.roic_pct}
                    for y in history.years
                ],
                "tier": tier,
            },
        )))
    return out
