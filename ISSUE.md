```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║     ██╗███████╗███████╗██╗   ██╗███████╗                                      ║
║     ██║██╔════╝██╔════╝██║   ██║██╔════╝                                      ║
║     ██║███████╗███████╗██║   ██║█████╗                                        ║
║     ██║╚════██║╚════██║██║   ██║██╔══╝                                        ║
║     ██║███████║███████║╚██████╔╝███████╗                                      ║
║     ╚═╝╚══════╝╚══════╝ ╚═════╝ ╚══════╝                                      ║
║                                                                               ║
║     Precision.  No noise.  Just the signal.                                   ║
║                                                                               ║
║     Known issues.  Fixes applied.  Runbook recorded.                          ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

## Fork Sync Strategy (Upstream vs Our Fork)

### Summary

This project is a fork of `virattt/ai-hedge-fund`. GitHub shows us as “N commits ahead, M commits behind” and occasionally offers a scary **“Discard X commits”** button. We never want to discard our work; instead, we treat the upstream repo as the source of truth and **regularly merge/rebase `upstream/main` into our own `main` (and feature branches)**.

### Recommended workflow

#### 1. Add upstream remote (one-time)

From the repo root:

```bash
git remote add upstream https://github.com/virattt/ai-hedge-fund.git   # or SSH URL
git fetch upstream
```

Now:

- `origin/main` = our fork on GitHub  
- `upstream/main` = original repository

#### 2. Keep `main` aligned with upstream

On a regular basis:

```bash
git checkout main
git fetch upstream
git merge upstream/main        # or: git rebase upstream/main
```

- If there are **no conflicts**, `main` fast-forwards and we’re no longer “behind” upstream.
- If there **are conflicts**, resolve them locally in the files Git reports, run tests, then commit the merge.

> **Never** use the “Discard X commits” button on GitHub to sync. That would throw away our local work. Always sync via `merge`/`rebase` from `upstream/main`.

#### 3. Do new work on feature branches

For non-trivial changes:

```bash
git checkout main
git pull upstream main          # ensure main is fresh
git checkout -b feature/my-change
# ... edits, commits ...
```

When upstream moves:

```bash
git fetch upstream
git rebase upstream/main        # from feature branch
```

Resolve any conflicts once, then:

```bash
git push origin feature/my-change  # add --force-with-lease if rebased
```

We can then open PRs from our feature branches into our own `main` (or upstream if contributing back) with clean, linear history.

---

## Autoresearch full-signal cache fails with sentiment parsing + OpenAI quota errors

### Summary (Status: **Resolved**)

Running the optional **full 18‑agent signal cache** via `autoresearch.cache_signals` appears to:

- Run for a long time (tens of minutes) and
- Emit repeated LLM output parsing errors from the sentiment pipeline and then
- Hit OpenAI `429 insufficient_quota` errors,

after which `autoresearch/cache/meta.json` still shows `"has_signals": false`.

### Reproduction

From the repo root (`ai-hedge-fund`):

```bash
poetry run python -m autoresearch.cache_signals \
  --tickers AAPL,NVDA,MSFT,GOOGL,TSLA \
  --start 2025-06-01 --end 2025-12-01 \
  --model gpt-4.1 --provider OpenAI
```

Environment (user side):

- Free test tickers only (AAPL, NVDA, MSFT, GOOGL, TSLA)
- OpenAI API key configured in `.env`
- `autoresearch/cache/prices.json` and `meta.json` already exist from prior runs

### Observed behavior

1. `autoresearch.cache_signals` runs for a long time while agents fetch data.
2. Terminal repeatedly shows **sentiment parsing errors**, e.g.:

   - `Error in LLM call after 3 attempts: Failed to parse Sentiment from completion {"error": "No headline provided. Please provide a news headline for analysis."}.`
   - Pydantic errors like:
     - `Field required [type=missing, input_value={'error': 'No headline provided...'}, input_type=dict]` for `sentiment` and `confidence`.
   - LangChain troubleshooting link: `OUTPUT_PARSING_FAILURE`.

3. After many such retries, calls begin failing with **OpenAI quota errors**:

   - `Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details.', 'type': 'insufficient_quota', ...}}`

4. The process keeps logging these 429 errors and retrying, but never cleanly completes the full-signal cache.
5. After stopping the run, `autoresearch/cache/meta.json` still contains:

   ```json
   {
     "tickers": ["AAPL", "NVDA", "MSFT", "GOOGL", "TSLA"],
     "start_date": "2025-06-01",
     "end_date": "2025-12-01",
     "model": "gpt-4.1",
     "provider": "OpenAI",
     "has_signals": false
   }
   ```

