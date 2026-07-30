"""Web scraping helpers backed by Firecrawl (https://docs.firecrawl.dev).

News APIs give us headlines and a link, but not the article body.  Firecrawl turns
a URL into clean markdown, which lets agents reason about what an article actually
says instead of guessing from its headline.
"""

import logging
import os
import time
from collections import OrderedDict

from firecrawl import Firecrawl

logger = logging.getLogger(__name__)

# Articles are fed into LLM prompts, so cap how much text we keep per article.
DEFAULT_MAX_CHARS = 4000

# Deadline for the scrape job itself, in milliseconds (the API default is 60s), with the
# client HTTP timeout just above it.  That way the server reports its own timeout instead
# of the client abandoning - and the SDK retrying - a job that is still running.
SCRAPE_TIMEOUT_MS = 20_000
REQUEST_TIMEOUT_SECONDS = 25

# Successful scrapes, bounded and short-lived: enough to avoid scraping the same article
# twice in a run, not so long that a corrected article is served forever.  Failures are
# deliberately not cached, so a transient error does not sideline a URL.
CACHE_MAX_ENTRIES = 256
CACHE_TTL_SECONDS = 3600
_article_cache: OrderedDict[str, tuple[float, str]] = OrderedDict()


def scrape_article_text(url: str, api_key: str = None, max_chars: int = DEFAULT_MAX_CHARS) -> str | None:
    """Scrape an article and return its text as markdown, truncated to `max_chars`.

    Returns None when no Firecrawl API key is configured or the scrape fails, so
    callers can fall back to whatever data they already have (e.g. the headline).
    """
    firecrawl_api_key = api_key or os.environ.get("FIRECRAWL_API_KEY")
    if not firecrawl_api_key:
        return None

    markdown = _scrape_markdown(url, firecrawl_api_key)
    if not markdown:
        return None

    return markdown[:max_chars]


def _scrape_markdown(url: str, api_key: str) -> str | None:
    """Scrape a single URL to markdown, caching successful scrapes."""
    cached = _cache_get(url)
    if cached is not None:
        return cached

    try:
        client = Firecrawl(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS)
        document = client.scrape(url, formats=["markdown"], timeout=SCRAPE_TIMEOUT_MS)
    except Exception as e:
        logger.warning("Failed to scrape article %s: %s", url, e)
        return None

    if document.markdown:
        _cache_set(url, document.markdown)

    return document.markdown


def _cache_get(url: str) -> str | None:
    """Return the cached markdown for a URL, unless it has gone stale."""
    entry = _article_cache.get(url)
    if entry is None:
        return None

    cached_at, markdown = entry
    if time.monotonic() - cached_at > CACHE_TTL_SECONDS:
        del _article_cache[url]
        return None

    _article_cache.move_to_end(url)
    return markdown


def _cache_set(url: str, markdown: str) -> None:
    """Cache the markdown for a URL, evicting the least recently used entry if full."""
    _article_cache[url] = (time.monotonic(), markdown)
    _article_cache.move_to_end(url)
    if len(_article_cache) > CACHE_MAX_ENTRIES:
        _article_cache.popitem(last=False)
