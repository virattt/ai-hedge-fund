# Milestone 1: Web Scraping for Full-Text News

**Goal:** Scrape full article text via Crawl4AI so the news sentiment agent gets richer context than just headlines.

**Risk:** Low — additive change, gated behind env var, falls back to headline-only on failure.

## Tasks

- [ ] Add `crawl4ai` to `pyproject.toml`
- [ ] Create `src/tools/scraper.py` with `scrape_article_text(url) -> str | None`
  - Use Crawl4AI for extraction
  - Timeout handling (default 10s)
  - Text truncation (~2000 chars)
  - Return None on any failure
- [ ] Add article text cache to `src/data/cache.py`
  - Add `_article_text_cache` dict
  - Add `get_article_text()` / `set_article_text()` methods
  - Same pattern as existing 5 caches
- [ ] Update `src/agents/news_sentiment.py` to use scraped text
  - In the analysis loop (lines 71-84): attempt `scrape_article_text(news.url)`
  - If available, change prompt to include article excerpt
  - Fall back to headline-only on failure
  - Gate behind `SCRAPE_FULL_TEXT` env var (default false)
- [ ] Write tests in `tests/test_scraper.py`
  - Mock Crawl4AI responses
  - Test timeout handling
  - Test text truncation
  - Test cache hit/miss
- [ ] Integration test: run with `SCRAPE_FULL_TEXT=true poetry run python src/main.py --ticker AAPL`
  - News sentiment reasoning should show richer context
  - All existing tests pass with default (false)

## Files

| Action | File |
|--------|------|
| Create | `src/tools/scraper.py` |
| Create | `tests/test_scraper.py` |
| Modify | `pyproject.toml` |
| Modify | `src/data/cache.py` |
| Modify | `src/agents/news_sentiment.py` |
