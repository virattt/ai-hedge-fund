# Autoresearch Program — Equipment Sector (AMAT, ASML, LRCX, KLAC, TEL)

You are an autonomous research agent. Your goal is to **maximize the Sharpe ratio** of the equipment sector portfolio by tuning `params_equipment.py`.

## The Setup

Three files matter:

- **`autoresearch/params_equipment.py`** — The ONLY file you modify. Contains every tunable knob for the equipment universe.
- **`autoresearch/evaluate.py`** — Runs a fast backtest and prints `val_sharpe=X.XXXX`.
- **`autoresearch/results_equipment.tsv`** — Running log of all experiments (append-only, create if missing).

The backtest uses cached price data from `autoresearch/cache/prices_equipment.json`. It makes **zero LLM calls and zero API calls** — pure math. Each experiment runs in ~4-6 seconds.

## The Loop

Repeat this loop indefinitely:

### Step 1: Read the current state
```bash
# Check current best result
tail -5 autoresearch/results_equipment.tsv 2>/dev/null || echo "No results yet"

# Read the current params
cat autoresearch/params_equipment.py
```

### Step 2: Form a hypothesis
Think about what change might improve Sharpe. Equipment behavioral regime:
- **Capex cycle driven** — longer trend detection windows likely outperform
- **Higher vol than tech** (max DD -16.9% vs -8.2% for tech at same risk limit)
- **Strong momentum** — semiconductor equipment orders cluster in cycles
- **Correlation risk** — all 5 names (AMAT, ASML, LRCX, KLAC, TEL) are highly correlated → correlation penalty (CORR_BANDS) may matter more here than for tech

### Step 3: Make ONE focused change to `autoresearch/params_equipment.py`

### Step 4: Run the experiment
```bash
cd /Users/macbookpro16/Documents/stocks/ai-hedge-fund
poetry run python -m autoresearch.evaluate --params autoresearch.params_equipment

# OOS check (second half only):
poetry run python -m autoresearch.evaluate --params autoresearch.params_equipment \
  --start 2025-08-01 --end 2026-03-07
```

### Step 5: Compare and decide

**Baseline to beat:** `val_sharpe=1.9107, val_return=+98.74%, OOS=2.39`

- **If better** → commit and log:
  ```bash
  echo -e "$(date +%Y-%m-%dT%H:%M)\tYOUR_CHANGE\tval_sharpe=X.XXXX\tval_return=+XX%" >> autoresearch/results_equipment.tsv
  git add autoresearch/params_equipment.py autoresearch/results_equipment.tsv
  git commit -m "autoresearch[equip]: [describe change] | sharpe=X.XXXX"
  ```
- **If worse or equal** → revert:
  ```bash
  git checkout autoresearch/params_equipment.py
  ```

### Step 6: Repeat from Step 1

---

## Current State (read before first experiment)

**Baseline:** `val_sharpe=1.8781, val_return=+96.21%, val_max_dd=-17.5%`
**OOS (H2 2025):** `val_sharpe=2.3679, val_return=+72%` ← strong, don't hurt this

### What's already been optimized (do NOT re-test)
- `ADX_PERIOD` → 40 (quarterly capex cycle; 26=baseline, 40=best)
- `EMA_MEDIUM/LONG` → 21/55 (vs tech 13/34; longer trends)
- `RISK_BASE_LIMIT` → 0.30 (reducing to 0.22 or 0.26 hurts Sharpe)
- `STRATEGY_WEIGHTS` → trend=0.30, mr=0.18, momentum=0.37, vol=0.15 (tech weights = best; more trend=worse)
- `EMA_SHORT` → 5 (unchanged from tech, optimal)
- `BOLLINGER_WINDOW` → 30 (vs 20, +0.01)
- `RISK_EXTREME_VOL_MULT` → 0.60 (vs 0.50, +0.01)
- `MOM_CONFIDENCE_SCALE` → 18 (vs 15, +0.01)
- `VOL_LOW_REGIME` → 0.90 (vs 0.95)
- `VOL_HIGH_REGIME` → 1.25 (vs 1.2)
- `EMA_LONG` → 50 (vs 55)
- `STRATEGY_WEIGHTS` → trend 0.32, mr 0.16 (vs 0.30, 0.18)

### Still untried (priority order)
1. **MOM_3M_WEIGHT** — try 0.1, 0.2 (equipment has longer momentum cycles than tech)
2. **MOM_6M_WEIGHT** — try 0.1, 0.2 (6-month capex order cycle)
3. **MOM_CONFIDENCE_SCALE** — try 12.0, 18.0, 20.0
4. **BOLLINGER_WINDOW** — 30 done; try 35, 40
5. **VOL_HIST_WINDOW** — try 30, 42 (equipment vol is chunkier)
6. **VOL_MA_WINDOW** — try 90, 126 (quarterly averaging)
7. **CORR_BANDS** — equipment names are highly correlated; try tightening (0.70→0.5 multiplier for high correlation)
8. **RISK_MAX_MULT** — try 1.20, 1.25 (allow more size in low-vol regimes)
9. **SIGNAL_BULLISH_THRESHOLD** — try 0.15, 0.25
10. **RISK_EXTREME_VOL_MULT** — try 0.40, 0.60 (equipment has extreme vol spikes around earnings)
11. **BUY_THRESHOLD** — try 0.04, 0.06
12. **MIN_CONFIDENCE_TO_ACT** — try 15, 25

### Known dead code in params_equipment.py (changes have zero effect)
- `CORR_BANDS` / `CORR_DEFAULT_MULT` — defined but not yet wired (may become live if fast_backtest.py is updated)
- `CONFIDENCE_POWER` — cancels out in technical-only mode
- `BB_BULLISH`, `BB_BEARISH`, `ZSCORE_BULLISH`, `ZSCORE_BEARISH` — BOLLINGER_STD=5.0 makes these unreachable
- `STAT_ARB_ROLLING`, `HURST_MAX_LAG`, `HURST_THRESHOLD`, `SKEW_THRESHOLD` — stat_arb weight=0.00

---

## Important Rules

1. **ONLY modify `autoresearch/params_equipment.py`**. Never modify evaluate.py, fast_backtest.py, params.py, or any src/ files.
2. **ALWAYS run evaluate.py with `--params autoresearch.params_equipment` after a change.**
3. **ALWAYS revert if worse or equal.** Never keep a neutral change.
4. **Keep params_equipment.py valid Python.** If evaluate crashes, revert immediately.
5. **No negative weights.** Strategy weights and analyst weights must be >= 0.
6. **Check OOS periodically** (every ~10 commits) to ensure we're not overfitting.

## Quick Reference

```bash
# Run experiment
poetry run python -m autoresearch.evaluate --params autoresearch.params_equipment

# OOS check
poetry run python -m autoresearch.evaluate --params autoresearch.params_equipment \
  --start 2025-08-01 --end 2026-03-07

# Revert bad change
git checkout autoresearch/params_equipment.py

# Commit good change
git add autoresearch/params_equipment.py autoresearch/results_equipment.tsv
git commit -m "autoresearch[equip]: <description> | sharpe=X.XXXX"

# Check results history
cat autoresearch/results_equipment.tsv
```
