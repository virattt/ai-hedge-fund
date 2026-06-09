"""Discovery source: single insider transactions ≥ $1M (whale-insider trades).

Uses OpenInsider's `latest_insider_buys_25k` preset and filters to large
single transactions. Catches the case where one CFO drops $5M in one trade —
which cluster_buy misses by definition (cluster requires 3+ insiders).

Score:
  - 25 base for ≥ $1M single trade
  - 40 if ≥ $5M (institutional-scale insider conviction)
"""

import logging
from collections import defaultdict

from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)

_MIN_VALUE = 1_000_000.0
_BIG_VALUE = 5_000_000.0


async def fetch() -> list[tuple[str, IdeaSignal]]:
    try:
        from app.backend.services.openinsider_service import get_openinsider_screener
        response = await get_openinsider_screener("latest_insider_buys_25k", None)
    except Exception as exc:
        logger.warning("mega_dollar_buy: fetch failed: %s", exc)
        return []

    by_ticker: dict[str, list[object]] = defaultdict(list)
    for rec in response.records:
        if not rec.ticker:
            continue
        if (rec.value or 0) < _MIN_VALUE:
            continue
        by_ticker[rec.ticker.upper()].append(rec)

    out: list[tuple[str, IdeaSignal]] = []
    for ticker, recs in by_ticker.items():
        top = max(recs, key=lambda r: r.value or 0)
        max_value = top.value or 0
        total_value = sum(r.value or 0 for r in recs)

        score = 40.0 if max_value >= _BIG_VALUE else 25.0
        label = f"{top.insider_name or 'Insider'} ${max_value:,.0f} mega-buy"

        out.append((ticker, IdeaSignal(
            source="mega_dollar_buy",
            score=score,
            label=label,
            detail={
                "ticker": ticker,
                "company": next((r.company_name for r in recs if r.company_name), None),
                "top_insider": top.insider_name,
                "top_title": top.title,
                "top_value": max_value,
                "trade_date": top.trade_date,
                "transaction_count": len(recs),
                "total_value": total_value,
            },
        )))
    return out
