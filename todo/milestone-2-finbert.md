# Milestone 2: FinBERT Financial Sentiment Agent

**Goal:** Add a local FinBERT model (`ProsusAI/finbert` from HuggingFace) as a new analyst agent. Runs locally, no LLM API tokens needed.

**Risk:** Low-Medium — new agent, no existing code modified except analyst registry. Heavy dependencies (torch).

**Dependency:** Benefits from M1 (scraped article text) but works without it (uses headlines).

## Tasks

- [ ] Add `transformers>=4.35.0`, `torch` to `pyproject.toml`
- [ ] Create `src/tools/finbert.py` with `FinBERTAnalyzer` singleton
  - Lazy-load model on first call (`ProsusAI/finbert`)
  - `analyze_sentiment(text) -> dict` — returns `{label, score}` (positive/negative/neutral)
  - `analyze_batch(texts) -> list[dict]` — batch inference
  - Handle model download gracefully
- [ ] Create `src/agents/finbert_sentiment.py`
  - `finbert_sentiment_agent(state)` following exact pattern of `news_sentiment_agent`
  - Fetch news via `src/tools/api.py`
  - Optionally use scraped text from M1 if available
  - Run FinBERT per article
  - Aggregate into signal (bullish/bearish/neutral) with confidence
  - No LLM call — pure model inference + rule-based aggregation
- [ ] Register in `src/utils/analysts.py` `ANALYST_CONFIG` with `order: 17`
- [ ] Write tests in `tests/test_finbert.py`
  - Mock transformer pipeline
  - Verify output format matches expected signal schema
  - Test aggregation logic
  - Test graceful failure when model unavailable
- [ ] Integration test: run with FinBERT agent selected
  - Should produce signal with per-article FinBERT scores in reasoning

## Files

| Action | File |
|--------|------|
| Create | `src/tools/finbert.py` |
| Create | `src/agents/finbert_sentiment.py` |
| Create | `tests/test_finbert.py` |
| Modify | `pyproject.toml` |
| Modify | `src/utils/analysts.py` |
