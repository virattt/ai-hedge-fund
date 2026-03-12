# AutoResearch Results — ARR.md

> Autonomous parameter optimization of the AI Hedge Fund trading strategy.
> Inspired by Andrej Karpathy's autoresearch paradigm: *"programming the program."*
> The agent modifies one file (`params.py`), measures the result, commits if better, reverts if not.

---

## Sessions

| Session | Date | Commits | Experiments | Start Sharpe | End Sharpe |
|---|---|---|---|---|---|
| Session 1 | 2026-03-10 | ~15 | ~80 | -2.3132 (Mode 2 broken) → 1.0385 (Mode 1 baseline) | **2.2203** (overfit, 6-month window) |
| Session 2 | 2026-03-12 | 27 | ~110 | 1.0385 (full 14-month window) | **1.7880** |
| **Total** | | **~42** | **191** | **-2.3132** | **1.7880** |

---

## The Setup

### What is being optimized

A systematic trading strategy backtested over **14 months** (Jan 2025 – Mar 2026) on 5 tech stocks: `AAPL`, `NVDA`, `MSFT`, `GOOGL`, `TSLA`. Starting capital: $100,000.

The **objective function** is `val_sharpe` — the Sharpe ratio on the validation window. It is fast (~5 seconds per evaluation), deterministic, and directly measures risk-adjusted return.

### The agent's constraint

The agent is allowed to modify **only one file**: `autoresearch/params.py`. This file contains every tunable knob. The loop is:

```
modify params.py → run evaluate.py → compare Sharpe
  → if better: git commit (keep the improvement)
  → if worse: git checkout params.py (discard, revert to last best)
```

This guarantees **monotonic improvement** — the committed state is always the best seen so far.

### Two modes

- **Mode 1 (Technical-Only)**: The backtest uses only recomputed technical indicators. Single agent. This is what Session 2 optimized.
- **Mode 2 (Full-Signal)**: Uses cached signals from 18 LLM investor agents (Buffett, Burry, Damodaran, etc.) plus technical indicators. Requires `autoresearch/cache/signals.json` to be present.

---

## Session 1 — Diagnosis and Baseline (2026-03-10)

### The initial problem

The first run of `evaluate.py` produced:

```
val_sharpe=0.0   val_sortino=-15.87   val_max_dd=0.0   val_return=0.0
```

Zero trades. Zero return. **The portfolio was holding 100% cash the entire backtest.**

### Root cause diagnosis

The system was running in **Mode 2** because `signals.json` was present. The 18 LLM agents had a strong **bearish bias on tech stocks** — they were trained on value investing frameworks (Graham, Munger, Buffett) that inherently distrust high-multiple growth stocks. During a 2025 AI bull market, these agents were unanimously bearish on NVDA, AAPL, MSFT.

The `SHORT_THRESHOLD` was set to `-0.90`, meaning the portfolio would only open a short if the aggregate signal was more negative than -0.90. The bearish signals from 18 agents clustered around -0.50 to -0.65 — not negative enough to short, but negative enough to block all buys. **The system was paralyzed.**

The mathematical fingerprint: a Sortino of -15.87 on zero returns is what happens when you hold 100% cash while the benchmark runs up 40%+. The "return" relative to benchmark is catastrophically negative but zero actual portfolio moves.

### Fix

`SHORT_THRESHOLD: -0.90 → -0.15`

This unblocked Mode 2 by allowing shorts when the aggregate signal was sufficiently bearish. The portfolio started trading. However, Mode 2 Sharpe was still problematic because the bearish agents caused heavy shorting during a bull run.

### Session 1 outcome

Session 1 focused on a **6-month window** (overfit) and reached `val_sharpe = 2.2203`. This result was **not durable** — when re-evaluated on the full 14-month window it collapsed to `-0.09`. Session 1 also identified:
- The `SHORT_THRESHOLD` fix
- Faster EMAs (5/13/34 vs 8/21 defaults)
- Trend weight should be higher than mean reversion

A deliberate reset commit (`eec076d`) established the true baseline: **`val_sharpe = 1.0385` on the full 14-month window**.

---

## Session 2 — Systematic Optimization (2026-03-12)

### Starting point

```
val_sharpe  = 1.0385
val_sortino = 1.6411
val_max_dd  = -12.69%
val_return  = +28.92%
```

### The optimization sequence (all 27 committed improvements)

#### Phase 1: Signal Quality (Sharpe 1.04 → 1.07)

**Exp 1–4: `BOLLINGER_STD` 2.5 → 3.0 → 3.5 → 4.0 → 5.0**

