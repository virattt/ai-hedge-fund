"""Discovery source: reasonably-priced growth via PEG ratio.

Targets the GARP investor — companies whose forward P/E is justified by
their growth rate. PEG = trailing P/E divided by EPS growth %; a PEG below
1.0 means the market is pricing the stock cheaper than its growth implies.

This is a *valuation* signal, not a catalyst — fires on names that are simply
reasonably priced today, regardless of whether anything is happening.

Universe: watchlist tickers + recent DiscoverySnapshot tickers, capped at 60.

Score:
  - +20 base:  PEG ≤ 1.0 (fair price for growth)
  - +30:       PEG ≤ 0.7 (cheap growth)
  - +35:       PEG ≤ 0.5 (deep value among growers — rare)

Skips: PEG missing, PEG ≤ 0 (negative or zero growth distorts the ratio),
trailing P/E ≤ 0 (loss-making).
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.backend.database import SessionLocal
from app.backend.database.models import DiscoverySnapshot, WatchlistItem
from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)

_FAIR_PEG = 1.0
_CHEAP_PEG = 0.7
_DEEP_VALUE_PEG = 0.5

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
        peg = m.peg_ratio
        if peg is None or peg <= 0:
            continue
        if m.trailing_pe is None or m.trailing_pe <= 0:
            continue
        if peg > _FAIR_PEG:
            continue

        if peg <= _DEEP_VALUE_PEG:
            score = 35.0
            tier = "deep value"
        elif peg <= _CHEAP_PEG:
            score = 30.0
            tier = "cheap"
        else:
            score = 20.0
            tier = "fair"

        label = f"{tier}: PEG {peg:.2f} · P/E {m.trailing_pe:.1f}"
        out.append((ticker, IdeaSignal(
            source="valuation_score",
            score=score,
            label=label,
            detail={
                "ticker": ticker,
                "peg_ratio": peg,
                "trailing_pe": m.trailing_pe,
                "forward_pe": m.forward_pe,
                "price_to_book": m.price_to_book,
                "tier": tier,
            },
        )))
    return out
