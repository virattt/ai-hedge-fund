# Autoresearch Program — AI Hedge Fund Parameter Optimization

You are an autonomous research agent. Your goal is to **maximize the Sharpe ratio** of a multi-agent hedge fund system by tuning its parameters.

## The Setup

There are three files that matter:

- **`autoresearch/params.py`** — The ONLY file you modify. Contains every tunable knob.
- **`autoresearch/evaluate.py`** — Runs a fast backtest and prints `val_sharpe=X.XXXX`.
- **`autoresearch/results.tsv`** — Running log of all experiments (append-only).

The backtest uses cached price data and (optionally) cached agent signals. It makes **zero LLM calls and zero API calls** — pure math. Each experiment runs in seconds.

## The Loop

Repeat this loop indefinitely:

### Step 1: Read the current state
```bash
# Check current best result
tail -5 autoresearch/results.tsv

# Read the current params
cat autoresearch/params.py
```

### Step 2: Form a hypothesis
Think about what change might improve Sharpe. Consider:
- Which strategy weights are overweighted for this market regime?
- Are the indicator windows too short or too long?
- Are the risk limits too tight or too loose?
- Which analyst signals are adding noise vs. alpha?
- Are the buy/sell thresholds optimal?

### Step 3: Make ONE focused change to `autoresearch/params.py`
Change ONE parameter or ONE small group of related parameters. Examples:
- Increase momentum weight from 0.25 to 0.35 (decrease another to compensate)
- Shorten EMA_SHORT from 8 to 5
- Increase BUY_THRESHOLD from 0.15 to 0.20
- Reduce ANALYST_WEIGHTS for a noisy agent
- Tighten risk limits (reduce RISK_BASE_LIMIT)

### Step 4: Run the experiment
```bash
cd /Users/macbookpro16/Documents/stocks/ai-hedge-fund
poetry run python -m autoresearch.evaluate
```

### Step 5: Compare and decide
Read the output. Compare `val_sharpe` with the previous best.

- **If better** → commit and keep:
  ```bash
  git add autoresearch/params.py autoresearch/results.tsv
  git commit -m "autoresearch: [describe change] | sharpe=X.XXXX"
  ```
- **If worse or equal** → revert:
  ```bash
  git checkout autoresearch/params.py
  ```

### Step 6: Repeat from Step 1

## Strategy Guide

### What to optimize (priority order)

1. **Strategy weights** (Section 1 in params.py) — Which technical strategies contribute alpha? Try shifting weight from underperformers to outperformers. The weights don't need to sum to 1.0 but should stay non-negative.

2. **Signal classification thresholds** (SIGNAL_BULLISH_THRESHOLD, SIGNAL_BEARISH_THRESHOLD) — Are we too eager or too cautious in classifying signals?

3. **Portfolio decision rules** (Section 5) — BUY_THRESHOLD, SELL_THRESHOLD, SHORT_THRESHOLD, POSITION_SIZE_FRACTION, MIN_CONFIDENCE_TO_ACT. These directly control trade generation.

4. **Indicator windows** (Section 2) — EMA periods, RSI periods, Bollinger width, momentum lookbacks. Shorter windows = more responsive but noisier.

5. **Risk parameters** (Section 3) — Volatility bands, correlation multipliers, base limits. Looser limits = bigger positions = more reward/risk.

6. **Analyst weights** (Section 4) — Only useful if you ran `cache_signals.py` first. Otherwise only `technical_analyst_agent` has a signal.

### Tips

- **One variable at a time** for clean attribution. Multi-variable changes make it hard to know what helped.
- **Try the opposite** of your intuition sometimes. If increasing a param helped, try increasing it more. If it hurt, try the opposite direction.
- **Explore before exploiting.** In the first ~20 experiments, make large changes to map the landscape. Then fine-tune the best region.
- **Track which changes helped.** Use descriptive commit messages.
- **Don't over-fit.** If the backtest window is short, be wary of changes that produce >2x improvement — they might be noise.
- **Periodically check `results.tsv`** to see the trajectory and decide where to focus.
- **If Sharpe is negative**, focus on reducing max drawdown and increasing total return before fine-tuning.

### Experiment budget

Each experiment takes ~4-6 seconds. Aim for **50+ experiments per hour**. In an overnight session (8 hours), that's 400+ experiments.

## Current State (read this before your first experiment)

