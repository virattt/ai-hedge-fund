# Dexter -> AIHF Second-Opinion Instructions

Use this section in the Dexter repo so any operator can run a reliable second-opinion pass against AI Hedge Fund.

## README Paste Block (short version)

```markdown
### AIHF second-opinion (quick start)

1) Start AIHF backend:
`poetry run uvicorn app.backend.main:app --reload`

2) Submit a Dexter draft + poll until complete:
```bash
poetry run python scripts/dexter_second_opinion_client.py \
  --draft /absolute/path/to/portfolio_draft_tastytrade.json \
  --flow-id 1 \
  --base-url http://localhost:8000 \
  --output-dir ./second_opinion_runs \
  --params-profile tastytrade_factors_on \
  --run-report
```

Expected: `final status: COMPLETE`, result JSON written, and non-null `results.decisions` / `results.analyst_signals`.
```

## Purpose

Dexter remains the thesis engine. AIHF is the adversarial committee check.
For each `PortfolioDraft`, Dexter can call AIHF async, wait for completion, and turn the response into agreement/disagreement buckets.

## 1) Start AIHF backend

Run in the AIHF repo:

```bash
poetry run uvicorn app.backend.main:app --reload
```

Default base URL:

- `http://localhost:8000`

## 2) Submit a draft and poll status (recommended helper)

Run in the AIHF repo (or vendor/copy the helper into Dexter automation):

```bash
poetry run python scripts/dexter_second_opinion_client.py \
  --draft /absolute/path/to/portfolio_draft_tastytrade.json \
  --flow-id 1 \
  --base-url http://localhost:8000 \
  --output-dir ./second_opinion_runs \
  --params-profile tastytrade_factors_on \
  --run-report
```

What this does:

1. Loads graph from saved flow (`--flow-id`)
2. POSTs run to `/api/v1/second-opinion/runs`
3. Polls `/api/v1/second-opinion/runs/{run_id}`
4. Fetches `/api/v1/second-opinion/runs/{run_id}/result`
5. Prints Strong agree / Mild disagree / Hard disagree

## 3) Expected healthy output

- `final status: COMPLETE`
- `second_opinion_run_result_<run_id>.json` is written
- Result contains non-null:
  - `results.decisions`
  - `results.analyst_signals`

## 4) API contract (if calling from Dexter directly)

- `POST /api/v1/second-opinion/runs` -> `{ "run_id": <int>, "status": "queued" }`
- `GET /api/v1/second-opinion/runs/{run_id}` -> status metadata
- `GET /api/v1/second-opinion/runs/{run_id}/result` -> final payload when `COMPLETE` or `ERROR`

## 5) Minimum draft fields

```json
{
  "sleeve": "tastytrade",
  "params_profile": "tastytrade_factors_on",
  "assets": [
    { "symbol": "ASML", "target_weight_pct": 8.0 },
    { "symbol": "AMAT", "target_weight_pct": 6.0 }
  ],
  "graph_nodes": [],
  "graph_edges": [],
  "margin_requirement": 0.5,
  "portfolio_positions": [],
  "model_name": "gpt-4.1",
  "model_provider": "openai"
}
```

Notes:

- If `graph_nodes`/`graph_edges` are empty, pass `--flow-id` so the client hydrates graph from a saved flow.
- `model_provider` is normalized by the helper, but keep canonical provider names in production payloads.

## 6) Known-good milestone

Validated end-to-end with:

- `--draft portfolio_draft_tastytrade.json`
- `--flow-id 1`
- `--params-profile tastytrade_factors_on`

Recent successful runs completed with populated decisions/signals and non-empty agreement output.