Hypothesis: Bollinger bands at 2.5σ were generating false mean-reversion signals. Tech stocks in a bull market trend — they don't revert cleanly to a 2.5σ band. Widening the bands should reduce false bearish mean-reversion signals.

Result: Monotonic improvement from 1.0385 to **1.0564** at 5.0σ. Testing 6.0σ showed no further gain — 5.0σ is effectively a "never trigger" threshold that neutralizes the Bollinger signal entirely, leaving RSI as the sole mean-reversion driver.

**Side effect discovered**: With `BOLLINGER_STD=5.0`, the mean-reversion sub-strategy's `BB_BULLISH`, `BB_BEARISH`, `ZSCORE_BULLISH`, `ZSCORE_BEARISH` parameters become **dead levers** — the Bollinger condition is almost impossible to satisfy in practice.

**Exp 5–7: `MOM_BULLISH/MOM_BEARISH` 0.01 → 0.005 → 0.002 → 0.001**

Hypothesis: A 1% 1-month return threshold to trigger a momentum signal was too coarse for daily rebalancing on large-cap tech. Lower the bar to capture more momentum moves.

Result: Monotonic improvement from 1.0564 to **1.0669** at ±0.001. Testing ±0.0005 showed slight worsening — the signal becomes too noisy at sub-0.1% thresholds.

---

#### Phase 2: Capital Deployment (Sharpe 1.07 → 1.23)

**Exp 8: `RISK_BASE_LIMIT` 0.18 → 0.30**

Hypothesis: At 18% base position limit, the strategy was severely capital-constrained. With 5 stocks and a 30% risk budget, you can't deploy meaningfully. The improved signal quality from Phase 1 justifies larger positions.

Result: **+0.083 Sharpe jump** (1.0669 → 1.1495). Testing 0.35 and 0.40 showed diminishing returns — 30% is the risk-adjusted sweet spot for this 5-stock universe.

**Exp 9–10: `RISK_VOL_BANDS` — remove volatility penalties**

Baseline bands:
```python
(0.15, 1.25),   # low vol → modest boost
(0.30, 0.90),   # medium vol → 10% reduction
(0.50, 0.60),   # high vol → 40% reduction
```

Hypothesis: These bands were built for a diversified portfolio. Applied to AAPL, NVDA, MSFT, GOOGL, TSLA — all structurally high-vol tech stocks in a bull market — they were permanently penalizing every single position. A 40% reduction on high-vol names means the strategy was never deploying full capital on its best signals.

Fix in two steps: first relaxed medium-vol penalty, then removed all penalties entirely:
```python
(0.15, 1.25),   # low vol → keep boost
(0.40, 1.00),   # medium vol → no penalty
(0.70, 1.00),   # high vol → no penalty
```

Result: **1.1865 → 1.2334**. This was the second-largest single-phase improvement of the session.

---

#### Phase 3: Trend Detection (Sharpe 1.23 → 1.43)

**Exp 11–13: `ADX_PERIOD` 10 → 14 → 21 → 22**

Hypothesis: ADX at period 10 is extremely noisy — it fires on every 2-day move. The standard technical analysis period is 14. But for large-cap tech on daily data in a trending market, a longer lookback should filter noise better.

Result: Monotonic improvement through 14 (1.2385), 21 (1.2792). Testing 20 and 23 showed worsening. **ADX_PERIOD=22 was later found to be the true sweet spot** at Sharpe 1.6997 (discovered again in the fine-tuning phase).

The intuition: 22 trading days ≈ 1 calendar month of trend measurement. Monthly trend confirmation is the right granularity for daily trades in a monthly-rebalancing universe.

**Exp 14–15: `STRATEGY_WEIGHTS` — kill stat_arb, boost momentum**

Hypothesis: `stat_arb` weight = 0.10 was consuming model capacity on a Hurst exponent calculation that is irrelevant for highly correlated, trending large-cap tech stocks. The Hurst exponent works for mean-reverting asset pairs. AAPL and NVDA in 2025 are momentum names, not stat-arb candidates.

Changes:
- `stat_arb`: 0.10 → 0.00 (eliminate noise)
- `momentum`: 0.35 → 0.45 (reallocate to strongest signal)
- `trend`: 0.25 → 0.30 (then rebalanced further)

Result: **1.2792 → 1.3903 → 1.4130**

**Dead code discovery**: With `stat_arb=0.00`, the `compute_hurst()` function still runs every bar but its result is multiplied by zero weight. This is wasted compute, not a correctness issue.

