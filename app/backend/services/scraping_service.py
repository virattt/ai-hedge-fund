"""Scraping service: Crawl4AI integration with concurrency limiting, timeout, content truncation, and data retention.

Implements manual BFS deep crawling by extracting links from each crawl result
and visiting them level-by-level, compatible with crawl4ai >=0.4.
"""
import asyncio
import logging
import traceback
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler
from crawl4ai.models import CrawlResult, MarkdownGenerationResult

from app.backend.database.connection import SessionLocal
from app.backend.models.schemas import ScrapeResultStatus, ScrapeStatus
from app.backend.repositories.scraping_repository import ScrapingRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CONTENT_LENGTH: int = 1_048_576  # 1 MB – stored content truncation limit
MAX_RESULTS_PER_WEBSITE: int = 50  # data retention: keep only most recent N results
SCRAPE_TIMEOUT_SECONDS: int = 60  # asyncio.wait_for timeout per page
MAX_CONCURRENT_SCRAPES: int = 3  # semaphore limit for concurrent scrapes
MAX_TIMEOUT_SECONDS: int = 300  # hard cap on total scrape time

# Module-level semaphore shared by the scheduler and on-demand triggers
_scrape_semaphore: asyncio.Semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCRAPES)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass
class TruncatedContent:
    """Result of truncating page content to the storage limit."""
    text: str | None
    original_byte_length: int


def _log(msg: str) -> None:
    """Log to both Python logger and stdout for guaranteed console visibility."""
    logger.info(msg)
    print(f"[SCRAPER] {msg}", flush=True)


def _log_error(msg: str) -> None:
    """Log error to both Python logger and stderr for guaranteed console visibility."""
    logger.error(msg)
    print(f"[SCRAPER ERROR] {msg}", flush=True)


def _truncate_content(raw: str | None) -> TruncatedContent:
    """Return possibly-truncated content with its original byte length."""
    if not raw:
        return TruncatedContent(text=raw, original_byte_length=0)
    original_length = len(raw.encode("utf-8"))
    text = raw
    if original_length > MAX_CONTENT_LENGTH:
        text = raw[:MAX_CONTENT_LENGTH]
        _log(f"  Truncated content from {original_length} to {MAX_CONTENT_LENGTH} bytes")
    return TruncatedContent(text=text, original_byte_length=original_length)


def _extract_links(crawl_result: CrawlResult, base_url: str, include_external: bool) -> list[str]:
    """Extract navigable links from a crawl result's links dict.

    crawl_result.links is {"internal": [...], "external": [...]},
    where each entry has an "href" key.
    """
    links_dict: dict[str, list[dict]] | None = crawl_result.links
    if not links_dict:
        return []

    urls: list[str] = []

    for link_entry in links_dict.get("internal", []):
        href = link_entry.get("href", "") if isinstance(link_entry, dict) else ""
        if href:
            absolute = urljoin(base_url, href)
            urls.append(absolute)

    if include_external:
        for link_entry in links_dict.get("external", []):
            href = link_entry.get("href", "") if isinstance(link_entry, dict) else ""
            if href:
                absolute = urljoin(base_url, href)
                urls.append(absolute)

    # Deduplicate while preserving order, strip fragments
    seen: set[str] = set()
    clean: list[str] = []
    for u in urls:
        normalized = u.split("#")[0].rstrip("/")
        if normalized and normalized not in seen:
            seen.add(normalized)
            clean.append(normalized)
    return clean


