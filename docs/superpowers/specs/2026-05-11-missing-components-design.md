# Design: Four Missing Components for AI Hedge Fund

**Date:** 2026-05-11
**Scope:** Four self-contained additions that close the most critical gaps identified in the gap analysis — all implementable without paid external APIs.

---

## 1. Persistent State / Database

### Goal
Give the system memory across runs. Right now every execution starts from zero; no audit trail, no position continuity, no way to review what the system decided and why.

### Storage
- **Engine:** SQLite (`data/hedge_fund.db`)
- **ORM:** SQLAlchemy (already a transitive dependency via LangChain)

### Tables

**`portfolio_snapshots`**
```
id          INTEGER PRIMARY KEY
run_id      TEXT NOT NULL
date        TEXT NOT NULL         -- YYYY-MM-DD
cash        REAL NOT NULL
long_value  REAL NOT NULL
short_value REAL NOT NULL
nlv         REAL NOT NULL
positions   TEXT NOT NULL         -- JSON blob: {ticker: {shares, cost_basis, side}}
created_at  TEXT NOT NULL
```

**`trade_log`**
```
id          INTEGER PRIMARY KEY
run_id      TEXT NOT NULL
date        TEXT NOT NULL
ticker      TEXT NOT NULL
action      TEXT NOT NULL         -- buy | sell | short | cover | hold
quantity    INTEGER NOT NULL
price       REAL NOT NULL
cash_impact REAL NOT NULL
created_at  TEXT NOT NULL
```

**`decision_log`**
```
id          INTEGER PRIMARY KEY
run_id      TEXT NOT NULL
date        TEXT NOT NULL
ticker      TEXT NOT NULL
agent       TEXT NOT NULL
signal      TEXT NOT NULL         -- bullish | bearish | neutral
confidence  REAL NOT NULL
reasoning   TEXT NOT NULL
created_at  TEXT NOT NULL
```

### New Module
`src/data/database.py` — handles all DB init, session management, and write helpers. Imported by the backtesting engine and the live runner.

### Integration Points
- `src/backtesting/engine.py` — writes snapshots and trades after each day
- `src/agents/portfolio_manager.py` — writes decision_log entries per agent signal
- `src/main.py` — generates a `run_id` (UUID) at startup, passes it through state

### What it does NOT do
- Does not replace in-memory portfolio state during a run (performance)
- Does not implement multi-user isolation
- Does not persist LLM API call costs

---

## 2. SEC EDGAR NLP Agent

### Goal
Give analysts access to the richest source of qualitative signal: the company's own words in SEC filings. The agent reads 10-K (annual), 10-Q (quarterly), and 8-K (material events) and returns a structured signal.

### Data Source
SEC EDGAR full-text search API — free, no API key required.
- Base URL: `https://efts.sec.gov/EFTS/hits.hits`
- Filing viewer: `https://www.sec.gov/cgi-bin/browse-edgar`
- Rate limit: 10 req/sec (public)

### Sections Analyzed
| Filing | Sections Extracted |
|--------|--------------------|
| 10-K   | Item 7 (MD&A), Item 1A (Risk Factors), Item 7A (Quantitative Risk) |
| 10-Q   | Item 2 (MD&A), Item 1A (Risk Factors — changes only) |
| 8-K    | Full text — material events (earnings, M&A, management changes, guidance) |

### Extraction Strategy
- Map ticker to CIK via SEC's company tickers JSON
- Fetch EDGAR XBRL filing index for most recent 10-K, 10-Q, 8-K
- Download HTML filing, extract target sections via heading patterns
- Truncate to token budget (max 6,000 tokens per filing across sections)
- Pass to LLM with analyst prompt

### LLM Prompt Design
The agent is styled as a qualitative analyst reading a filing for the first time:
- What is management's tone — optimistic, cautious, defensive?
- Are there new or escalating risk factors vs. prior filing?
- What forward guidance language appears?
- Are there material events (8-K) that change the investment thesis?

### Output (same interface as all other agents)
```python
{
  "signal": "bullish" | "bearish" | "neutral",
  "confidence": 0–100,
  "reasoning": str  # 2-3 key findings from the filings
}
```

### New Files
- `src/agents/sec_filings.py` — the analyst agent
- `src/tools/sec_api.py` — EDGAR fetch utilities (CIK lookup, filing index, section extraction)

### Integration
Registered in `src/graph/agents.py` (or equivalent analyst registry) with display name `"SEC Filings Analyst"`. Available as an optional analyst like all others.

