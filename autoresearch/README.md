# Autoresearch — Autonomous AI Parameter Optimization

> *"Any metric you care about that is reasonably efficient to evaluate can be autoresearched by an agent swarm."*
> — Andrej Karpathy

---

## The Insight

Karpathy let an AI agent optimize his neural net training code for 2 days. It ran 700 experiments autonomously. Found 20 improvements he'd missed after months of manual tuning. 11% performance gain.

The agent found bugs. Tuned hyperparameters. Discovered missing regularization. Planned its own experiments based on prior results.

What did Karpathy do? He wrote `program.md`.

He described the task, the evaluation metric, and the rules. The agent did the rest.

This is the key reframe: **you're not writing code anymore, you're programming the program.** The human's job is to define what "better" means and make it fast to measure. The agent's job is to find it.

That's what this system does — for trading strategy optimization.

---

## Where This Lives

This system is the research engine underneath **[Dexter](https://github.com/eliza420ai-beep/dexter)** — a thesis-driven portfolio that lives in your terminal.

The full loop works like this:

```
SOUL.md (your convictions)
  → Dexter reads thesis, builds sleeves (80% BTC / 10% stocks / 10% on-chain)
  → AI Hedge Fund runs 18 analyst agents against the same names
      → challenges conviction before it gets trusted
      → pokes holes in the thesis
  → Autoresearch sharpens both overnight
      → tunes the AI Hedge Fund's technical parameters (this repo)
      → improves Dexter's own reasoning via MLX on Apple Silicon
  → Repeat
```

**SOUL.md is the origin.** It defines the thesis — the AI infrastructure supply chain, the conviction tiers, the regime overlay. Everything downstream serves that thesis or challenges it. The AI Hedge Fund is the second-opinion engine: 18 agents that don't know your thesis and don't care — they just run the numbers. Autoresearch is what makes both systems sharper over time without human intervention.

---

## This System

Inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch) and its [Apple Silicon MLX port](https://github.com/trevin-creator/autoresearch-mlx).

An autonomous loop that lets an AI agent run hundreds of experiments to optimize the AI Hedge Fund's trading parameters — technical indicators, strategy weights, risk limits, analyst trust, and portfolio construction rules — while you sleep.

The metric is **Sharpe ratio**. The agent tunes `params.py`. Everything else is fixed.

```
┌─────────────────────────────────────────────────────┐
│  Step 0: CACHE (one-time, ~30 sec for prices only)  │
│  Download price data for your tickers.               │
│  Optionally cache full agent signals (~30 min).      │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│  AUTORESEARCH LOOP (overnight, autonomous)           │
│                                                      │
│  1. AI reads program.md                              │
│  2. AI reads results.tsv (prior experiments)         │
│  3. AI forms a hypothesis                            │
│  4. AI modifies params.py (one change at a time)     │
│  5. Run: poetry run python -m autoresearch.evaluate  │
│     → loads cached data                              │
│     → recomputes technical signals with new params   │
│     → runs fast deterministic backtest               │
│     → outputs val_sharpe=X.XXXX                      │
│  6. If better → git commit (keep)                    │
│     If worse  → git checkout (revert)                │
│  7. Repeat                                           │
│                                                      │
│  ~5-15 seconds per experiment                        │
│  ~300+ experiments per hour                          │
│  ~2000+ experiments overnight                        │
│  Zero LLM calls during backtest. Zero API calls.     │
└──────────────────────────────────────────────────────┘
```

The agent doesn't just enumerate possibilities — it reads its own history, builds intuition about the parameter landscape, and directs exploration accordingly. That's the difference between a grid search and a research agent.

---

## Quick Start

### 1. Cache price data (required, ~30 seconds)

```bash
poetry run python -m autoresearch.cache_signals --prices-only \
  --tickers AAPL,NVDA,MSFT,GOOGL,TSLA \
  --start 2025-06-01 --end 2025-12-01
```

### 2. Run a baseline experiment

```bash
poetry run python -m autoresearch.evaluate
```

**Mode 1 (prices-only cache, no `signals.json`):**
```
val_sharpe=0.4523
val_sortino=0.6789
val_max_dd=-12.34
val_return=8.56
elapsed_ms=3200
```

**Mode 2 (full signal cache present):** scores will differ because 18 agents are averaged.
If you see `val_sharpe=0.0, val_sortino=-15.87, val_return=0.0` — the system held cash the entire backtest. See [Diagnosing Zero Returns](#diagnosing-zero-returns).

### 3. Start the autonomous loop

Point Claude Code (or any AI coding agent) at `autoresearch/program.md` and give it one instruction:

```
Open program.md and follow the instructions. Run experiments until I tell you to stop.
```

That's it. Come back in the morning.

Or run experiments manually:
1. Edit `autoresearch/params.py`
2. Run `poetry run python -m autoresearch.evaluate`
3. If Sharpe improved, commit. If not, revert.
4. Repeat.

---

## Files

| File | Purpose | Who modifies it |
|------|---------|----------------|
| `params.py` | All tunable knobs | The AI agent (only file it touches) |
| `evaluate.py` | Runs one experiment, prints metric. Use `--start`/`--end` for OOS tuning | Nobody (fixed) |
| `fast_backtest.py` | Deterministic backtester (no LLM) | Nobody (fixed) |
| `cache_signals.py` | One-time data caching | Nobody (run once) |
| `oos_check.py` | Out-of-sample validation (first vs second half) | Nobody (run to check robustness) |
| `cross_asset_check.py` | Cross-asset test (tech vs energy) | Nobody (run to check generalization) |
| `program.md` | AI agent instructions | Nobody (fixed) |
| `results.tsv` | Running experiment log | Appended automatically |
| `cache/` | Cached price data + signals | Generated by cache_signals.py |

**Cache behavior:** `signals.json` resumes (skips already-cached dates). `prices.json` is **overwritten every run** — a backup is saved to `prices.json.bak` first. Always use `--start`/`--end` matching `params.BACKTEST_START`/`BACKTEST_END` so the cache covers the full backtest window.

The human-defined constraint: the agent may only touch `params.py`. Everything else is the evaluation harness — fixed, trusted, deterministic. This separation is what makes the loop trustworthy.

---

## Two Modes

### Mode 1: Technical-Only (free, instant)

Only needs cached price data. The autoresearch loop tunes:
- Technical indicator parameters (EMA windows, RSI periods, etc.)
- Strategy weights (trend vs momentum vs mean reversion vs volatility)
- Signal classification thresholds
- Risk parameters (volatility bands, correlation multipliers, position limits)
- Portfolio decision rules (buy/sell/short thresholds, confidence gates)

This is sufficient to find significant improvements and runs completely free. Start here.

### Mode 2: Full-Signal (needs one LLM run)

**Important:** `cache_signals` defaults to **OpenRouter** (`z-ai/glm-4.5-air`) — ~$3–5 for full run, no rate limits. Set `OPENROUTER_API_KEY` in `.env`. Free models (`:free` suffix) are rate-limited (16/min); the code auto-throttles but runs ~6h for full cache. Defaults match the backtest window (2025-01-02 → 2026-03-07). If you have an older cache built for a shorter range, rebuild it to get sharpe≈2.02:
```bash
rm autoresearch/cache/signals.json
poetry run python -m autoresearch.cache_signals
```

If you also run the full signal cache (defaults: OpenRouter + glm-4.5-air):

```bash
poetry run python -m autoresearch.cache_signals \
  --tickers AAPL,NVDA,MSFT,GOOGL,TSLA
```

This caches all 18 analyst signals (Buffett, Munger, etc.) for every business day.
The autoresearch loop can then also tune analyst trust weights — discovering which agents add alpha and which add noise.

---

## What Gets Tuned

| Category | Parameters | Impact |
|----------|-----------|--------|
| Strategy weights | trend, momentum, mean reversion, volatility, stat arb | Which technical strategies to trust |
| Indicator params | EMA windows, RSI periods, Bollinger width, momentum lookbacks | Signal sensitivity and noise |
| Signal thresholds | Bullish/bearish classification cutoffs | How aggressive signals are |
| Risk management | Vol bands, correlation multipliers, base position limits | Position sizing |
| Portfolio rules | Buy/sell/short thresholds, position size fraction, min confidence | Trade generation |
| Analyst weights | Per-agent trust levels (18 agents) | Who to listen to (Mode 2 only) |

---

## Why This Works

The standard objection to automated optimization is overfitting. A grid search will find parameters that look great in-sample and fall apart out-of-sample.

This system avoids it through:

1. **One change at a time.** Clean attribution. The agent knows what caused each improvement.
2. **Hypothesis-driven search.** The agent reads results, builds intuition, and directs exploration — it's not randomly sampling the space.
3. **Git as a ratchet.** Every improvement is committed. Every regression is reverted. The system can only move forward.
4. **Human-defined evaluation.** You choose the backtest window, the tickers, the metric. The agent can't game a metric it doesn't control.

The analogy to neural net training holds: a well-designed evaluation harness that's fast to run is the prerequisite. Once you have that, autoresearch is just letting the agent do the rest.

---

## The autoresearch-MLX Connection

This system follows the same design principles as [autoresearch-mlx](https://github.com/trevin-creator/autoresearch-mlx). MLX is applied twice in the full stack:

1. **Here** — optimizing the AI Hedge Fund's technical trading parameters (this repo)
2. **In Dexter** — sharpening Dexter's own reasoning: conviction scoring, theta strike selection, quarterly audit quality — running short 5-minute experiments on Apple Silicon, no GPU, no cloud, no bill

| autoresearch-mlx | ai-hedge-fund autoresearch | Dexter autoresearch |
|---|---|---|
| `train.py` (single mutable file) | `params.py` | Dexter's reasoning modules |
| `val_bpb` (bits per byte) | `val_sharpe` (Sharpe ratio) | BTC/SPY/GLD benchmark delta |
| 5-min training on Apple Silicon | 5-15 sec backtest (pure Python) | 5-min MLX run on Apple Silicon |
| Neural net hyperparameters | Trading strategy parameters | Conviction scoring + options logic |
| Keep/revert via git | Keep/revert via git | Keep/revert via git |
| ~8 experiments/hour | ~300 experiments/hour | ~8-12 experiments/hour |

The structure is identical across all three. **The autoresearch loop is domain-agnostic.** What changes is the evaluation harness and the mutable file — not the loop itself.

That's the infrastructure point: the same pattern that improved Karpathy's neural net training applies to trading parameter tuning, which applies to thesis-driven portfolio reasoning. One loop. Any metric that's fast to evaluate.

---

## Diagnosing Zero Returns

If you see `val_sharpe=0.0, val_sortino=-15.87, val_return=0.0`, the portfolio held 100% cash. `val_sortino = -√252 = -15.874` is the mathematical fingerprint: every daily return was exactly 0.0 (cash earns nothing; the risk-free rate creates constant negative excess; standard deviation is 0 → Sharpe undefined → 0; sortino = -√252 exactly).

**Why it happens in Mode 2 (full signal cache):**

`signals.json` contains 18 LLM agents. The backtest aggregates all 18 with equal weight. In Mode 2:

- Weighted scores typically range **-0.65 to +0.10** (LLM agents tend to be net bearish on tech)
- `BUY_THRESHOLD = 0.05` — occasionally crossed, but barely
- `SHORT_THRESHOLD` default was `-0.90` — impossible to reach with 18-agent averaging (max bearish is ~-0.65)
- Result: never buys (not bullish enough), never shorts (not bearish enough), never sells (no positions)

**Fix already applied in `params.py`:** `SHORT_THRESHOLD` is now `-0.15`, matching the actual range of Mode 2 aggregate scores. Re-run to verify:

```bash
poetry run python -m autoresearch.evaluate
```

**To test Mode 1 (technical only) instead:**

```bash
# Move the signals cache out of the way
mv autoresearch/cache/signals.json autoresearch/cache/signals.json.bak
poetry run python -m autoresearch.evaluate
# Restore when done
mv autoresearch/cache/signals.json.bak autoresearch/cache/signals.json
```

Mode 1 uses only the recomputed technical indicators (1 agent, scores ±0.2–1.0), which are well-calibrated for the default thresholds. This is the recommended starting point.

**The deeper issue:**

In Mode 2, `SHORT_THRESHOLD` and `BUY_THRESHOLD` need to account for the 18-agent averaging. Scores are ~18× more compressed than in Mode 1. This is exactly what autoresearch should find — but only once the system can actually execute trades to measure. The `-0.15` fix unblocks it.

---

## Tips

- **Start with prices-only mode.** It's free and fast. Run 100+ experiments before investing in the full signal cache.
- **Use descriptive commit messages.** After an overnight run, you want to trace which changes helped most.
- **Check `results.tsv` periodically.** It shows the trajectory of improvements — both where you've been and where to look next.
- **Change the backtest window** in `params.py` to test robustness. A strategy that only works on one period is likely overfit.
- **The 5 free tickers** (AAPL, GOOGL, MSFT, NVDA, TSLA) are enough for parameter tuning. Add more tickers for validation after finding a strong configuration.
- **Let it run overnight.** The value compounds. An agent that has run 500 experiments has a much richer picture of the parameter landscape than one that has run 50.
- **Don't interrupt a good run.** If the trajectory is improving, let it continue. The agent is building intuition you can't replicate by checking in every hour.

---

## Multi-Sector Roadmap

The current autoresearch system is calibrated for **large-cap tech momentum** (AAPL, NVDA, MSFT, GOOGL, TSLA). Cross-asset testing confirms the strategy is **sector-specific**: the same params produce Sharpe 2.02 on tech and Sharpe 0.03 on energy.

The planned portfolio spans multiple behavioral clusters, each requiring its own parameter set:

| Sector | Tickers | Behavioral regime | Key param differences |
|--------|---------|------------------|-----------------------|
| **Mega-cap tech** | AAPL, NVDA, MSFT, GOOGL, TSLA | Momentum/trend | Tuned — Sharpe 2.02 |
| **Semicon equipment** | AMAT, ASML, LRCX, KLAC, TEL | Long capex cycle, order-book driven | **Tuned — Sharpe 1.86, OOS 2.35** |
| **Memory/storage** | MU, WDC, STX | Highly cyclical, volatile | **Baseline 2.44** (tech params generalize!) |
| **Power & infra** | VST, CEG, NRG | Utility-like, rate-sensitive | Baseline -0.02 → needs tuning |
| **EDA** | SNPS, CDNS | Long-duration compounder, low vol | Wide thresholds, very high MIN_CONFIDENCE |
| **Tokenization rails** | COIN, HOOD, CRCL | Crypto-correlated, high beta | Completely different regime |
| **Hyperscalers** | META, MSFT, AMZN, GOOGL | Momentum, AI capex driven | Similar to tech but more stable |
| **Foundry** | TSM | Geopolitical + capex cycle | Unique risk profile |

**The architecture implication:** as the universe expands, `params.py` will need to evolve into **per-universe param sets** — either multiple `params_<sector>.py` files or a params dict keyed by sector. The autoresearch loop can then tune each sector independently.

**When ready to expand:**
```bash
# Step 1: Cache prices for new sector
poetry run python -m autoresearch.cache_signals \
  --tickers AMAT,ASML,LRCX,KLAC,TEL \
  --prices-only \
  --prices-path prices_equipment.json

# Step 2: Baseline check (expect low Sharpe — current params aren't tuned for equipment)
poetry run python -m autoresearch.evaluate \
  --tickers AMAT,ASML,LRCX,KLAC,TEL \
  --prices-path prices_equipment.json

# Step 3: Run autoresearch loop with OOS check pointed at the new sector
# (requires per-sector params file — see roadmap)
```

**Overnight autoresearch (equipment):**

```bash
# 1. Read the program
cat autoresearch/program_equipment.md

# 2. Run the loop (or point an AI agent at program_equipment.md)
bash autoresearch/run_overnight_equipment.sh   # prints instructions

# 3. Each experiment
poetry run python -m autoresearch.evaluate --params autoresearch.params_equipment
# If better → git add autoresearch/params_equipment.py autoresearch/results_equipment.tsv && git commit -m "autoresearch[equip]: ..."
# If worse  → git checkout autoresearch/params_equipment.py
```

Equipment baseline to beat: **Sharpe 1.86, OOS 2.35**. Power and memory have `params_power.py` and `params_memory.py`; run with `--params autoresearch.params_power` or `--params autoresearch.params_memory`.
