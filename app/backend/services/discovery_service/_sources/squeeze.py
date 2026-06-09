"""Discovery source: short-squeeze candidates from Finnhub/yfinance.

Each qualifying candidate (short ≥ 25%, days_to_cover ≥ 2, has insider buys)
contributes +15 to its ticker's score. Reuses the cached squeeze service.
"""

import logging

from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)

_MIN_SHORT_PCT = 25.0
_MIN_DAYS_TO_COVER = 2.0


async def fetch() -> list[tuple[str, IdeaSignal]]:
    try:
        from app.backend.services.finnhub_service import get_squeeze_candidates
        response = await get_squeeze_candidates()
    except Exception as exc:
        logger.warning("squeeze source: fetch failed: %s", exc)
        return []

    out: list[tuple[str, IdeaSignal]] = []
    for c in response.candidates:
        spct = c.short_pct_float or 0
        dtc = c.days_to_cover or 0
        if spct < _MIN_SHORT_PCT or dtc < _MIN_DAYS_TO_COVER:
            continue

        out.append((
            c.ticker,
            IdeaSignal(
                source="squeeze",
                score=15.0,
                label=f"{spct:.0f}% short, {dtc:.1f}d to cover",
                detail={
                    "ticker": c.ticker,
                    "company": c.company_name,
                    "short_pct_float": spct,
                    "days_to_cover": dtc,
                    "insider_buy_count": c.insider_buy_count,
                    "insider_buy_value": c.insider_buy_value,
                },
            ),
        ))
    return out