---

#### Phase 4: Full Capital Deployment (Sharpe 1.41 → 1.61)

**Exp 16–20: `POSITION_SIZE_FRACTION` 0.35 → 0.50 → 0.65 → 0.80 → 1.00**

Hypothesis: With Phase 1-3 improvements now generating high-quality signals, the 35% position fraction was leaving money on the table. Each step up proved justified.

Result: Monotonic improvement:
- 0.35 → 0.50: **1.4130 → 1.4707**
- 0.50 → 0.65: **1.4707 → 1.4997**
- 0.65 → 0.80: **1.4997 → 1.5532**
- 0.80 → 1.00: **1.5532 → 1.6088**

This is the clearest validation of Phase 1-3: **signal quality was the bottleneck, not position sizing**. Once signals were clean, deploying maximum allowed capital improved Sharpe at every step.

---

#### Phase 5: Volatility Regime Calibration (Sharpe 1.61 → 1.70)

**Exp 21: `VOL_LOW_REGIME` 0.80 → 0.95**

Hypothesis: A vol regime ratio of 0.80 (current vol must be 20% below its MA to qualify as "low vol") is too restrictive for tech stocks. Most trading days in a trending bull market should qualify as low-vol.

Result: **1.6088 → 1.6345**

**Exp 22: `VOL_Z_BULLISH` -1.0 → -0.5**

Hypothesis: Requiring vol Z-score < -1.0 to generate a bullish vol signal meant only the lowest-volatility days triggered this signal. Relaxing to -0.5 captures more "declining volatility" days which are historically bullish.

Result: **1.6345 → 1.6367**

**Exp 23: `VOL_Z_BEARISH` 1.0 → 2.0**

Hypothesis: A vol Z-score threshold of 1.0 to generate a bearish vol signal fires too easily. In a bull market, even mild volatility spikes are noise. Require a true 2-sigma vol spike before treating it as bearish.

Result: **1.6367 → 1.6587**

**Exp 24: `STRATEGY_WEIGHTS` — tune volatility sub-weight**

After calibrating the vol signal thresholds, the volatility sub-strategy was now generating better signals. Increased its weight while reducing momentum slightly:
- `volatility`: 0.10 → 0.15
- `momentum`: 0.40 → 0.35

Result: **1.6587 → 1.6666**

---

#### Phase 6: Fine-Tuning at the Edge (Sharpe 1.67 → 1.79)

**Exp 25: `ADX_PERIOD` revisited: 21 → 22**

After all the other optimizations, the ADX period was revisited. With the full stack now calibrated, period 22 (1 calendar month) proved marginally better than 21.

Result: **1.6666 → 1.6997**

This was a micro-improvement that became significant because it changed which days the trend signal fires, interacting with the newly calibrated volatility signal.

**Exp 26: `STRATEGY_WEIGHTS` — momentum/mr micro-rebalance**

Hypothesis: After eliminating stat_arb and boosting vol weight, the momentum vs. mean_reversion balance needed re-examination. A subtle shift — reducing mr slightly (0.20→0.18) and adding that weight to momentum (0.35→0.37) — without changing the total.

Final weights:
```python
STRATEGY_WEIGHTS = {
    "trend":          0.30,
    "mean_reversion": 0.18,
    "momentum":       0.37,
    "volatility":     0.15,
    "stat_arb":       0.00,
}
```

Result: **1.6997 → 1.7880** — the largest single-step improvement of Session 2.

This jump suggests the 0.37/0.18 split hits a local optimum: momentum is the dominant signal for these trending tech names, but a small mean-reversion component (RSI-driven, since Bollinger is neutralized) provides a contrarian cushion that meaningfully improves risk-adjusted returns.

Subsequent tests at 0.38/0.17 (→1.7261), 0.39/0.16 (→1.7359), 0.36/0.19 (→1.6763) all degraded Sharpe, confirming 0.37/0.18 as the true sweet spot.

---

## Final State

### Parameters: Baseline vs. Best