def _get_markdown_text(crawl_result: CrawlResult) -> str | None:
    """Extract markdown text from a CrawlResult, handling both str and MarkdownGenerationResult."""
    raw = crawl_result.markdown
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    if isinstance(raw, MarkdownGenerationResult):
        return raw.raw_markdown
    return str(raw)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def execute_scrape(website_id: int) -> None:
    """Scrape a website and persist the result.

    When max_depth > 1, performs manual BFS crawling: scrapes the root page,
    extracts links, then visits discovered URLs level-by-level up to max_depth,
    capped at max_pages total pages.
    """
    async with _scrape_semaphore:
        session = SessionLocal()
        try:
            repo = ScrapingRepository(session)
            website = repo.get_website_by_id(website_id)
            if website is None:
                _log_error(f"Website {website_id} not found; skipping")
                return

            if website.scrape_status != ScrapeStatus.IN_PROGRESS:
                repo.update_website_status(website_id, ScrapeStatus.IN_PROGRESS)
            _log(f"--- Starting scrape for website {website_id}: {website.url} ---")

            scrape_run_id = str(uuid.uuid4())
            max_depth: int = website.max_depth
            max_pages: int = website.max_pages
            include_external: bool = website.include_external

            # Total timeout for entire crawl
            total_timeout = min(SCRAPE_TIMEOUT_SECONDS * min(max_pages, 10), MAX_TIMEOUT_SECONDS)

            success = False
            error_message: str | None = None

            try:
                _log(f"  Launching browser for {website.url} (depth={max_depth}, max_pages={max_pages})...")

                async with AsyncWebCrawler() as crawler:
                    _log("  Browser launched. Fetching page(s)...")

                    # BFS state
                    # Each entry: (url, depth, parent_url)
                    queue: deque[tuple[str, int, str | None]] = deque()
                    queue.append((website.url, 0, None))
                    visited: set[str] = set()
                    url_to_result_id: dict[str, int] = {}
                    pages_crawled = 0
                    any_success = False

                    deadline = asyncio.get_event_loop().time() + total_timeout

                    while queue and pages_crawled < max_pages:
                        page_url, depth, parent_url = queue.popleft()

                        # Normalize for dedup
                        normalized = page_url.split("#")[0].rstrip("/")
                        if normalized in visited:
                            continue
                        visited.add(normalized)

                        # Check total timeout
                        remaining = deadline - asyncio.get_event_loop().time()
                        if remaining <= 0:
                            _log_error(f"  Total timeout reached after {pages_crawled} pages")
                            break

                        per_page_timeout = min(SCRAPE_TIMEOUT_SECONDS, remaining)

                        try:
                            crawl_result: CrawlResult = await asyncio.wait_for(
                                crawler.arun(url=page_url),
                                timeout=per_page_timeout,
                            )
                        except asyncio.TimeoutError:
                            _log_error(f"  Page timeout: {page_url}")
                            repo.create_scrape_result(
                                website_id=website_id, content=None, content_length=0,
                                status=ScrapeResultStatus.ERROR, error_message=f"Page timed out after {per_page_timeout:.0f}s",
                                page_url=page_url, depth=depth,
                                parent_result_id=url_to_result_id.get(parent_url) if parent_url else None,
                                scrape_run_id=scrape_run_id,
                            )
                            pages_crawled += 1
                            continue

                        parent_result_id = url_to_result_id.get(parent_url) if parent_url else None

                        if not crawl_result.success:
                            page_error = f"Crawl4AI returned success=False, status={crawl_result.status_code}"
                            if crawl_result.error_message:
                                page_error += f": {crawl_result.error_message}"
                            _log_error(f"  Page {page_url}: {page_error}")
                            db_result = repo.create_scrape_result(
                                website_id=website_id, content=None, content_length=0,
                                status=ScrapeResultStatus.ERROR, error_message=page_error,
                                page_url=page_url, depth=depth,
                                parent_result_id=parent_result_id, scrape_run_id=scrape_run_id,
                            )
                        else:
                            raw_markdown = _get_markdown_text(crawl_result)
                            tc = _truncate_content(raw_markdown)
                            _log(f"  Page {page_url}: {tc.original_byte_length} bytes (depth={depth})")
                            db_result = repo.create_scrape_result(
                                website_id=website_id, content=tc.text, content_length=tc.original_byte_length,
                                status=ScrapeResultStatus.SUCCESS,
                                page_url=page_url, depth=depth,
                                parent_result_id=parent_result_id, scrape_run_id=scrape_run_id,
                            )
                            any_success = True

                            # Discover child links for BFS (only if we haven't reached max depth)
                            if depth < max_depth - 1:
                                child_links = _extract_links(crawl_result, page_url, include_external)
                                for link in child_links:
                                    link_normalized = link.split("#")[0].rstrip("/")
                                    if link_normalized not in visited:
                                        queue.append((link, depth + 1, page_url))

                        url_to_result_id[page_url] = db_result.id
                        pages_crawled += 1

                    _log(f"  Crawled {pages_crawled} page(s) total")
                    success = any_success

            except asyncio.TimeoutError:
                error_message = f"Scrape timed out after {total_timeout} seconds"
                _log_error(f"  TIMEOUT for website {website_id} after {total_timeout}s")
            except Exception as exc:
                error_message = str(exc)
                _log_error(f"  EXCEPTION for website {website_id}: {exc}")
                _log_error(f"  Traceback:\n{traceback.format_exc()}")
                if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc).lower():
                    _log_error("  >>> FIX: Run 'playwright install chromium' to download the browser <<<")

            if success:
                repo.update_website_status(website_id, ScrapeStatus.IDLE, last_scraped_at=datetime.now(timezone.utc))
                repo.cleanup_old_results(website_id, keep=MAX_RESULTS_PER_WEBSITE)
                _log(f"--- Scrape complete for website {website_id}: SUCCESS (run={scrape_run_id}) ---")
            else:
                if error_message:
                    repo.create_scrape_result(
                        website_id=website_id, content=None, content_length=0,
                        status=ScrapeResultStatus.ERROR, error_message=error_message,
                        page_url=website.url, depth=0, scrape_run_id=scrape_run_id,
                    )
                repo.update_website_status(website_id, ScrapeStatus.ERROR, last_error=error_message)
                _log_error(f"--- Scrape complete for website {website_id}: FAILED ({error_message}) ---")
        finally:
            session.close()
