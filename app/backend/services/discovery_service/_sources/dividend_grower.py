"""Discovery source: long-term dividend growers (DGI / aristocrat / king tiers).

Targets the dividend-growth-investor crowd — companies that have raised the
annual dividend payout for 5+ consecutive years. Compounders that shareholders
trust enough to keep increasing the payout, often the most boring (and most
reliable) names in the market.

Universe: watchlist tickers + recent DiscoverySnapshot tickers, capped at 60.

Tiers, mirroring the standard dividend-investor lexicon:
  - +15:  5-9 consecutive years (DGI candidate)
  - +25:  10-24 consecutive years (Achiever / Aristocrat-track)
  - +35:  25+ consecutive years (Dividend King)

Skips: <5 years, no dividend history, negative current yield.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.backend.database import SessionLocal
from app.backend.database.models import DiscoverySnapshot, WatchlistItem
from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)

_DGI_THRESHOLD = 5
_ACHIEVER_THRESHOLD = 10
_KING_THRESHOLD = 25

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
    from app.backend.services.fundamentals_service import get_company_metrics_batch

    universe = _gather_universe()
    if not universe:
        return []

    metrics_by_ticker = await get_company_metrics_batch(universe)

    out: list[tuple[str, IdeaSignal]] = []
    for ticker, m in metrics_by_ticker.items():
        if m is None or not m.has_data:
            continue
        years = m.consecutive_dividend_growth_years
        if years < _DGI_THRESHOLD:
            continue
        if m.current_dividend_yield is None or m.current_dividend_yield <= 0:
            continue

        if years >= _KING_THRESHOLD:
            score = 35.0
            tier = "Dividend King"
        elif years >= _ACHIEVER_THRESHOLD:
            score = 25.0
            tier = "Dividend Achiever"
        else:
            score = 15.0
            tier = "DGI candidate"

        yield_pct = m.current_dividend_yield * 100
        label = f"{tier}: {years}y growth · {yield_pct:.1f}% yield"
        out.append((ticker, IdeaSignal(
            source="dividend_grower",
            score=score,
            label=label,
            detail={
                "ticker": ticker,
                "consecutive_growth_years": years,
                "current_yield_pct": yield_pct,
                "tier": tier,
            },
        )))
    return out
