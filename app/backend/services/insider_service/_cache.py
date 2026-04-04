"""LRU+TTL in-process cache shared across all insider service endpoints."""
import time
from collections import OrderedDict

# Values are (response_object, monotonic_timestamp).
_insider_cache: OrderedDict[str, tuple[object, float]] = OrderedDict()
_CACHE_TTL_SECONDS: float = 300.0  # 5 minutes
_CACHE_MAX_SIZE: int = 50


def _cache_get(cache_key: str) -> object | None:
    """Return cached response if present and not expired, else None.

    Evicts the entry when it has expired.
    """
    entry = _insider_cache.get(cache_key)
    if entry is None:
        return None
    response, timestamp = entry
    if time.monotonic() - timestamp > _CACHE_TTL_SECONDS:
        _insider_cache.pop(cache_key, None)
        return None
    return response


def _cache_put(cache_key: str, response: object) -> None:
    """Store response with current timestamp. Evicts oldest entry if over max size."""
    _insider_cache[cache_key] = (response, time.monotonic())
    while len(_insider_cache) > _CACHE_MAX_SIZE:
        _insider_cache.popitem(last=False)
