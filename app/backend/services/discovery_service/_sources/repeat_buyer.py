"""Discovery source: same insider buying the same ticker 3+ times in 30 days.

Captures the "building a position" pattern — insiders who keep coming back to
the open market over weeks signal real conviction (vs. one-off rebalancing).

Uses OpenInsider's `latest_insider_buys_25k` preset, groups by
(insider_name, ticker), and counts distinct trade dates. A ticker can have
multiple repeat-buyers; we emit one IdeaSignal per ticker, capturing the most
prolific insider as the primary.

Score:
  - 20 base when one insider has 3+ distinct trade dates
  - 30 if 5+ trade dates OR 2+ distinct insiders both repeating
"""

import logging
from collections import defaultdict

from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)

_MIN_TRADES_PER_INSIDER = 3
_PROLIFIC_TRADES = 5


async def fetch() -> list[tuple[str, IdeaSignal]]:
    try:
        from app.backend.services.openinsider_service import get_openinsider_screener
        response = await get_openinsider_screener("latest_insider_buys_25k", None)
    except Exception as exc:
        logger.warning("repeat_buyer: fetch failed: %s", exc)
        return []

    # Group records by (ticker, insider_name)
    grouped: dict[tuple[str, str], list[object]] = defaultdict(list)
    for rec in response.records:
        if not rec.ticker or not rec.insider_name:
            continue
        grouped[(rec.ticker.upper(), rec.insider_name)].append(rec)

    # Identify (ticker, insider) pairs with enough distinct trade dates
    repeat_pairs: dict[str, list[tuple[str, list[object]]]] = defaultdict(list)
    for (ticker, insider), recs in grouped.items():
        distinct_dates = {r.trade_date for r in recs if r.trade_date}
        if len(distinct_dates) >= _MIN_TRADES_PER_INSIDER:
            repeat_pairs[ticker].append((insider, recs))

    out: list[tuple[str, IdeaSignal]] = []
    for ticker, insider_groups in repeat_pairs.items():
        # Pick the most-prolific insider as the primary
        insider_groups.sort(key=lambda ig: len({r.trade_date for r in ig[1] if r.trade_date}), reverse=True)
        primary_insider, primary_recs = insider_groups[0]
        primary_dates = {r.trade_date for r in primary_recs if r.trade_date}
        primary_total = sum(r.value or 0 for r in primary_recs)

        prolific = len(primary_dates) >= _PROLIFIC_TRADES
        multiple_repeaters = len(insider_groups) >= 2
        score = 30.0 if (prolific or multiple_repeaters) else 20.0

        label = f"{primary_insider} bought {len(primary_dates)}× in 30d"

        out.append((ticker, IdeaSignal(
            source="repeat_buyer",
            score=score,
            label=label,
            detail={
                "ticker": ticker,
                "company": primary_recs[0].company_name,
                "primary_insider": primary_insider,
                "primary_title": primary_recs[0].title,
                "primary_trade_count": len(primary_dates),
                "primary_total_value": primary_total,
                "repeating_insider_count": len(insider_groups),
                "all_repeat_insiders": [ig[0] for ig in insider_groups][:5],
            },
        )))
    return out
