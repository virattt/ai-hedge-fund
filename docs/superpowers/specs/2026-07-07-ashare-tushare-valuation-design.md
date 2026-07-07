# A-share Tushare valuation + Sina price failover — Design

**Date:** 2026-07-07
**Status:** Approved (pending written-spec review)
**Scope:** `src/tools/api_akshare.py`, new `src/tools/api_tushare.py`, `pyproject.toml`, tests

## 1. Context & problem

Live reproduction (2026-07-07, akshare 1.18.64 — already the latest PyPI release)
showed the A-share data layer is half-broken because **Eastmoney (`_em`) endpoints
forcibly close the connection**, while **Sina** endpoints work:

| akshare function | Source | Status |
|---|---|---|
| `stock_zh_a_spot_em` (all-market market-cap table) | Eastmoney | ❌ `RemoteDisconnected` (persistent, 2/2 retries failed) |
| `stock_zh_a_hist` (daily OHLCV) | Eastmoney | ❌ `RemoteDisconnected` (persistent) |
| `stock_individual_info_em` (per-ticker market cap) | Eastmoney | ❌ `RemoteDisconnected` |
| `stock_zh_a_daily` (daily OHLCV) | **Sina** | ✅ `(25, 9)` |
| `stock_financial_abstract` (metrics) | Sina | ✅ `(80, 104)` |
| `stock_financial_report_sina` (statements) | Sina | ✅ `(102, 83)` |

Consequences in the current code:

- `get_prices` → calls the broken `stock_zh_a_hist` → returns `[]`. **Prices are dead.**
- `get_market_cap` → primary (spot table) and fallback (`stock_individual_info_em`)
  are **both** Eastmoney → returns `None`. **Market cap is dead.**
- `get_financial_metrics` → the entire valuation block
  (`market_cap`, `price_to_earnings_ratio`, `price_to_book_ratio`,
  `price_to_sales_ratio`, `enterprise_value`) is hardcoded to `None`
  regardless of source — there has never been a valuation provider for A-shares.

The existing retry/backoff/spot-table-dedup work (`a25c556`) is correct but only
mitigates *transient* drops; it cannot ride out a persistent server-side block.

## 2. Goals & non-goals

**Goals**

1. Restore **market cap** for A-shares via Tushare `pro.daily_basic` (the stable,
   token-authenticated source), filling the dead valuation block.
2. As a near-free bonus, also fill **`pe` / `pb` / `ps`** ratios from the same
   `daily_basic` call (currently all `None`).
3. Restore **daily prices** by adding a Sina (`stock_zh_a_daily`) failover to
   `get_prices`, keeping Eastmoney `stock_zh_a_hist` as primary (it may recover).
4. Degrade gracefully: with no token or insufficient Tushare points, the system
   keeps running (returns `None` / `[]`) exactly as it does today — no new
   failure modes, no noisy retries.

**Non-goals (explicitly out of scope)**

- `enterprise_value`: not provided by `daily_basic`; leave `None`. (Future: derive
  from `market_cap + total_debt − cash` using line-item data.)
- Tushare as a price source (`pro.daily`): prices stay on akshare. Tushare is a
  *valuation* provider only.
- Fixing the Eastmoney block itself (server-side, not in our control).

## 3. Decisions

| Decision | Choice | Why |
|---|---|---|
| Tushare scope | market cap + pe/pb/ps only | One `daily_basic` call yields all four; prices already have a working Sina path |
| Token reality | none yet; free tier = 100 pts; `daily_basic` needs 2000 | Build token-ready + degrade-gracefully; acquiring the token/points stays on the user |
| File org | **new `src/tools/api_tushare.py`** | Keeps each backend focused and independently testable; `api_akshare.py` is already 935 lines |
| Price fix | **bundled** (option A) | Same data layer; leaving prices dead while touching this layer is wrong |
| Dispatch | unchanged in `api.py` | Still routes A-shares to `api_akshare`, which delegates valuation to `api_tushare` internally |

## 4. Architecture

```
api.py  ──(is_a_share)──▶  api_akshare.py
                              │
                              ├── get_prices ── ak.stock_zh_a_hist (Eastmoney, primary)
                              │                   └─ failover ─▶ ak.stock_zh_a_daily (Sina)
                              │
                              ├── get_market_cap ──▶ api_tushare.get_valuation  (primary)
                              │                        └─ failback ─▶ existing spot path
                              │
                              └── get_financial_metrics ──▶ (per period) api_tushare.get_valuation
                                                            fills market_cap / pe / pb / ps
```

`api_tushare` is a **valuation provider** with one public entry point. It owns
the Tushare token, the SDK client, the shared per-trade-date table, and all
degradation logic. `api_akshare` calls it; nothing else changes shape.

## 5. Component design

