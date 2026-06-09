"""Discovery engine: run all sources in parallel, aggregate by key, sort by score.

Applies time-decay to insider-flavored signals (cluster_buy, csuite_buy, etc.)
so a 90-day-old CFO buy no longer contributes its full score to the composite
ranking. Half-life of 45 days, floor of 10%. Signals without a detectable date
field pass through at full strength — appropriate for inherently-fresh
signals like commodity_tailwind, squeeze, and relative_strength.
"""

import asyncio
import logging
import math
from collections import defaultdict
from datetime import date, datetime

from app.backend.models.discovery_schemas import DiscoveryIdea, IdeaSignal
from app.backend.services.discovery_service._sources import SOURCES

logger = logging.getLogger(__name__)

_DECAY_HALF_LIFE_DAYS = 45.0
_DECAY_FLOOR = 0.1

# Cap concurrent source execution. Fanning all sources in parallel on cold
# cache spikes CPU and trips upstream yfinance / EDGAR rate limits.
_SOURCE_CONCURRENCY = 4

# Detail keys that carry a meaningful "as-of" date — first hit wins.
_DATE_KEYS = (
    "trade_date", "filing_date", "last_date", "latest_filing_date",
    "first_date", "date", "snapshot_at",
)


def _extract_date(detail: dict | None) -> date | None:
    if not detail:
        return None
    for key in _DATE_KEYS:
        raw = detail.get(key)
        if not raw:
            continue
        text = str(raw).strip()
        if not text:
            continue
        try:
            # Accept full ISO datetimes too — keep just the date prefix
            return date.fromisoformat(text[:10])
        except ValueError:
            continue
    return None


def _decay_multiplier(signal_date: date | None) -> float:
    """Return the score multiplier for a signal of given age. Fresh signals
    (today) get 1.0; 45-day-old signals get 0.5; old signals floor at 0.1.
    """
    if signal_date is None:
        return 1.0
    today = date.today()
    age_days = max(0, (today - signal_date).days)
    if age_days == 0:
        return 1.0
    raw = math.pow(0.5, age_days / _DECAY_HALF_LIFE_DAYS)
    return max(_DECAY_FLOOR, raw)


def _apply_decay(signal: IdeaSignal) -> IdeaSignal:
    """Return a new IdeaSignal with decayed score + decay metadata. Does NOT
    mutate the input — sources are free to share signal instances.
    """
    signal_date = _extract_date(signal.detail)
    multiplier = _decay_multiplier(signal_date)
    if multiplier >= 0.999:
        return signal

    decayed_score = signal.score * multiplier
    new_detail = dict(signal.detail or {})
    new_detail["original_score"] = signal.score
    new_detail["decay_multiplier"] = round(multiplier, 3)
    if signal_date is not None:
        new_detail["signal_age_days"] = (date.today() - signal_date).days

    return IdeaSignal(
        source=signal.source,
        score=round(decayed_score, 2),
        label=signal.label,
        detail=new_detail,
        kill_filter=signal.kill_filter,
    )


async def aggregate_ideas() -> list[DiscoveryIdea]:
    # Partial-success fanout: one source failing must not cancel the others.
    # This is the documented exception case for gather(return_exceptions=True);
    # TaskGroup's all-or-nothing semantics would lose 18 sources' work on
    # any single yfinance / EDGAR transient failure.
    sem = asyncio.Semaphore(_SOURCE_CONCURRENCY)

    async def _gated(fn):
        async with sem:
            return await fn()

    tasks = [_gated(src) for _, src in SOURCES]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    by_key: dict[str, list[IdeaSignal]] = defaultdict(list)
    for (source_name, _), result in zip(SOURCES, results):
        if isinstance(result, Exception):
            logger.warning("Discovery source %s failed: %s", source_name, result)
            continue
        for key, signal in result:
            by_key[key].append(_apply_decay(signal))

    ideas: list[DiscoveryIdea] = []
    for key, signals in by_key.items():
        # kill_filter: any signal can hard-exclude this ticker (e.g. a future
        # 'high_leverage' source flagging zombie companies). Honor it before
        # building the idea, so kill-flagged tickers never reach the response.
        if any(s.kill_filter for s in signals):
            logger.debug(
                "discovery_engine: dropping %s — kill_filter set by %s",
                key, [s.source for s in signals if s.kill_filter],
            )
            continue

        is_ticker = not key.startswith("cik:")
        if is_ticker:
            ticker_or_cik = key
            cik = None
        else:
            try:
                cik = int(key.split(":", 1)[1])
            except (ValueError, IndexError):
                cik = None
            ticker_or_cik = key.split(":", 1)[1] if ":" in key else key

        # Pick first non-null company name across signals' detail
        company = None
        for s in signals:
            if s.detail:
                name = s.detail.get("company")
                if name:
                    company = name
                    break

        ideas.append(DiscoveryIdea(
            ticker=ticker_or_cik,
            company=company,
            cik=cik,
            score=sum(s.score for s in signals),
            signals=sorted(signals, key=lambda s: -s.score),
            is_ticker=is_ticker,
        ))

    ideas.sort(key=lambda i: -i.score)
    return ideas
