# Autoresearch Program — Memory Sector (MU, WDC, STX)

You are an autonomous research agent. Your goal is to **maximize the Sharpe ratio** of the memory sector portfolio by tuning `params_memory.py`.

## The Setup

Three files matter:

- **`autoresearch/params_memory.py`** — The ONLY file you modify. Contains every tunable knob for the memory universe.
- **`autoresearch/evaluate.py`** — Runs a fast backtest and prints `val_sharpe=X.XXXX`.
- **`autoresearch/results_memory.tsv`** — Running log of all experiments (append-only, create if missing).

The backtest uses cached price data from `autoresearch/cache/prices_memory.json`. It makes **zero LLM calls and zero API calls** — pure math. Each experiment runs in ~4–6 seconds.

## The Loop

Repeat this loop indefinitely:

### Step 1: Read the current state
```bash
tail -5 autoresearch/results_memory.tsv 2>/dev/null || echo "No results yet"
cat autoresearch/params_memory.py
```

### Step 2: Form a hypothesis
Memory behavioral regime:
- **Highly cyclical** — DRAM/NAND cycle, strong momentum when cycle turns
- **Already generalizes well** — tech params gave Sharpe 2.44
- **Higher vol** — max DD -18.7%; risk limits may need tuning like equipment

### Step 3: Make ONE focused change to `autoresearch/params_memory.py`

### Step 4: Run the experiment
```bash
cd /Users/macbookpro16/Documents/stocks/ai-hedge-fund
poetry run python -m autoresearch.evaluate --params autoresearch.params_memory

# OOS check:
poetry run python -m autoresearch.evaluate --params autoresearch.params_memory \
  --start 2025-08-01 --end 2026-03-07
```

### Step 5: Compare and decide

**Baseline to beat:** `val_sharpe=2.7601, val_return=+294.73%, OOS=2.99`

- **If better** → commit and log to results_memory.tsv
- **If worse or equal** → revert

### Step 6: Repeat from Step 1

## Quick Reference

```bash
poetry run python -m autoresearch.evaluate --params autoresearch.params_memory
poetry run python -m autoresearch.evaluate --params autoresearch.params_memory --start 2025-08-01 --end 2026-03-07
git checkout autoresearch/params_memory.py  # revert
```
