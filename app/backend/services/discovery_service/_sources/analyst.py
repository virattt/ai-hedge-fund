"""Discovery source: analyst recommendation upgrades (Wall Street consensus shift).

Enrichment-only: queries Finnhub `/stock/recommendation` for tickers in the
user's watchlist. For each, computes net change in (strongBuy + buy) between
the most recent and prior monthly snapshot. Positive shift = bullish consensus.

Score:
  - 15 if net upgrade shift > 0
  - 25 if net upgrade shift >= 3 (strong consensus move)

Universe = watchlist only for v1. Avoids API budget bloat and circular
dependency risk (analyst can't trigger sources that re-trigger analyst).
"""

import logging
import os

import httpx

from app.backend.database import SessionLocal
from app.backend.database.models import WatchlistItem
from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)

_FINNHUB_BASE = "https://finnhub.io/api/v1"
_PLACEHOLDER_PREFIXES = ("your-", "placeholder", "change-me", "sk-xxx")
_BIG_SHIFT = 3
_MAX_TICKERS = 100


def _real_finnhub_key() -> str | None:
    key = os.environ.get("FINNHUB_API_KEY", "").strip()
    if not key:
        return None
    if any(key.lower().startswith(p) for p in _PLACEHOLDER_PREFIXES):
        return None
    return key


def _build_universe() -> list[str]:
    """Watchlist tickers only (v1). Bounded universe = predictable API budget."""
    db = SessionLocal()
    try:
        rows = db.query(WatchlistItem.ticker).all()
    finally:
        db.close()
    universe = sorted({row[0].upper() for row in rows if row[0]})
    return universe[:_MAX_TICKERS]


async def _fetch_recommendation_shift(client: httpx.AsyncClient, ticker: str, key: str) -> int | None:
    """Return net (strongBuy + buy) change: latest period - prior period.

    Returns None if no data, < 2 snapshots, or fetch error.
    """
    url = f"{_FINNHUB_BASE}/stock/recommendation"
    try:
        resp = await client.get(url, params={"symbol": ticker, "token": key})
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception:
        return None
    if not isinstance(data, list) or len(data) < 2:
        return None
    latest, prior = data[0], data[1]
    latest_buys = (latest.get("strongBuy") or 0) + (latest.get("buy") or 0)
    prior_buys = (prior.get("strongBuy") or 0) + (prior.get("buy") or 0)
    return latest_buys - prior_buys


async def fetch() -> list[tuple[str, IdeaSignal]]:
    key = _real_finnhub_key()
    if not key:
        logger.info("analyst source: FINNHUB_API_KEY not configured, skipping")
        return []

    universe = _build_universe()
    if not universe:
        return []  # empty watchlist — nothing to enrich

    out: list[tuple[str, IdeaSignal]] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for ticker in universe:
            shift = await _fetch_recommendation_shift(client, ticker, key)
            if shift is None or shift <= 0:
                continue

            score = 25.0 if shift >= _BIG_SHIFT else 15.0
            plural = "" if shift == 1 else "s"
            out.append((ticker, IdeaSignal(
                source="analyst",
                score=score,
                label=f"+{shift} net analyst upgrade{plural} (vs prior month)",
                detail={"ticker": ticker, "net_shift": shift},
            )))
    return out
