"""News sentiment service — yfinance headlines + keyword classification.

Was previously Finnhub-backed, but Finnhub's /news-sentiment endpoint moved
behind the paid tier (free returns 403). Pivoted to yfinance's free news feed
and a keyword classifier — less precise than Finnhub's NLP scoring but
sufficient for the 'is the news net-bearish enough to be a contrarian setup?'
use case driving contrarian_setup.

Returns the same NewsSentimentResult dataclass so all downstream consumers
work unchanged. Caches 6h per ticker (yfinance news is fresh-ish but not
realtime, and re-fetching constantly burns CPU on parsing).
"""

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass

import yfinance as yf

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS: float = 6 * 3600.0
_CACHE_MAX_SIZE: int = 500

# Keyword sets — favor specificity over volume. Single-word matches against
# both title and summary, lower-cased.
_BEARISH_KEYWORDS: frozenset[str] = frozenset({
    "downgrade", "downgrades", "downgraded",
    "miss", "misses", "missed",
    "warning", "warns", "warned",
    "lawsuit", "sued", "litigation",
    "investigation", "investigates", "probe", "probed",
    "fraud", "scandal", "scam",
    "decline", "declines", "declined", "declining",
    "drop", "drops", "dropped", "dropping",
    "selloff", "sell-off", "plunge", "plunges", "plunged",
    "slump", "slumps", "slumped", "slumping",
    "crash", "crashes", "crashed",
    "concern", "concerns", "concerning",
    "headwind", "headwinds",
    "cut", "cuts", "slashed", "slash",
    "fired", "ousted", "resigns", "resigned", "stepping down",
    "weak", "weakness", "weakening",
    "slowdown", "slowing",
    "loss", "losses", "loses", "lost",
    "bearish", "bear", "negative", "pessimistic",
    "delisted", "delisting",
    "bankrupt", "bankruptcy",
})

_BULLISH_KEYWORDS: frozenset[str] = frozenset({
    "upgrade", "upgrades", "upgraded",
    "beat", "beats", "topped", "topping",
    "raise", "raised", "raises",
    "surge", "surges", "surged", "surging",
    "rally", "rallies", "rallied",
    "rise", "rises", "rising", "rose",
    "jump", "jumps", "jumped", "jumping",
    "soar", "soars", "soared", "soaring",
    "growth", "growing",
    "strong", "strength", "robust",
    "tailwind", "tailwinds",
    "breakthrough",
    "partnership", "partner", "partnered",
    "acquisition", "acquires", "acquired",
    "expansion", "expands", "expanded", "expanding",
    "profit", "profits", "profitable",
    "boost", "boosts", "boosted",
    "record", "high", "all-time high",
    "bullish", "bull", "positive", "optimistic",
    "outperform", "outperforms", "outperformed",
    "approval", "approved", "approves",
    "wins", "winning", "victory",
})

# Words present in nearly every finance headline that don't signal direction
_STOPWORDS: frozenset[str] = frozenset({
    "stock", "shares", "company", "market", "stocks", "earnings", "report",
})


@dataclass
class NewsSentimentResult:
    ticker: str
    bullish_percent: float
    bearish_percent: float
    company_news_score: float | None
    sector_avg_score: float | None
    article_count: int | None


_cache: OrderedDict[str, tuple[NewsSentimentResult | None, float]] = OrderedDict()


def _cache_get(key: str) -> NewsSentimentResult | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    value, ts = entry
    if time.monotonic() - ts > _CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return value


def _cache_put(key: str, value: NewsSentimentResult | None) -> None:
    _cache[key] = (value, time.monotonic())
    while len(_cache) > _CACHE_MAX_SIZE:
        _cache.popitem(last=False)


def is_available() -> bool:
    """yfinance has no auth — sentiment is always available unless network down."""
    return True


def _classify_headline(text: str) -> str:
    """Return 'bullish' | 'bearish' | 'neutral' for one headline+summary blob."""
    if not text:
        return "neutral"
    lowered = text.lower()
    # Token check — match on word boundaries by splitting on whitespace + punctuation
    tokens = set()
    for piece in lowered.replace(",", " ").replace(".", " ").replace(":", " ").replace(";", " ").split():
        tokens.add(piece.strip("'\""))
    bullish_hits = len(tokens & _BULLISH_KEYWORDS) + sum(
        1 for kw in _BULLISH_KEYWORDS if " " in kw and kw in lowered
    )
    bearish_hits = len(tokens & _BEARISH_KEYWORDS) + sum(
        1 for kw in _BEARISH_KEYWORDS if " " in kw and kw in lowered
    )
    if bullish_hits == bearish_hits:
        return "neutral"
    return "bullish" if bullish_hits > bearish_hits else "bearish"


def _fetch_sync(symbol: str) -> NewsSentimentResult | None:
    try:
        news_items = yf.Ticker(symbol.upper()).news
    except Exception as exc:
        logger.debug("yfinance .news failed for %s: %s", symbol, exc)
        return None
    if not news_items:
        return None

    bullish = 0
    bearish = 0
    neutral = 0
    for item in news_items:
        # yfinance v0.2+ wraps content in `content` dict, older versions are flat
        content = item.get("content") if isinstance(item, dict) else None
        if isinstance(content, dict):
            title = str(content.get("title") or "")
            summary = str(content.get("summary") or content.get("description") or "")
        else:
            title = str(item.get("title") or "") if isinstance(item, dict) else ""
            summary = str(item.get("summary") or "") if isinstance(item, dict) else ""
        verdict = _classify_headline(f"{title} {summary}")
        if verdict == "bullish":
            bullish += 1
        elif verdict == "bearish":
            bearish += 1
        else:
            neutral += 1

    total = bullish + bearish + neutral
    if total == 0:
        return None

    bullish_pct = bullish / total
    bearish_pct = bearish / total
    company_news_score = (bullish - bearish) / total if total > 0 else 0.0

    return NewsSentimentResult(
        ticker=symbol.upper(),
        bullish_percent=bullish_pct,
        bearish_percent=bearish_pct,
        company_news_score=company_news_score,
        sector_avg_score=None,
        article_count=total,
    )


async def get_sentiment(symbol: str) -> NewsSentimentResult | None:
    """Cached: fetch yfinance news for one ticker and classify by keyword.
    Returns None if no news could be fetched.
    """
    cache_key = symbol.upper()
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    result = await asyncio.to_thread(_fetch_sync, symbol)
    _cache_put(cache_key, result)
    return result


async def get_sentiment_batch(tickers: list[str]) -> dict[str, NewsSentimentResult | None]:
    """Concurrent fetch for many tickers. yfinance is rate-tolerant per-call;
    no need to chunk."""
    if not tickers:
        return {}
    tasks = [get_sentiment(t) for t in tickers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: dict[str, NewsSentimentResult | None] = {}
    for t, res in zip(tickers, results, strict=True):
        if isinstance(res, BaseException):
            out[t.upper()] = None
        else:
            out[t.upper()] = res
    return out
