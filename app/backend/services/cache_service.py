"""Cache flush registry.

Owns the canonical list of every in-memory cache across the platform and
provides one-call flush. Each entry imports the target module's cache
reference, records its size, then clears it.

Adding a new cache:
1. Add the module + cache attribute to `_REGISTRY`.
2. Hot-reload the backend; the new entry is included automatically.

This is used by the `POST /cache/flush` endpoint and the Settings UI button.
"""

import asyncio
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import import_module

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _CacheRef:
    """Identifies one cache: module path + attribute name + display label."""
    module: str
    attr: str
    label: str


@dataclass(frozen=True)
class _FlushResult:
    """Outcome of clearing one cache: human label + entry count removed."""
    label: str
    cleared: int


_REGISTRY: tuple[_CacheRef, ...] = (
    _CacheRef("app.backend.services.pricing_service", "_period_cache", "pricing"),
    _CacheRef("app.backend.services.pricing_service", "_inflight_locks", "pricing_inflight_locks"),
    _CacheRef("app.backend.services.fundamentals_service._metrics", "_cache", "company_metrics"),
    _CacheRef("app.backend.services.fundamentals_service._revenue", "_cache", "revenue_growth"),
    _CacheRef("app.backend.services.fundamentals_service._roic", "_cache", "roic_history"),
    _CacheRef("app.backend.services.news_sentiment_service", "_cache", "news_sentiment"),
    _CacheRef("app.backend.services.openinsider_service", "_oi_cache", "openinsider"),
    _CacheRef("app.backend.services.finnhub_service", "_cache", "finnhub"),
    _CacheRef("app.backend.services.earnings_calendar_service", "_cache", "earnings_calendar"),
    _CacheRef("app.backend.services.earnings_service", "_cache", "earnings_transcripts"),
    _CacheRef("app.backend.services.catalyst_service", "_cache", "catalysts"),
    _CacheRef("app.backend.services.political_service", "_cache", "political"),
    _CacheRef("app.backend.services.news_service", "_article_cache", "news_articles"),
    _CacheRef("app.backend.services.insider_service", "_insider_cache", "insider"),
    _CacheRef("app.backend.services.discovery_service._sources.commodity_tailwind", "_series_cache", "commodity_tailwind"),
)


def _module_attr(module_path: str, attr: str) -> object | None:
    """Look up an attribute on a dynamically-imported module via __dict__.

    Resolving via __dict__ rather than direct attribute access keeps the
    cache registry authoritative — service modules never declare a static
    contract here, and the registry's `_CacheRef` rows are the only thing
    naming these attributes by string.
    """
    try:
        module = import_module(module_path)
    except ImportError as exc:
        logger.warning("cache flush: cannot import %s: %s", module_path, exc)
        return None
    return module.__dict__.get(attr)


def _clear_container(container: object) -> int:
    """Empty whatever container shape we got. Returns entries removed."""
    if isinstance(container, dict):
        size = len(container)
        container.clear()
        return size
    if isinstance(container, list):
        size = len(container)
        container.clear()
        return size
    if isinstance(container, set):
        size = len(container)
        container.clear()
        return size
    return 0


def _flush_activist_13d_module() -> _FlushResult:
    """The activist_13d source uses two coupled module globals (_cache list +
    _cache_ts timestamp) instead of an OrderedDict, so it needs a custom reset.
    """
    module_path = "app.backend.services.discovery_service._sources.activist_13d"
    try:
        module = import_module(module_path)
    except ImportError:
        return _FlushResult("activist_13d", 0)
    cache_list = module.__dict__.get("_cache")
    cleared = len(cache_list) if isinstance(cache_list, list) else 0
    module.__dict__["_cache"] = None
    module.__dict__["_cache_ts"] = 0.0
    return _FlushResult("activist_13d", cleared)


def _flush_inflight_refreshes() -> _FlushResult:
    """Cancel any in-flight Discovery refreshes so a flushed cache forces a
    cold compute on the next request rather than reusing in-progress work.
    """
    inflight = _module_attr("app.backend.services.discovery_service", "_inflight_refreshes")
    if not isinstance(inflight, dict):
        return _FlushResult("discovery_inflight", 0)
    cancelled = 0
    for task in list(inflight.values()):
        if isinstance(task, asyncio.Task) and not task.done():
            task.cancel()
            cancelled += 1
    inflight.clear()
    return _FlushResult("discovery_inflight", cancelled)


def _reset_yfinance_cooldown() -> _FlushResult:
    """Clear the pricing-service rate-limit cooldown so the next call retries
    yfinance immediately rather than waiting for the cooldown window."""
    try:
        module = import_module("app.backend.services.pricing_service")
    except ImportError:
        return _FlushResult("yfinance_cooldown", 0)
    cooldown = module.__dict__.get("_yfinance_cooldown_until", 0.0)
    was_active = isinstance(cooldown, (int, float)) and cooldown > time.monotonic()
    module.__dict__["_yfinance_cooldown_until"] = 0.0
    return _FlushResult("yfinance_cooldown", 1 if was_active else 0)


def flush_all() -> dict[str, int]:
    """Clear every registered cache. Returns {label: entries_cleared}.

    Discovery itself no longer caches, so the next page load will compute
    fresh against now-clean fundamentals/pricing/news caches.
    """
    cleared: dict[str, int] = {}

    for ref in _REGISTRY:
        container = _module_attr(ref.module, ref.attr)
        if container is None:
            cleared[ref.label] = 0
            continue
        try:
            cleared[ref.label] = _clear_container(container)
        except Exception as exc:
            logger.warning("cache flush: failed to clear %s: %s", ref.label, exc)
            cleared[ref.label] = 0

    for fn in (_flush_activist_13d_module, _flush_inflight_refreshes, _reset_yfinance_cooldown):
        result = fn()
        cleared[result.label] = result.cleared

    total = sum(cleared.values())
    logger.info("Cache flush complete: %d total entries cleared across %d caches", total, len(cleared))
    return cleared


def list_caches() -> Iterable[str]:
    """Return labels of every cache the registry knows about."""
    labels = [ref.label for ref in _REGISTRY]
    labels.extend(["activist_13d", "discovery_inflight", "yfinance_cooldown"])
    return labels
