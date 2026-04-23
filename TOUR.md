# AI Hedge Fund Step-by-Step Tour

This tour helps you understand the project from graph orchestration to final decisions.

## Step 0: Setup

Run these commands in project root:

```bash
poetry install
cp .env.example .env
```

If you want local Ollama model:

```bash
ollama serve
ollama list
```

## Step 1: Understand the Runtime Entry

Read:

- src/main.py
- src/graph/state.py

What to focus on:

- `run_hedge_fund(...)` creates the initial graph state
- `create_workflow(...)` builds StateGraph nodes and edges
- `AgentState` has `messages`, `data`, and `metadata`

## Step 2: Understand Node Order

The workflow order is:

1. `start_node`
2. selected analyst nodes
3. `risk_management_agent`
4. `portfolio_manager`
5. `END`

Why this matters:

- Analysts produce signals first
- Risk node computes allowed position capacity
- Portfolio node combines both for final decisions

## Step 3: Trace LLM Interaction

Read:

- src/utils/llm.py
- src/llm/models.py
- src/agents/portfolio_manager.py

What to focus on:

- `call_llm(...)` is the shared LLM gateway
- model comes from state metadata (`model_name`, `model_provider`)
- output is validated by Pydantic models

## Step 4: Run a Minimal CLI Session

```bash
poetry run python src/main.py --tickers AAPL --start-date 2026-03-01 --end-date 2026-04-01
```

Tip:

- pick 1 ticker and 1-2 analysts first, then scale up

## Step 5: Run Learning Tests (No external APIs)

```bash
poetry run pytest tests/test_tour_smoke.py -q
```

These tests verify:

- graph contains core nodes
- JSON response parsing behavior
- sell/hold constraints from portfolio positions

## Step 5.1: Run Mocked End-to-End Flow (No external APIs)

```bash
poetry run pytest tests/test_tour_e2e_mock.py -q
```

This test demonstrates the full runtime chain with mocks:

- analyst node writes signals
- risk node writes limits and prices
- portfolio manager consumes both and emits final decision

## Step 6: Deep Dive Checklist

- Can you explain where `risk_data` is written?
- Can you explain where `sell` becomes allowed?
- Can you explain where LLM picks `sell` vs `hold`?
- Can you explain what is deterministic vs model-driven?

## Step 7: Suggested Practice Path

1. Add one custom analyst node and connect it.
2. Add one new field into `metadata` and consume it in one agent.
3. Add one test for your new node output shape.

If you can do all three, you are ready to modify strategy logic safely.
