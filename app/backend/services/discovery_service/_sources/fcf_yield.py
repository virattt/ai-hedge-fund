"""Discovery source: companies generating high free cash flow relative to market cap.

The "Cash Machine" filter. Net income can be massaged via accounting; free
cash flow is what actually lands in the company's bank account. A name with
FCF yield ≥ 7% is, by definition, generating real cash worth at least 7% of
its market cap each year — the kind of business Buffett and Greenblatt buy.

Universe: watchlist + recent DiscoverySnapshot tickers, capped at 25.

Score:
  - +15 base: FCF yield ≥ 7% (cash-cow territory)
  - +25:      FCF yield ≥ 10% (rare, often signals undervaluation)
  - +35:      FCF yield ≥ 15% (extreme, usually distressed-value or cyclical bottom)

Skips: FCF unavailable, FCF ≤ 0 (cash-burning company).
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.backend.database import SessionLocal
from app.backend.database.models import DiscoverySnapshot, WatchlistItem
from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)

_CASH_COW_FCF_YIELD = 0.07
_HIGH_FCF_YIELD = 0.10
_EXTREME_FCF_YIELD = 0.15

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
        if m is None or m.fcf_yield is None or m.fcf_yield < _CASH_COW_FCF_YIELD:
            continue
        if m.free_cash_flow is None or m.free_cash_flow <= 0:
            continue

        if m.fcf_yield >= _EXTREME_FCF_YIELD:
            score = 35.0
            tier = "extreme cash machine"
        elif m.fcf_yield >= _HIGH_FCF_YIELD:
            score = 25.0
            tier = "high-cash"
        else:
            score = 15.0
            tier = "cash-cow"

        yield_pct = m.fcf_yield * 100
        fcf_billions = m.free_cash_flow / 1e9 if m.free_cash_flow else 0
        if fcf_billions >= 1:
            fcf_str = f"${fcf_billions:.1f}B"
        else:
            fcf_str = f"${(m.free_cash_flow or 0) / 1e6:.0f}M"
        label = f"{tier}: {yield_pct:.0f}% FCF yield · {fcf_str} FCF"

        out.append((ticker, IdeaSignal(
            source="fcf_yield",
            score=score,
            label=label,
            detail={
                "ticker": ticker,
                "fcf_yield": m.fcf_yield,
                "free_cash_flow": m.free_cash_flow,
                "market_cap": m.market_cap,
                "tier": tier,
            },
        )))
    return out
