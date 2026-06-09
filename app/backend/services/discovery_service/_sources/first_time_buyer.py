"""Discovery source: officer/director making their first open-market purchase.

Uses OpenInsider's `latest_officer_buys_25k` preset (officers/directors only,
trades ≥ $25k). A first-time buy is detected via the `delta_own` cell being
"New" — OpenInsider's marker for positions that did not exist before the trade.

Captures the "I just sat in this chair and I see what's coming" trade.

Score:
  - 15 base
  - 20 if title contains CEO / CFO / President / Chair (highest-rank conviction)
"""

import logging
from collections import defaultdict

from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)

_HIGH_RANK_TOKENS = (
    "ceo", "cfo", "president", "chair",
    "chief executive", "chief financial",
)


def _is_first_time(delta_own_raw: str | None) -> bool:
    if delta_own_raw is None:
        return False
    return delta_own_raw.strip().lower() == "new"


def _is_high_rank(title: str | None) -> bool:
    if not title:
        return False
    title_lc = title.lower()
    return any(tok in title_lc for tok in _HIGH_RANK_TOKENS)


async def fetch() -> list[tuple[str, IdeaSignal]]:
    try:
        from app.backend.services.openinsider_service import get_openinsider_screener
        response = await get_openinsider_screener("latest_officer_buys_25k", None)
    except Exception as exc:
        logger.warning("first_time_buyer: fetch failed: %s", exc)
        return []

    by_ticker: dict[str, list[object]] = defaultdict(list)
    for rec in response.records:
        if not rec.ticker:
            continue
        if not _is_first_time(rec.delta_own):
            continue
        by_ticker[rec.ticker.upper()].append(rec)

    out: list[tuple[str, IdeaSignal]] = []
    for ticker, recs in by_ticker.items():
        # Pick the highest-rank insider as the primary, but report total.
        top = max(recs, key=lambda r: (_is_high_rank(r.title), r.value or 0))
        score = 20.0 if _is_high_rank(top.title) else 15.0

        total_value = sum(r.value or 0 for r in recs)
        label = f"{top.title or 'New insider'} initial buy ${(top.value or 0):,.0f}"

        out.append((ticker, IdeaSignal(
            source="first_time_buyer",
            score=score,
            label=label,
            detail={
                "ticker": ticker,
                "company": top.company_name,
                "insider_name": top.insider_name,
                "title": top.title,
                "value": top.value,
                "trade_date": top.trade_date,
                "qualifying_count": len(recs),
                "total_value": total_value,
            },
        )))
    return out