**Baseline to beat:** `val_sharpe=2.0358, val_return=+59.97%` (ADX 26, RISK_BASE_LIMIT 0.32)

- **Mode 2** (signals.json + technical_analyst only): `val_sharpe=2.0221, val_return=+58.33%`
- **Mode 1** (no signals): `val_sharpe=1.7945, val_return=+49.11%`

**What happened in 191 experiments across 2 sessions:**
The strategy is running in Mode 1 (technical-only). The system is now correctly calibrated for a 14-month AI bull market (Jan 2025 – Mar 2026) on AAPL, NVDA, MSFT, GOOGL, TSLA.

**What's already been optimized (do not re-test):**
- `BOLLINGER_STD` → 5.0 (neutralizes Bollinger, lets RSI drive mean-reversion)
- `MOM_BULLISH/BEARISH` → ±0.001
- `RISK_BASE_LIMIT` → 0.30
- `RISK_VOL_BANDS` → flat 1.0 for medium/high vol (no tech penalty)
- `ADX_PERIOD` → 22 (≈1 calendar month, sweet spot)
- `stat_arb` weight → 0.00 (noise for correlated tech names)
- `POSITION_SIZE_FRACTION` → 1.00 (full deployment)
- `VOL_LOW_REGIME` → 0.95, `VOL_Z_BULLISH` → -0.5, `VOL_Z_BEARISH` → 2.0
- `STRATEGY_WEIGHTS` → trend=0.30, mr=0.18, momentum=0.37, vol=0.15, stat_arb=0.00

**RSI now live (fast_backtest.py):** `RSI_OVERSOLD`, `RSI_OVERBOUGHT`, `RSI_SHORT` drive mean-reversion. Use 0/100 to disable. Default 30/70 hurt in bull market; 25/75 also worse. Try 20/80 or 35/65 in bear/sideways regimes.

**Known dead code in params.py (changes have zero effect):**
- `CORR_BANDS` / `CORR_DEFAULT_MULT` — function defined but never called
- `CONFIDENCE_POWER` — cancels out in Mode 1 (single agent)
- `BB_BULLISH`, `BB_BEARISH`, `ZSCORE_BULLISH`, `ZSCORE_BEARISH` — dead since BOLLINGER_STD=5.0 makes condition impossible

**Session 2 (2026-03-12):** ADX_PERIOD 22→26 **improved** to 2.0241 (committed).

**Session 1 (reverted — no improvement over 2.02):**
- `MOM_6M_WEIGHT` 0.3 → Sharpe 1.17 (worse)
- `RISK_MIN_MULT` 0.10 → same 2.02
- `SIGNAL_BULLISH_THRESHOLD` 0.22 → 1.93, 0.18 → 1.75 (worse)
- `cathie_wood_agent` 0.2 → 0.03, -30% dd (much worse)
- `STRATEGY_WEIGHTS` momentum 0.39 → same
- `BUY_THRESHOLD` 0.06, `MIN_CONFIDENCE_TO_ACT` 15, `RISK_MAX_MULT` 1.20 → same

**Session 2 tested:** MOM_3M 0.2 (worse), EMA shorter (worse), ADX 18/26/28 (26 best), VOLATILITY_LOOKBACK 40/50 (worse), fundamentals 0.05 (same).

**Still untried:** `RISK_BASE_LIMIT`, low-vol band multiplier, `SELL_THRESHOLD`.

**To get Mode 2 (2.02):** Run `cache_signals.py` first, then `evaluate`. Ensure `signals.json` exists in `autoresearch/cache/`.

---

## Important Rules

1. **ONLY modify `autoresearch/params.py`**. Never modify evaluate.py, fast_backtest.py, or any src/ files.
2. **ALWAYS run evaluate.py after a change.** Never commit without measuring.
3. **ALWAYS revert if worse.** Never keep a change that reduces Sharpe.
4. **Keep params.py valid Python.** If the evaluate crashes, revert immediately.
5. **No infinite values.** Keep all parameters finite and reasonable.
6. **No negative weights.** Strategy weights and analyst weights must be >= 0.

## Quick Reference

```bash
# Run one experiment
poetry run python -m autoresearch.evaluate

# Check results history
cat autoresearch/results.tsv

# Revert a bad change
git checkout autoresearch/params.py

# Commit a good change
git add autoresearch/params.py autoresearch/results.tsv
git commit -m "autoresearch: <description> | sharpe=X.XXXX"
```
