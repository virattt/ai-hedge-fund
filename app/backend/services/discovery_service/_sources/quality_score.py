"""Discovery source: high-quality compounder businesses.

Identifies companies with durable competitive advantages — high ROE, low debt,
fat margins. Unlike the catalyst-driven sources (insider buys, spinoffs), this
fires on the *steady-state* fundamentals: a name that consistently earns high
returns on shareholder capital with a clean balance sheet, regardless of
whether something is happening this month.

Universe: watchlist tickers + recent DiscoverySnapshot tickers, capped at 60
to bound yfinance cost.

Score:
  - +20 base: ROE ≥ 15% AND debt/equity ≤ 1.0
  - +30:     ROE ≥ 20% AND debt/equity ≤ 0.5 AND gross_margin ≥ 0.40
  - +35:     all of the above PLUS profit_margin ≥ 0.20 (top-tier compounder)
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.backend.database import SessionLocal
from app.backend.database.models import DiscoverySnapshot, WatchlistItem
from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)

_SOLID_ROE = 0.15
_HIGH_ROE = 0.20
_SOLID_DTE_MAX = 1.0  # debt-to-equity
_HIGH_DTE_MAX = 0.5
_HIGH_GROSS_MARGIN = 0.40
_TOP_TIER_PROFIT_MARGIN = 0.20

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
        if m.return_on_equity is None:
            continue

        # yfinance returns debtToEquity as a percentage (e.g. 50.0 = 50%, i.e. 0.5)
        # rather than a ratio. Convert if it looks like a percentage.
        dte = m.debt_to_equity
        if dte is not None and dte > 5.0:
            dte = dte / 100.0

        passes_solid = m.return_on_equity >= _SOLID_ROE and (dte is None or dte <= _SOLID_DTE_MAX)
        if not passes_solid:
            continue

        passes_high = (
            m.return_on_equity >= _HIGH_ROE
            and (dte is None or dte <= _HIGH_DTE_MAX)
            and (m.gross_margin or 0) >= _HIGH_GROSS_MARGIN
        )
        passes_top = passes_high and (m.profit_margin or 0) >= _TOP_TIER_PROFIT_MARGIN

        if passes_top:
            score = 35.0
            tier_label = "top-tier compounder"
        elif passes_high:
            score = 30.0
            tier_label = "high-quality"
        else:
            score = 20.0
            tier_label = "solid quality"

        roe_pct = m.return_on_equity * 100
        gross_pct = (m.gross_margin or 0) * 100
        label = f"{tier_label}: ROE {roe_pct:.0f}% · GM {gross_pct:.0f}%"

        out.append((ticker, IdeaSignal(
            source="quality_score",
            score=score,
            label=label,
            detail={
                "ticker": ticker,
                "return_on_equity": m.return_on_equity,
                "debt_to_equity": dte,
                "gross_margin": m.gross_margin,
                "profit_margin": m.profit_margin,
                "tier": tier_label,
            },
        )))
    return out
