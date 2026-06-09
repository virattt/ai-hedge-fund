"""yfinance-backed pricing service: period returns + SPY-relative alpha.

Provides ticker close-on-or-after-date lookup, period-return %, and
SPY-relative alpha computation. Used by:
  - watchlist 'return since added' column
  - discovery 'top-N N-day performance' column
  - whale_entry_service current-price lookup
  - discovery_backtest_service trigger-return computation

Caches each (ticker, since_date) computation for 30 min — daily closes don't
change intraday, so a short TTL covers same-day refresh without re-hitting
yfinance for every API call.

Burst protection:
  - Per-key in-flight asyncio.Lock prevents N coroutines from racing past
    the same cache miss (the "thundering herd" — what triggered yfinance
    rate-limiting before).
  - Module-level Semaphore caps concurrent yfinance calls regardless of
    cache state, smoothing bursts across pricing + relative_strength +
    revenue_acceleration + whale_entry_service callers.
"""

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import yfinance as yf

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 1800.0
_CACHE_MAX_SIZE = 500
_SPY_TICKER = "SPY"
_MAX_CONCURRENT_YFINANCE_CALLS = 2
_RATE_LIMIT_RETRY_DELAY_S = 5.0
_GLOBAL_COOLDOWN_SECONDS = 60.0


class _RateLimited(Exception):
    """yfinance returned 'Too Many Requests' — transient, do not cache the failure."""


_yfinance_semaphore: asyncio.Semaphore = asyncio.Semaphore(_MAX_CONCURRENT_YFINANCE_CALLS)
_inflight_locks: dict[tuple[str, str], asyncio.Lock] = {}

# Circuit breaker: when yfinance starts throttling, every subsequent call
# returns None immediately for _GLOBAL_COOLDOWN_SECONDS rather than queuing
# more requests that just extend the throttle. The current cache continues
# to serve existing entries; only new fetches short-circuit.
_yfinance_cooldown_until: float = 0.0


def _is_in_cooldown() -> bool:
    return time.monotonic() < _yfinance_cooldown_until


def _trigger_cooldown() -> None:
    global _yfinance_cooldown_until
    _yfinance_cooldown_until = time.monotonic() + _GLOBAL_COOLDOWN_SECONDS
    logger.warning(
        "pricing_service: yfinance rate-limited globally — circuit breaker engaged for %.0fs",
        _GLOBAL_COOLDOWN_SECONDS,
    )


def _is_rate_limit_message(text: str) -> bool:
    lower = text.lower()
    return "too many requests" in lower or "rate limit" in lower


@dataclass
class PeriodReturn:
    """Two-endpoint price snapshot used to compute return %."""
    start_date: str
    start_price: float
    end_date: str
    end_price: float


@dataclass
class AlphaMetrics:
    """Period-return + SPY alpha for a single ticker."""
    ticker: str
    period_return_pct: float
    spy_return_pct: float
    alpha_pct: float
    start_date: str
    end_date: str
    start_price: float
    end_price: float


_period_cache: OrderedDict[tuple[str, str], tuple[PeriodReturn | None, float]] = OrderedDict()


def _cache_get(key: tuple[str, str]) -> PeriodReturn | None:
    entry = _period_cache.get(key)
    if entry is None:
        return None
    value, ts = entry
    if time.monotonic() - ts > _CACHE_TTL_SECONDS:
        _period_cache.pop(key, None)
        return None
    return value


def _cache_put(key: tuple[str, str], value: PeriodReturn | None) -> None:
    _period_cache[key] = (value, time.monotonic())
    while len(_period_cache) > _CACHE_MAX_SIZE:
        _period_cache.popitem(last=False)


def _coerce_since(since: date | datetime | str) -> date:
    if isinstance(since, datetime):
        return since.astimezone(timezone.utc).date() if since.tzinfo else since.date()
    if isinstance(since, date):
        return since
    if isinstance(since, str):
        return date.fromisoformat(since.split("T")[0])
    raise TypeError(f"Unsupported since type: {type(since).__name__}")


