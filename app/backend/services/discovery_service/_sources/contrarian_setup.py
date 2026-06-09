"""Discovery source: 'Golden Entry' — insiders buying while news is bearish.

The contrarian signal. Pulls tickers with material insider activity from
OpenInsider (cluster_buy + ceo_cfo_conviction presets — already cached by
their respective sources, so the OpenInsider hit is free), then queries
Finnhub news-sentiment per ticker. Where bearish coverage outweighs bullish,
emits a contrarian boost — i.e., the 'pros buying while retail / news hate
the name' inflection.

Score:
  - +25 base contrarian setup (insider activity + bearish_pct > bullish_pct)
  - +35 "deep contrarian" (bearish_pct ≥ 0.6 — overwhelmingly negative coverage)
"""

import asyncio
import logging
from collections import defaultdict

from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)

_BASE_SCORE = 25.0
_DEEP_BEARISH_THRESHOLD = 0.6
_DEEP_SCORE = 35.0
_MIN_BEARISH_LEAD = 0.05  # bearish must lead bullish by at least 5pp
_MIN_TICKER_INSIDERS = 2  # filter tiny-noise tickers


async def fetch() -> list[tuple[str, IdeaSignal]]:
    from app.backend.services.news_sentiment_service import get_sentiment_batch, is_available
    from app.backend.services.openinsider_service import get_openinsider_screener

    if not is_available():
        logger.info("contrarian_setup: FINNHUB_API_KEY not configured — skipping")
        return []

    insider_records: dict[str, list] = defaultdict(list)

    cluster_task = get_openinsider_screener("cluster_buy", None)
    csuite_task = get_openinsider_screener("ceo_cfo_conviction", None)
    cluster_resp, csuite_resp = await asyncio.gather(
        cluster_task, csuite_task, return_exceptions=True,
    )

    if not isinstance(cluster_resp, BaseException):
        for rec in cluster_resp.records:
            if rec.ticker:
                insider_records[rec.ticker.upper()].append(rec)
    if not isinstance(csuite_resp, BaseException):
        for rec in csuite_resp.records:
            if rec.ticker and (rec.value or 0) >= 250_000:
                insider_records[rec.ticker.upper()].append(rec)

    candidates = [
        ticker for ticker, recs in insider_records.items()
        if len({r.insider_name for r in recs if r.insider_name}) >= _MIN_TICKER_INSIDERS
    ]
    if not candidates:
        return []

    # Bound the Finnhub call: 30 candidates per pass keeps us well under 60/min
    capped = candidates[:30]
    sentiment_by_ticker = await get_sentiment_batch(capped)

    out: list[tuple[str, IdeaSignal]] = []
    for ticker in capped:
        sentiment = sentiment_by_ticker.get(ticker)
        if sentiment is None:
            continue
        if sentiment.bearish_percent <= sentiment.bullish_percent + _MIN_BEARISH_LEAD:
            continue

        recs = insider_records[ticker]
        distinct_insiders = len({r.insider_name for r in recs if r.insider_name})
        total_value = sum(r.value or 0 for r in recs)

        is_deep = sentiment.bearish_percent >= _DEEP_BEARISH_THRESHOLD
        score = _DEEP_SCORE if is_deep else _BASE_SCORE
        adjective = "Deeply hated" if is_deep else "Hated"
        label = (
            f"{adjective} ({sentiment.bearish_percent * 100:.0f}% bearish news) "
            f"+ {distinct_insiders} insiders buying"
        )

        out.append((ticker, IdeaSignal(
            source="contrarian_setup",
            score=score,
            label=label,
            detail={
                "ticker": ticker,
                "bearish_percent": sentiment.bearish_percent,
                "bullish_percent": sentiment.bullish_percent,
                "company_news_score": sentiment.company_news_score,
                "sector_avg_score": sentiment.sector_avg_score,
                "article_count": sentiment.article_count,
                "distinct_insiders": distinct_insiders,
                "total_insider_value": total_value,
            },
        )))
    return out
