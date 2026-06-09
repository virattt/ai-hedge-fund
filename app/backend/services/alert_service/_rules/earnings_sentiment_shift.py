"""earnings_sentiment_shift rule — fires on watchlist tickers whose latest
sentiment delta direction is improving or deteriorating.

The framework's de-dupe (rule_type, ticker, 3-day window) is leveraged by
encoding the direction in the ticker key — so a flip from improving →
deteriorating fires a NEW alert rather than being suppressed.
"""

import logging

from app.backend.database import SessionLocal
from app.backend.database.models import WatchlistItem
from app.backend.services.alert_service._types import AlertCandidate

logger = logging.getLogger(__name__)


async def evaluate(_thresholds: dict) -> list[AlertCandidate]:
    db = SessionLocal()
    try:
        items = (
            db.query(WatchlistItem)
            .filter(WatchlistItem.last_delta_direction.isnot(None))
            .all()
        )
    finally:
        db.close()

    out: list[AlertCandidate] = []
    for item in items:
        direction = item.last_delta_direction
        if direction in (None, "stable"):
            continue  # only alert on actionable shifts

        # Encode direction in ticker key so each direction state is its own
        # de-dupe slot (allows flip-back to fire a new alert)
        ticker_key = f"{item.ticker}:{direction}"[:20]

        emoji = "📈" if direction == "improving" else "📉"
        severity = "warning" if direction == "improving" else "critical"

        out.append(AlertCandidate(
            rule_type="earnings_sentiment_shift",
            ticker=ticker_key,
            title=f"{emoji} {item.ticker}: sentiment {direction}",
            message=(
                f"Earnings sentiment for {item.ticker} shifted to '{direction}'.\n"
                f"Overall: {item.last_overall_sentiment or '?'}\n"
                f"Management tone: {item.last_management_tone or '?'}\n"
                f"Last analyzed: {item.last_analyzed_at}"
            ),
            payload=item.last_payload or {},
            severity=severity,
        ))
    return out