### 5.1 New file `src/tools/api_tushare.py`

**`_get_pro() -> "tushare.pro_api client | None"`** (module-level lazy singleton)
- Read `os.environ.get("TUSHARE_TOKEN")`. If absent/empty → return `None` and log
  once at INFO ("TUSHARE_TOKEN not set; A-share valuation will be unavailable").
  No token is the steady state until the user registers, so this must be silent
  after the first log.
- If present: `tushare.set_token(token)`; cache and return `ts.pro_api()`.
- Import `tushare` lazily *inside* this function so a missing/optional dependency
  does not break import of `api_akshare` (matches the lazy `from src.tools import
  api_akshare` pattern in `api.py`).

**`_VALUATION_DISABLED: bool`** (module-level circuit breaker)
- `False` initially. Set to `True` the first time `daily_basic` returns a
  **permission / insufficient-points** error. Once tripped, `get_valuation`
  short-circuits to `None` for the rest of the process — we never re-fire the
  gated endpoint per ticker (which would burn the daily call quota).
- Tripped **only** on permission errors, NOT on transient network/timeout errors
  (those route through the existing `_with_retry` and must not latch the breaker).

**`_daily_basic_table(trade_date: str) -> pd.DataFrame | None`** (shared memo)
- `daily_basic(trade_date=YYYYMMDD)` returns **all** A-shares' valuation for that
  one trade date in a single call — the same "one call covers every ticker"
  shape as the existing `_spot_table`. Memoize by `trade_date` in a module-level
  `dict[str, pd.DataFrame]`, guarded by `_cache.fetch_lock("tushare:daily_basic:<date>")`
  so the concurrent fan-out serialises to one network call per date.
- Returns `None` on permission error (and trips the breaker) or empty result.

**`get_valuation(ticker, as_of_date) -> dict | None`**
- The single public entry point. Returns
  `{"market_cap": float, "pe": float|None, "pb": float|None, "ps": float|None,
    "trade_date": str}` or `None`.
- Short-circuit if `_get_pro()` is `None` or `_VALUATION_DISABLED`.
- `ticker` is already in Tushare format (`600519.SH`) — **no conversion**.
- Trade-date walk-back: try `as_of_date` normalised to `YYYYMMDD`; if the table
  for that date is empty/nonexistent, step back one calendar day at a time up to
  **7** days (covers the longest CN holiday gaps). This finds the latest trading
  day ≤ `as_of_date` without an extra `trade_cal` call.
- Look up the row by `ts_code == ticker`; if missing → `None`.

### 5.2 `get_prices` Sina failover (in `api_akshare.py`)

Current `_fetch()` calls only `stock_zh_a_hist` (Eastmoney). Change to:

1. Try `stock_zh_a_hist` (primary; may recover).
2. On exception or empty frame, **fall over** to `ak.stock_zh_a_daily(
   symbol=<sina-prefixed>, start_date=start_ak, end_date=end_ak, adjust="qfq")`.
3. Build the Sina symbol via the existing prefix logic already in
   `_fetch_statements` (`sh`/`sz`/`bj` + bare code) — extract to a small
   `_sina_symbol(ticker)` helper to avoid duplication.

Column handling — Sina and Eastmoney schemas differ, verified empirically:

| Source | Date col | OHLCV cols | date dtype |
|---|---|---|---|
| Eastmoney `stock_zh_a_hist` | `日期` | `开盘/收盘/最高/最低/成交量` | str |
| Sina `stock_zh_a_daily` | `date` | `open/high/low/close/volume` | **`datetime.date`** |

- Apply the **appropriate** `col_map` based on which source returned (detect by
  column name, e.g. presence of `"日期"`).
- For Sina, `date` is a `datetime.date`; the existing `time=str(row["time"])`
  cast already stringifies it correctly once renamed `date→time`.

Wrap the whole fetch (primary + failover) in `_with_retry` as today; the failover
itself is the new branch inside `_fetch`.

### 5.3 `get_market_cap` (in `api_akshare.py`)

Insert Tushare as the **primary**, ahead of the existing Eastmoney spot path:

```
v = api_tushare.get_valuation(ticker, end_date)
if v and v["market_cap"]:
    return v["market_cap"]
# ...existing spot-table / stock_individual_info_em fallback (unchanged)...
```

### 5.4 `get_financial_metrics` enrichment (in `api_akshare.py`)

For each `report_period` record built today, after constructing the
`FinancialMetrics(...)`, look up the point-in-time valuation:

```
v = api_tushare.get_valuation(ticker, report_period)   # report_period = "YYYY-MM-DD"
if v:
    rec.market_cap = v["market_cap"]
    rec.price_to_earnings_ratio = v["pe"]
    rec.price_to_book_ratio     = v["pb"]
    rec.price_to_sales_ratio    = v["ps"]
```

