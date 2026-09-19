# Contributing

This repository is a fork of [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund). The goal of the fork workflow is to iterate locally without spending API credits.

## First test (offline, no keys)

```bash
git clone https://github.com/bugman666/ai-hedge-fund.git
cd ai-hedge-fund
poetry install
poetry run pytest hedge_fund
```

That is the same command CI runs. Most tests mock HTTP, LLM providers, and market data. Live Financial Datasets smoke tests are marked `live` and **skip** unless `FINANCIAL_DATASETS_API_KEY` is set — they do not fail a keyless run.

To exclude live tests even if a key is exported in your shell:

```bash
poetry run pytest hedge_fund -m "not live"
```

## First backtest (optional, needs keys)

Copy `.env.example` to `.env` in the repo root or to `~/.hedge-fund/.env` and set:

- `FINANCIAL_DATASETS_API_KEY` — prices, fundamentals, and earnings
- one LLM provider key if investor agents will run (quant-only mandates do not need an LLM key)
- or a local Ollama daemon for the no-key path: pull a tag (`ollama pull llama3.1`), then select it in the picker, pass `--model llama3.1`, or use `ollama:<tag>` for a pulled model that is not in the registry. Override the host with `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`). A missing daemon raises `LLMCallError` inside `LLM_REQUEST_TIMEOUT`; it does not hang. CI mocks this HTTP — do not point tests at a live Ollama.

Then:

```bash
poetry run aihf
# or, non-interactive paper cycle / backtest:
poetry run aihf ~/.hedge-fund/mandates/example.yaml --tickers AAPL,MSFT --paper
poetry run aihf ~/.hedge-fund/mandates/example.yaml --tickers AAPL,MSFT --backtest
```

The interactive app still prompts for missing keys on first run. Non-interactive and library paths raise immediately if a required key is absent (`FINANCIAL_DATASETS_API_KEY` on `FDClient()`, LLM keys on `make_llm()`).

To run the live Financial Datasets smoke tests:

```bash
export FINANCIAL_DATASETS_API_KEY=...
poetry run pytest hedge_fund/data/test_client.py
```

## Pull requests

Keep pull requests small and focused. CI must stay green without live API keys.