### Expected behavior

- If the LLM output for sentiment is malformed (e.g., returns an `"error"` object instead of `{sentiment, confidence}`), the pipeline should:
  - Either fall back gracefully (e.g., skip that day / news item with a warning) or
  - Fail fast with a clear error, rather than endlessly retrying.
- When OpenAI returns `429 insufficient_quota`, the cache job should:
  - Detect quota exhaustion,
  - Abort the run with a clear message, and
  - Avoid spinning on repeated retries that will never succeed.
- On success, `meta.json` should flip to `"has_signals": true` so `autoresearch.evaluate` can safely assume the full-signal cache is present.

### Impact

- The optional full 18‑agent signal cache is effectively unusable on a low / exhausted OpenAI quota:
  - Very long runtime with repeated parsing failures,
  - Followed by quota errors and no completed signal cache.
- Users can still run **Mode 1 (technical-only / prices-only)** autoresearch successfully, but cannot currently get a clean **Mode 2 (full-signal)** cache in this state.

### Suggested improvements

1. **Robust sentiment output schema handling**
   - Accept either:
     - `{ "sentiment": "...", "confidence": ... }` or
     - `{ "sentiment": "...", "confidence_score": ... }`, and map `confidence_score → confidence`.
   - If the model returns an `"error"` object instead, treat it as a soft failure:
     - Log once per date/ticker,
     - Skip that sample with a default neutral/low-confidence sentiment, and
     - Avoid triple‑retry loops that cannot succeed.

2. **Quota-aware retry / abort logic**
   - Detect `429` with `type: "insufficient_quota"` and:
     - Stop the cache job early with a clear message like:  
       `"OpenAI quota exhausted during cache_signals; signals cache incomplete (has_signals=false)."`
     - Optionally write a partial/meta status indicating which tickers/dates completed.

3. **Better progress and completion markers**
   - Only set `meta["has_signals"] = true` once all tickers × dates × agents have successfully written signals.
   - Consider writing intermediate progress (e.g., per-ticker or per-date ranges) so users can see how far the cache got before failure.

4. **Docs hint**
   - In `README.md` / `autoresearch/README.md`, explicitly note that:
     - Full-signal caching can be expensive and quota-heavy,
     - Mode 1 (prices-only) is the recommended first step, and
     - If `cache_signals` starts throwing 429 / OUTPUT_PARSING_FAILURE errors, users should switch back to prices-only mode until quota or provider issues are resolved.

---

### Fix applied

**Root cause of sentiment parsing errors:** `src/data/providers/yfinance_provider.py` sets `title=""` when a news article has no title. The news sentiment agent (`src/agents/news_sentiment.py`) then sends `Headline: ` (empty) to the LLM, which responds with `{"error": "No headline provided..."}` instead of `{sentiment, confidence}`. Pydantic rejects this, triggering 3 retries per empty headline — wasting LLM calls and burning quota.

**Fix:** In `src/agents/news_sentiment.py`, the filter for articles without sentiment now also skips articles with empty/blank titles:

```python
# Before
articles_without_sentiment = [news for news in recent_articles if news.sentiment is None]

# After
articles_without_sentiment = [
    news for news in recent_articles
    if news.sentiment is None and news.title and news.title.strip()
]
```

This eliminates all the "No headline provided" parsing errors and the wasted retry cycles they cause.

**Remaining issue:** OpenAI `429 insufficient_quota` is a billing/credits problem, not a code bug. Top up credits or switch to another provider (e.g., `--provider Groq` or `--provider Ollama`) before re-running the full signal cache.

---

### 429 abort fix applied

**cache_signals.py** now detects `429` or `insufficient_quota` in exceptions and:
- Aborts immediately (no endless retries)
- Prints a clear message: "QUOTA EXHAUSTED (429)"
- Writes `meta.json` with `aborted: "quota_exhausted"` and `has_signals: false`
- Exits with status 1

Users can run `cache_signals` without spinning on quota errors; the job fails fast and partial cache is preserved.

With these fixes in place, the **full-signal cache is stable** as long as the selected provider has sufficient quota. Mode 1 (prices-only) and the new fundamentals/events/macro/crypto caches described in `DATA.md` are unaffected by OpenAI limits and are the recommended baseline.