def _fetch_period_sync(ticker: str, since: date) -> PeriodReturn | None:
    """Synchronous yfinance fetch. Raises _RateLimited on transient throttling
    (caller decides whether to retry / skip caching); returns None for any
    other failure mode (delisted, malformed data, network)."""
    end = date.today() + timedelta(days=1)
    if since >= end:
        return None
    try:
        history = yf.Ticker(ticker).history(start=since, end=end, auto_adjust=True)
    except Exception as exc:
        msg = str(exc)
        if _is_rate_limit_message(msg):
            raise _RateLimited(msg) from exc
        logger.warning("pricing_service yfinance failed for %s: %s", ticker, exc)
        return None
    if history is None or history.empty:
        return None
    first_idx = history.index[0]
    last_idx = history.index[-1]
    try:
        start_close = float(history.iloc[0]["Close"])
        end_close = float(history.iloc[-1]["Close"])
    except (KeyError, ValueError, TypeError):
        return None
    if start_close <= 0 or end_close <= 0:
        return None
    return PeriodReturn(
        start_date=first_idx.strftime("%Y-%m-%d"),
        start_price=start_close,
        end_date=last_idx.strftime("%Y-%m-%d"),
        end_price=end_close,
    )


async def get_period_return(ticker: str, since: date | datetime | str) -> PeriodReturn | None:
    """Cached: fetch the close on/after `since` and the latest close.

    Returns None on delisted ticker, future date, or network failure.

    Per-key in-flight lock prevents the thundering-herd burst: when N
    coroutines ask for the same (ticker, since) simultaneously, only one
    hits yfinance — the rest await and read from cache.
    """
    since_d = _coerce_since(since)
    cache_key = (ticker.upper(), since_d.isoformat())
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if _is_in_cooldown():
        # Yfinance is currently throttling us — short-circuit without making
        # the request, return None so callers degrade gracefully. Cache
        # entries written before cooldown remain valid.
        return None

    lock = _inflight_locks.setdefault(cache_key, asyncio.Lock())
    async with lock:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached
        if _is_in_cooldown():
            return None
        async with _yfinance_semaphore:
            try:
                result = await asyncio.to_thread(_fetch_period_sync, ticker.upper(), since_d)
            except _RateLimited as exc:
                logger.info(
                    "pricing_service: rate-limited on %s, backing off %.1fs and retrying once",
                    ticker, _RATE_LIMIT_RETRY_DELAY_S,
                )
                await asyncio.sleep(_RATE_LIMIT_RETRY_DELAY_S)
                try:
                    result = await asyncio.to_thread(_fetch_period_sync, ticker.upper(), since_d)
                except _RateLimited:
                    _trigger_cooldown()
                    return None
        _cache_put(cache_key, result)
        return result


async def compute_alpha(ticker: str, since: date | datetime | str) -> AlphaMetrics | None:
    """Compute period return + SPY-relative alpha for one ticker.

    Serial (SPY first, then ticker) rather than parallel: SPY is shared
    across all callers, so a sequential pattern hits the SPY cache after
    the first request and never gets duplicated work.
    """
    since_d = _coerce_since(since)
    spy_data = await get_period_return(_SPY_TICKER, since_d)
    ticker_data = await get_period_return(ticker, since_d)
    if ticker_data is None or spy_data is None:
        return None

    ticker_return_pct = (ticker_data.end_price / ticker_data.start_price - 1.0) * 100.0
    spy_return_pct = (spy_data.end_price / spy_data.start_price - 1.0) * 100.0
    return AlphaMetrics(
        ticker=ticker.upper(),
        period_return_pct=ticker_return_pct,
        spy_return_pct=spy_return_pct,
        alpha_pct=ticker_return_pct - spy_return_pct,
        start_date=ticker_data.start_date,
        end_date=ticker_data.end_date,
        start_price=ticker_data.start_price,
        end_price=ticker_data.end_price,
    )


async def compute_alpha_batch(items: list[tuple[str, date | datetime | str]]) -> dict[str, AlphaMetrics | None]:
    """Compute alpha for many (ticker, since) pairs concurrently.

    Pre-warms the SPY cache once per unique since_date before fanning out
    ticker fetches. Without this, N coroutines each fire their own SPY
    request before the first one populates the cache — the textbook
    thundering-herd pattern that trips yfinance rate-limiting.
    """
    if not items:
        return {}
    unique_dates = {_coerce_since(s).isoformat() for _, s in items}
    for iso in unique_dates:
        await get_period_return(_SPY_TICKER, iso)

    tasks = [compute_alpha(t, s) for t, s in items]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: dict[str, AlphaMetrics | None] = {}
    for (ticker, _since), res in zip(items, results, strict=True):
        if isinstance(res, BaseException):
            logger.debug("pricing_service: alpha compute failed for %s: %s", ticker, res)
            out[ticker.upper()] = None
        else:
            out[ticker.upper()] = res
    return out