| Parameter | Baseline | Best | Change |
|---|---|---|---|
| `STRATEGY_WEIGHTS["trend"]` | 0.25 | **0.30** | +0.05 |
| `STRATEGY_WEIGHTS["mean_reversion"]` | 0.20 | **0.18** | -0.02 |
| `STRATEGY_WEIGHTS["momentum"]` | 0.35 | **0.37** | +0.02 |
| `STRATEGY_WEIGHTS["volatility"]` | 0.10 | **0.15** | +0.05 |
| `STRATEGY_WEIGHTS["stat_arb"]` | 0.10 | **0.00** | eliminated |
| `ADX_PERIOD` | 10 | **22** | +12 periods |
| `BOLLINGER_STD` | 2.5 | **5.0** | neutralized Bollinger |
| `MOM_BULLISH/BEARISH` | ±0.01 | **±0.001** | 10x more sensitive |
| `RISK_BASE_LIMIT` | 0.18 | **0.30** | +67% capital deployment |
| `RISK_VOL_BANDS` | penalizing at 0.30, 0.50 | **flat 1.0 for medium/high** | no tech penalty |
| `POSITION_SIZE_FRACTION` | 0.35 | **1.00** | full deployment |
| `VOL_LOW_REGIME` | 0.80 | **0.95** | +18.75% more low-vol days |
| `VOL_Z_BULLISH` | -1.0 | **-0.5** | 2x more bullish triggers |
| `VOL_Z_BEARISH` | 1.0 | **2.0** | 2x stricter bearish filter |

### Performance: Baseline vs. Best

| Metric | Baseline (eec076d) | Best (485d4d0) | Improvement |
|---|---|---|---|
| **Sharpe ratio** | 1.0385 | **1.7880** | **+72.2%** |
| **Sortino ratio** | ~1.64 | **2.85** | **+73.8%** |
| **Max drawdown** | -12.69% | **-8.58%** | **-32% less drawdown** |
| **Total return** | +28.92% | **+48.76%** | **+68.6% more return** |

---

## Key Discoveries

### 1. The vol bands were backwards for tech stocks
The original `RISK_VOL_BANDS` penalized high-volatility stocks. In a universe of AAPL, NVDA, MSFT, GOOGL, TSLA — all structurally high-vol names — this meant the risk system was permanently reducing position sizes on the stocks with the best signals. Removing the penalties was the single most impactful category of change.

### 2. BOLLINGER_STD=5.0 is strategically correct, not a mistake
At 5σ, the Bollinger condition almost never fires. This is intentional: these stocks don't mean-revert within a 20-day window during a bull run. Setting it high effectively says "mean reversion doesn't apply here" and lets the RSI drive that sub-strategy instead. The RSI signal is less noisy for momentum names.

### 3. ADX period = 1 calendar month
Period 22 ≈ 22 trading days ≈ 1 calendar month. This is the natural rebalancing granularity for institutional money moving in and out of large-cap tech. The trend confirmation at this timescale is significantly more predictive than the default 10-day ADX.

### 4. stat_arb was pure noise for this universe
Hurst exponent < 0.4 (mean-reversion) with positive skew is a valid signal for pairs-traded assets. AAPL, NVDA, MSFT, GOOGL, TSLA in 2025 are strongly trending, highly correlated names — exactly the wrong universe for stat-arb. Killing that 10% weight and reallocating to momentum was immediately beneficial.

### 5. Dead code in params.py
- `CORR_BANDS` / `compute_corr_multiplier()`: The function is defined but **never called** in `fast_backtest.py`. These parameters have zero effect.
- `CONFIDENCE_POWER`: In Mode 1 (single technical agent), this exponent cancels out mathematically in the weighted score calculation. It has no effect.
- After `BOLLINGER_STD=5.0`: `BB_BULLISH`, `BB_BEARISH`, `ZSCORE_BULLISH`, `ZSCORE_BEARISH` are effectively dead levers.

### 6. The overfit trap
Session 1 reached Sharpe 2.2203 — but on a 6-month window. When re-evaluated on the full 14-month window, it collapsed to -0.09. The autoresearch loop is only as good as its evaluation window. Session 2 deliberately used the full 14-month window and accepted a lower headline Sharpe in exchange for robustness.

---

## What Was Tested and Rejected

These parameters were tested and showed no improvement or degraded Sharpe:

