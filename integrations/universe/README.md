# Universe Selection

Data-driven replacement for the hardcoded stock list: scores every tradable
US equity and selects a diversified universe (default 127 names) optimized
for **profitable, repeatable trading opportunities** — not just size or
liquidity.

## Quick start

```bash
# Build today's universe (writes data/universe/YYYY-MM-DD.json)
poetry run alpaca-fund universe build

# Faster build without the Alpha Learnability replay
poetry run alpaca-fund universe build --skip-learnability

# Inspect it
poetry run alpaca-fund universe show

# Trade it (instead of --ticker)
poetry run alpaca-fund run --universe latest --broker alpaca
poetry run alpaca-fund daemon --universe latest --broker alpaca

# Validate against baselines (LLM-free backtest)
poetry run alpaca-fund universe backtest --start-date 2026-03-01 --size 20
```

Requires `ALPACA_API_KEY`/`ALPACA_SECRET_KEY` (asset master + bars) plus the
configured fundamentals provider (`DATA_PROVIDER=composite` with Finnhub, or
Financial Datasets).

## Pipeline

```
Alpaca asset master (~10k active, tradable US equities)
  -> Stage 0  cheap gates: exchange, common shares only, price >= $5,
              252+ bars, median dollar volume >= $5M   (bulk bars, disk-cached)
  -> Stage 1  price-based factor scoring on all survivors
  -> Stage 2  shortlist (top 300): fundamentals, earnings, news,
              Alpha Learnability replay; names with zero fundamentals
              filings are dropped (catches funds/trusts that slip past
              Stage 0 name markers, e.g. "Invesco QQQ Trust")
  -> Select   greedy by composite score under sector cap (20%) and
              pairwise correlation limit (0.90)
  -> data/universe/YYYY-MM-DD.json (full factor breakdown per ticker)
```

Everything takes an explicit `as_of` date and only uses data available on
that date, so historical universes can be built for backtests without
look-ahead bias.

## Factors

All factors emit an oriented raw value (higher = better), are winsorized and
z-scored cross-sectionally, then combined by weight. Weights live in
`UniverseConfig.factor_weights` (env: `UNIVERSE_FACTOR_WEIGHTS=name:w,...`);
weight 0 disables a factor.

| Theme | Factors |
|---|---|
| Liquidity / cost | `dollar_volume`, `amihud_illiquidity`, `estimated_spread` (Corwin-Schultz from daily bars), `zero_volume_days` |
| Tradable volatility | `volatility_band` (sweet spot 25-60% annualized), `vol_stability` (vol-of-vol) |
| Predictability | `autocorrelation`, `variance_ratio`, `efficiency_ratio`, `stat_stability` (structure must persist across half-windows) |
| Data quality | `bar_coverage`, `listing_age`, `fundamentals_coverage`, `news_coverage` |
| Event risk | `tail_risk` (kurtosis), `max_gap`, `earnings_gap_risk`, `earnings_proximity` |
| Crowding / shortability | `volume_surge`, `momentum_extremeness`, `shortability` (broker borrow flags) |
| Alpha Learnability | `alpha_learnability` (weight 2.0 — the headline factor) |

To add a factor: subclass `Factor` in `factors/`, register it in
`factors/__init__.py`, give it a weight. That's the whole contract.

## Alpha Learnability

Replays the **rule-based analysts** (technicals, fundamentals, valuation,
growth, sentiment — the exact agent functions the light trading cycle runs,
zero LLM cost) at ~monthly checkpoints over the trailing 2 years, then
scores each stock on how well our own pipeline predicted it:

- **IC** — Spearman correlation of the confidence-weighted signal vote vs
  5- and 21-day forward returns
- **Hit rate** — directional accuracy of non-neutral signals
- **Regime consistency** — IC per market regime (SPY up/down x high/low
  vol); the score is shrunk by sample size (`n/(n+20)`) and penalized by
  cross-regime IC dispersion, so *consistently right* beats *occasionally
  spectacular*

Replayed signals are cached per ticker in `data/universe/signals/`, so
rebuilds are incremental. The replay is the expensive part of a build —
`--skip-learnability` drops it, or shrink `--stage2-size`.

## Validation backtests

`alpaca-fund universe backtest` compares three universes with the
deterministic light-cycle agent (no LLM calls):

1. `ranked` — this system, built as of the backtest **start** date
2. `current` — the legacy hardcoded 100-stock list (`v2/backtesting/__main__.py`)
3. `dollar_volume` — naive top-N by median daily dollar volume

Reports return, Sharpe, Sortino, max drawdown, and SPY benchmark side by
side. `--size` shrinks all variants for fast iteration (analyst replay costs
scale with tickers x days against provider rate limits).

## Known limitations

- **Survivorship bias**: the candidate pool is today's asset master, so
  historical builds miss delisted names. Affects `ranked` and
  `dollar_volume` variants comparably in backtests.
- **No short-interest feed**: crowding uses price/volume proxies; borrow
  flags (`shortable`, `easy_to_borrow`) are current-state, not point-in-time.
- **No historical quotes**: spread is estimated from daily high/low bars.
- **Sector data is current-state** (provider company facts).

## Configuration

Every knob is env-overridable — see `config.py`. Highlights:

| Env var | Default | Meaning |
|---|---|---|
| `UNIVERSE_SIZE` | 127 | final universe size |
| `UNIVERSE_MIN_DOLLAR_VOLUME` | 5000000 | Stage 0 median dollar-volume gate |
| `UNIVERSE_STAGE2_SIZE` | 300 | shortlist for expensive factors |
| `UNIVERSE_SECTOR_CAP_PCT` | 0.20 | max share of one sector |
| `UNIVERSE_MAX_CORRELATION` | 0.90 | pairwise correlation limit |
| `UNIVERSE_REQUIRE_FUNDAMENTALS` | true | drop shortlist names with no fundamentals filings |
| `UNIVERSE_LEARNABILITY` | true | enable the replay |
| `UNIVERSE_FACTOR_WEIGHTS` | — | `name:weight,...` overrides |
