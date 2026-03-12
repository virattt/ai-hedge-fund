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

**Session 2 best (commit `485d4d0`, 2026-03-12):**
`val_sharpe=1.7880, val_sortino=2.8507, val_max_dd=-8.58%, val_return=+48.76%`

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

**Known dead code in params.py (changes have zero effect):**
- `CORR_BANDS` / `CORR_DEFAULT_MULT` — function defined but never called
- `RSI_SHORT` / `RSI_LONG` — `compute_rsi()` is defined but never called in the backtest
- `CONFIDENCE_POWER` — cancels out in Mode 1 (single agent)
- `BB_BULLISH`, `BB_BEARISH`, `ZSCORE_BULLISH`, `ZSCORE_BEARISH` — dead since BOLLINGER_STD=5.0 makes condition impossible

**Most promising next moves (in order):**
1. `MOM_6M_WEIGHT` — currently 0.0, **never tested**. 6-month momentum is the Jegadeesh-Titman factor, one of the most robust return predictors. Try `MOM_1M_WEIGHT=0.7, MOM_6M_WEIGHT=0.3`.
2. `RISK_MIN_MULT` — currently 0.25 (floor on position sizing). Try 0.10 to allow more aggressive deployment on strong signals even in elevated vol.
3. `SIGNAL_BULLISH_THRESHOLD` — try 0.22 or 0.23 (slight increase = more selective buys).
4. **Mode 2** — put signals.json back and tune `ANALYST_WEIGHTS` to down-weight bearish value agents (Graham, Munger, Burry) on this momentum tech universe.

Start with #1 — `MOM_6M_WEIGHT` is the only major untested live lever.

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