`report_period` is a real trading day (quarter/year end), so `daily_basic` at that
date gives a genuine point-in-time valuation per period — not just "latest". The
shared per-`trade_date` memo (§5.1) keeps this affordable: ~N distinct period
dates total, shared across the whole ticker fan-out.

## 6. Edge cases & correctness

1. **Unit conversion (critical).** `daily_basic.total_mv` and `circ_mv` are in
   **万元 (10,000 CNY)**. Must multiply by `1e4` to get CNY to match
   `currency="CNY"`. `pe`/`pb`/`ps` are unitless ratios — no conversion. A prior
   commit (`83a2ee5`) fixed an akshare unit bug; this one gets a pinned unit test,
   and **must be re-verified against a live response once a token is available**.
2. **Trade-date walk-back.** `as_of_date` may be a non-trading day, weekend, or
   future date. Walk back ≤ 7 calendar days. (Longest CN closure is the Spring
   Festival at ~7 trading days; 7 calendar days is the cheap bound — refine to
   trading-day-aware later if needed.)
3. **Circuit breaker scoping.** Trip **only** on Tushare permission/points errors
   (HTTP/SDK codes indicating 权限不足 / insufficient points). Transient network
   errors go through `_with_retry` and must NOT latch the breaker.
4. **Points-error detection (finalise at implementation).** Tushare raises on
   insufficient points; the exact exception/payload (`TushareError` vs. an
   error-row DataFrame with `code` 40203) varies by SDK version and cannot be
   tested without a token. Implementation must handle **both** an exception and
   an error-payload frame, and treat either as permission failure. Pin the chosen
   detection in a unit test once the real shape is known.
5. **Sina `date` is `datetime.date`.** Already handled by the `str(...)` cast after
   `date→time` rename; called out so it isn't "fixed" into breaking.
6. **No token is the steady state.** `_get_pro()` returning `None` must never
   raise or log per-call — only a single INFO at first contact.

## 7. Testing (all mock `pro.daily_basic` / akshare; no real token needed)

`tests/test_api_tushare.py`
- token present + data → `get_valuation` returns correct `market_cap` with the
  **×1e4 unit** applied and pe/pb/ps passed through.
- no token → returns `None`, no exception, **no** SDK import attempted.
- permission error (mock raises / returns error frame) → returns `None` **and**
  trips breaker; a second call makes **zero** SDK calls.
- transient error → does **not** trip breaker (still retries).
- non-trading-day `as_of_date` → walks back to the nearest populated date.
- shared-table dedup: many tickers, same `end_date` → exactly **one**
  `daily_basic(trade_date=…)` call (mirror `test_akshare_spot_dedup.py`).

`tests/test_akshare_prices_failover.py`
- `stock_zh_a_hist` raises → falls through to `stock_zh_a_daily`; returned
  `Price` list has correct OHLCV and stringified `time` from the `datetime.date`.
- `stock_zh_a_hist` succeeds → Sina is **not** called.
- Eastmoney-empty-but-no-exception → still falls over to Sina.

`tests/test_akshare_metrics_valuation.py`
- with Tushare valuation mocked, `get_financial_metrics` records carry non-None
  `market_cap`/`pe`/`pb`/`ps` for the periods Tushare resolves.
- Tushare returns `None` → fields stay `None` (today's behaviour preserved).

## 8. Dependencies

- Add `tushare = "^1.4"` to `pyproject.toml` `[tool.poetry.dependencies]`
  (imports as `tushare` / `ts`; ships `pro_api`). `pandas`/`requests` already deps.
- `tushare` is imported **lazily** inside `_get_pro()`, so the project still runs
  for users who never install/configure it (US-only runs, CI without token).
- Document `TUSHARE_TOKEN` in `.env.example` (create if absent) and note the
  2000-point requirement for `daily_basic` next to it.

## 9. Rollout / verification once a token exists

After the user adds `TUSHARE_TOKEN` to `.env` with ≥2000 points:
1. Run a single `get_market_cap("600519.SH", "2026-07-07")` and confirm a sane
   Maotai market cap (~2e12 CNY order of magnitude) — this also confirms the unit.
2. Run a small A-share analysis end-to-end and confirm valuation fields populate.
3. If `daily_basic` returns a permission error, confirm the breaker logs once and
   the run degrades to `None` cleanly.

## 10. Open questions for implementation

- Exact Tushare points-error signal (exception type vs. error frame) — pin from a
  real response at implementation time; spec covers both paths.
- Whether `stock_zh_a_daily`'s `adjust="qfq"` matches the project's forward-adjust
  semantics exactly — verified returning data; spot-check one ticker against
  `stock_zh_a_hist` (when Eastmoney recovers) for parity.