### Limitations
- US public companies only (requires CIK mapping)
- 45–90 day filing lag after quarter-end
- Section extraction is heuristic (heading-based); rare filing formats may need fallback to full-text truncation

---

## 3. Regime Detection Agent

### Goal
Classify the current market environment before analysts run. The regime feeds into the Risk Manager as a top-down constraint, preventing the system from taking full-size positions into a deteriorating market.

### Signals Used
All computed from SPY price history, which the system already fetches:

| Signal | Computation | Regimes |
|--------|-------------|---------|
| Trend | SPY 50-day MA vs 200-day MA | Bull / Bear |
| Volatility | 20-day realized vol of SPY daily returns (annualized) | Low (<15%) / Elevated (15–30%) / Crisis (>30%) |
| Momentum | SPY 3-month (63-day) return | Risk-On (>2%) / Neutral / Risk-Off (<−2%) |

### Regime Classification Logic
```
Bull  = Trend=Bull AND Momentum=Risk-On AND Vol≠Crisis
Bear  = Trend=Bear OR Momentum=Risk-Off
High-Vol = Vol=Crisis (overrides trend)
Risk-Off = Bear AND (Vol=Elevated OR Vol=Crisis)
```

Priority: High-Vol > Risk-Off > Bear > Bull

### Risk Manager Integration
The regime multiplier is applied after the existing volatility + correlation adjustments:

| Regime | Position Limit Multiplier | Long Constraint |
|--------|--------------------------|-----------------|
| Bull | 1.00× | None |
| Bear | 0.70× | Reduce new longs |
| High-Vol | 0.50× | No new longs |
| Risk-Off | 0.40× | No new longs |

### New Files
- `src/agents/regime_detector.py` — computes regime, exposes `detect_regime(prices: dict) -> RegimeState`
- `src/data/models.py` — add `RegimeState` dataclass: `{regime: str, trend: str, vol_level: str, momentum: str}`

### Integration Points
- `src/graph/workflow.py` (or equivalent) — regime detection runs as the first node before any analyst
- `src/agents/risk_manager.py` — receives `RegimeState` in its input, applies multiplier to position limits

### Backtesting
Regime is computed on each backtest day using only prices available up to that date — no look-ahead bias.

---

## 4. Confidence-Weighted Signal Aggregation

### Goal
Replace majority vote with a numerically sound aggregation that accounts for how strongly each analyst believes their signal. A 90%-confidence bearish signal should outweigh a 55%-confidence bullish signal.

### Current Behavior (to replace)
Simple count: bullish_count > bearish_count → "bullish majority." Confidence scores exist but are not used in aggregation.

### New Aggregation Algorithm

**Step 1 — Directional encoding:**
```
bullish  → +1
neutral  →  0
bearish  → −1
```

**Step 2 — Confidence weighting:**
```
weighted_score(agent) = direction × (confidence / 100)
```

**Step 3 — Normalized aggregate:**
```
aggregate = sum(weighted_scores) / n_analysts
# Range: [-1, +1]
```

**Step 4 — Signal + confidence mapping:**
```
aggregate > 0.15  → bullish,  confidence = aggregate × 100
aggregate < -0.15 → bearish,  confidence = |aggregate| × 100
else              → neutral,  confidence = (1 - |aggregate|) × 100
```

**Step 5 — Position sizing:**
Position size = risk_manager_limit × min(aggregate_confidence / 100, 1.0)
- 0.85 conviction → 85% of limit
- 0.52 conviction → 52% of limit

### Where This Lives
New function `aggregate_signals(signals: list[AgentSignal]) -> AggregatedSignal` in `src/agents/portfolio_manager.py`, replacing the current signal counting logic.

The portfolio manager LLM prompt is updated to receive the weighted aggregate (score, direction, top bull/bear agents) rather than a raw signal count.

### Backward Compatibility
The `--analysts-all` and `--analysts` flags continue to work unchanged. The aggregation function is purely internal.

---

## Implementation Order

1. **Database** — foundational, other components write to it
2. **Regime Detection** — no external deps, pure computation
3. **Confidence Calibration** — modifies existing code (smaller surface)
4. **SEC Filings Agent** — largest new component, isolated, external API

---

## Out of Scope (this spec)

- Real-time / intraday data feeds
- Options and derivatives
- Live broker integration
- Multi-asset coverage (FX, commodities, bonds)
- Analyst historical accuracy tracking
- PostgreSQL migration
