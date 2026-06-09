"""Discovery source: tickers with cluster insider buys (3+ distinct insiders).

Reuses the OpenInsider `cluster_buy` preset (already cached). Aggregates
records by ticker, counts distinct insiders + total dollar value.

Score:
  - 15 base when 3-4 distinct insiders bought
  - 25 when 5+ distinct insiders bought ("everyone's buying" moment)
"""

import logging
from collections import defaultdict

from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)

_MIN_INSIDERS = 3
_BIG_CLUSTER = 5


async def fetch() -> list[tuple[str, IdeaSignal]]:
    try:
        from app.backend.services.openinsider_service import get_openinsider_screener
        response = await get_openinsider_screener("cluster_buy", None)
    except Exception as exc:
        logger.warning("cluster_buy source: fetch failed: %s", exc)
        return []

    by_ticker: dict[str, list] = defaultdict(list)
    for rec in response.records:
        if rec.ticker:
            by_ticker[rec.ticker.upper()].append(rec)

    out: list[tuple[str, IdeaSignal]] = []
    for ticker, recs in by_ticker.items():
        distinct_insiders = len({r.insider_name for r in recs if r.insider_name})
        if distinct_insiders < _MIN_INSIDERS:
            continue

        total_value = sum(r.value or 0 for r in recs)
        score = 25.0 if distinct_insiders >= _BIG_CLUSTER else 15.0
        label = f"{distinct_insiders} insiders bought ${total_value:,.0f}"

        dates = [r.trade_date for r in recs if r.trade_date]
        out.append((ticker, IdeaSignal(
            source="cluster_buy",
            score=score,
            label=label,
            detail={
                "ticker": ticker,
                "company": next((r.company_name for r in recs if r.company_name), None),
                "distinct_insiders": distinct_insiders,
                "total_value": total_value,
                "transaction_count": len(recs),
                "insider_names": sorted({r.insider_name for r in recs if r.insider_name})[:10],
                "first_date": min(dates) if dates else None,
                "last_date": max(dates) if dates else None,
            },
        )))
    return out