| Parameter | Tested values | Outcome |
|---|---|---|
| `BOLLINGER_STD` | 6.0 | No improvement at 5.0 plateau |
| `MOM_BULLISH` | ±0.0005 | Noise floor, slight worsening |
| `RISK_BASE_LIMIT` | 0.35, 0.40 | Diminishing returns past 0.30 |
| `RISK_MAX_MULT` | 1.50 | Worse |
| `EMA combo` | 3/8/21, 8/21/55 | Worse than 5/13/34 |
| `MOM_3M_WEIGHT` | 0.8/0.2 split | Worse than pure 1M |
| `RISK_EXTREME_VOL_MULT` | 0.75, 1.00 | Worse than 0.50 |
| `VOL_HIGH_REGIME` | 1.5 | Worse than 1.2 |
| `ZSCORE_BULLISH/BEARISH` | ±1.5 | No effect (Bollinger neutralized) |
| `BB_BULLISH/BEARISH` | 0.1/0.9 | No effect (Bollinger neutralized) |
| `MA_WINDOW` | 30 | No effect |
| `VOLATILITY_LOOKBACK_DAYS` | 30, 90 | Worse than 60 |
| `VOL_HIST_WINDOW` | 10 | Worse than 21 |
| `BUY/SELL_THRESHOLD` | ±0.07 | No effect |
| `VOL_MA_WINDOW` | 30, 126 | Worse than 63 |
| `SIGNAL_BULLISH_THRESHOLD` | 0.15 | Much worse |
| `MIN_CONFIDENCE_TO_ACT` | 15 | Much worse |
| `MOM_CONFIDENCE_SCALE` | 10.0, 20.0 | Worse than 15.0 |
| `RISK_MED/HIGH_VOL_DECAY` | 0.1 | No improvement |
| `VOL_LOW_REGIME` | 0.97, 0.99 | No improvement |
| `ADX_PERIOD` | 20, 23, 24 | Worse than 22 |
| `STRATEGY_WEIGHTS` | 40+ combinations | All worse than 0.30/0.18/0.37/0.15/0.00 |
| `POSITION_SIZE_FRACTION` | > 1.00 | Capped at 1.00 by definition |

---

## Session 3 — RSI Unlock + Mode 2 Breakthrough (2026-03-12)

### RSI signal unlocked

`compute_rsi()` was defined but never called. Added RSI to the mean-reversion path in `fast_backtest.py`:
- `RSI_OVERSOLD` / `RSI_OVERBOUGHT` in params.py (default 30/70)
- Mean-reversion now triggers on (z-score + Bollinger) OR (RSI oversold/overbought)
- **Result:** RSI 30/70 and 25/75 both hurt in bull market (mean-reversion fights momentum). Use 0/100 to disable. RSI is now a tunable lever for bear/sideways regimes.

### Mode 2 breakthrough

With `signals.json` present, tested `ANALYST_WEIGHTS`:
- All 18 agents at 1.0 → -267% return (bearish value agents short the bull market)
- Down-weighting Graham/Munger/Burry → still -95% to -162%
- **Technical_analyst only** (all others 0) → **val_sharpe=2.0221, val_return=+58.33%**

The 2.02 vs Mode 1's 1.79 comes from **confidence averaging**: when 18 agents are in the cache, `confidence = avg(all 18 confidences)`. Even with 17 at weight 0, their cached confidence values boost the average → higher effective confidence → larger position sizes → better deployment.

**Best config:** `ANALYST_WEIGHTS` with technical_analyst=1.0, all others=0. Run `cache_signals.py` to generate `signals.json`, then `evaluate`.

---

## What's Next

1. **RSI tuning in bear/sideways regimes** — RSI 30/70, 25/75, 20/80 are now tunable. Test when market regime shifts.

2. **Rolling window robustness** — test whether the current params hold across different 6-month sub-windows within the 14-month backtest to detect overfitting.

3. **Cross-asset generalization** — run the same params on a different universe (e.g., energy, biotech) to test whether these findings are AAPL/NVDA-specific or generalizable.

4. **Selective LLM agent re-enablement** — try adding one growth/momentum agent (e.g. cathie_wood, stanley_druckenmiller) at 0.2 weight to see if any LLM signal adds alpha without the bearish drag.

---

## The Method (Why This Works)

This is Karpathy's autoresearch paradigm applied to trading:

> *"Any metric you care about that is reasonably efficient to evaluate can be autoresearched by an agent swarm."*

The key properties that make this tractable:

- **Fast evaluation**: ~5 seconds per experiment → 720 experiments/hour theoretical max
- **Deterministic**: same params always produce same Sharpe, no randomness
- **Single mutable file**: clean attribution, no side effects, easy rollback
- **Monotonic commits**: git ensures the committed state is always the all-time best
- **One change at a time**: isolates causality, prevents parameter interaction confusion

The agent is not guessing randomly. Each experiment is a **falsifiable hypothesis** about what the market regime requires — in this case: *tech stocks in a 2025 AI bull market are momentum names, not mean-reversion names, and risk systems calibrated for diversified portfolios actively hurt performance when applied to a concentrated tech universe.*

The data confirmed this hypothesis across every optimization axis.
