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
# always-on paper/sim scheduler (one evaluation, no long poll):
poetry run python -m hedge_fund.daemon ~/.hedge-fund/mandates/example.yaml --tickers AAPL,MSFT --once
```

The interactive app still prompts for missing keys on first run. Non-interactive and library paths raise immediately if a required key is absent (`FINANCIAL_DATASETS_API_KEY` on `FDClient()`, LLM keys on `make_llm()`).

To run the live Financial Datasets smoke tests:

```bash
export FINANCIAL_DATASETS_API_KEY=...
poetry run pytest hedge_fund/data/test_client.py
```

## Cycle observability (optional, offline)

The paper / live-clock CLI path can emit structured cycle events, refresh a
heartbeat file, and POST a failure webhook — no live APIs required to turn
this on. Useful later for a scheduler/daemon; useful today to watch a
hand-run cycle.

| Variable | What it does |
|----------|----------------|
| `HEDGE_FUND_EVENTS_PATH` | Append `cycle_start` / `cycle_end` / `cycle_error` as JSONL (also `--events [PATH]`) |
| `HEDGE_FUND_HEARTBEAT_PATH` | Heartbeat JSON the process rewrites each cycle (also `--heartbeat [PATH]`) |
| `HEDGE_FUND_HEARTBEAT=1` | Same heartbeat at `~/.hedge-fund/observability/heartbeat.json` |
| `HEDGE_FUND_WEBHOOK_URL` | POST a JSON failure summary if the cycle raises |
| `HEDGE_FUND_WEBHOOK_TIMEOUT` | Webhook timeout in seconds (default 5) |

Events always log at info/error. A failed webhook is logged; the original
cycle exception still propagates (fail loud). Offline tests live in
`hedge_fund/observability/test_observability.py` and use temp dirs plus a
mocked HTTP POST.

```bash
poetry run aihf ~/.hedge-fund/mandates/example.yaml --tickers AAPL,MSFT \
  --heartbeat /tmp/hedge-fund-heartbeat.json \
  --events /tmp/hedge-fund-events.jsonl
```

## Pull requests

Keep pull requests small and focused. CI must stay green without live API keys.
