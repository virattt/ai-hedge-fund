# Automation Jobs

This document describes the queue-driven automation jobs that coordinate AI Hedge Fund runs.

## Azure Storage Queue Message Schema

Messages must be UTF-8 JSON objects. The worker validates every message before processing and will dead-letter any payload that does not conform to the schema below.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `tickers` | array of strings | ✅ | One or more ticker symbols to analyse. Empty strings are removed automatically. |
| `analysis_window.start` | string (YYYY-MM-DD) | ✅ | Inclusive start date for the analysis window. You may also supply `analysis_window.start_date`. |
| `analysis_window.end` | string (YYYY-MM-DD) | ✅ | Inclusive end date for the analysis window. You may also supply `analysis_window.end_date`. |
| `overrides.show_reasoning` | boolean | ❌ | Whether to include detailed agent reasoning in the final payload. Defaults to `false`. |
| `overrides.selected_analysts` | array of strings | ❌ | Optional subset of analysts to include in the workflow. Defaults to all analysts. |
| `overrides.model_name` | string | ❌ | Explicit LLM model name, e.g. `gpt-4.1`. Defaults to the CLI default. |
| `overrides.model_provider` | string | ❌ | Provider key used by `run_hedge_fund`. Defaults to `OpenAI`. |
| `overrides` (other keys) | any | ❌ | Additional keys are preserved in the `metadata.rawMessage` field when results are persisted. |

### Example Message

```json
{
  "tickers": ["AAPL", "MSFT", "NVDA"],
  "analysis_window": {
    "start": "2024-01-01",
    "end": "2024-03-31"
  },
  "overrides": {
    "show_reasoning": false,
    "model_name": "gpt-4.1-mini"
  }
}
```

## Processing Flow

1. The worker boots with `python -m src.jobs.queue_worker` (see Docker notes below) and loads Azure Storage Queue credentials from `QUEUE_ACCOUNT`, `QUEUE_NAME`, and `QUEUE_SAS`.
2. One message is dequeued per invocation (Container Apps Jobs should run on a schedule or event trigger).
3. The worker retrieves the latest portfolio snapshot from Cosmos DB via `CosmosRepository.get_latest_portfolio_snapshot()`.
4. `run_hedge_fund(...)` executes using the tickers, analysis window, and optional overrides.
5. Results are persisted with `CosmosRepository.save_run_result(...)`, and a concise status summary is published via `CosmosRepository.publish_status(...)` before the queue message is deleted.

## Retry & Dead-Letter Semantics

- Network/API failures raised by Azure SDKs or HTTP clients are retried with exponential backoff (`QUEUE_MAX_ATTEMPTS`, default `5`). The delay doubles from `QUEUE_BACKOFF_SECONDS` (default `2s`) up to `QUEUE_BACKOFF_MAX_SECONDS` (default `30s`) with jitter.
- If all retry attempts fail, or if a non-retryable exception bubbles up from the business logic, the original queue message is moved to the dead-letter queue defined by `QUEUE_DEAD_LETTER_NAME` (defaults to `<QUEUE_NAME>-deadletter`).
- Malformed payloads (missing tickers, invalid JSON, missing analysis window, incorrect `overrides` type, etc.) are treated as poison messages and are immediately moved to the dead-letter queue without retry.

Dead-lettered messages are wrapped in a JSON envelope with the original payload, failure reason, and a UTC timestamp so you can analyse or replay them later.

## Docker / Container Apps Jobs

A dedicated worker image is provided via `docker/worker.Dockerfile`. Azure Container Apps Jobs should execute:

```bash
python -m src.jobs.queue_worker
```

The worker automatically loads environment variables from the mounted `.env` file (via `python-dotenv`) before connecting to Azure resources.
