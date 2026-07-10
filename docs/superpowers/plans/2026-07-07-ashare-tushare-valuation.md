# A-share Tushare Valuation + Sina Price Failover — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore A-share market cap / pe / pb / ps via Tushare `daily_basic`, and daily prices via a Sina failover, both degrading gracefully when no token / insufficient points.

**Architecture:** A new focused `src/tools/api_tushare.py` valuation provider (token-aware, per-trade-date shared table, points-error circuit breaker). `api_akshare.py` calls it from `get_market_cap` (primary) and `get_financial_metrics` (per-period enrichment), and gains a Sina `stock_zh_a_daily` failover in `get_prices`. Tushare is imported lazily so token-less environments are unaffected.

**Tech Stack:** Python 3.11, Poetry, akshare 1.18.64, tushare 1.4.29 (new), pandas, pytest.

**Spec:** `docs/superpowers/specs/2026-07-07-ashare-tushare-valuation-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `pyproject.toml` | Modify | Declare `tushare` dependency |
| `.env.example` | Modify | Document `TUSHARE_TOKEN` + 2000-point note |
| `src/tools/api_tushare.py` | Create | Tushare valuation provider: token, shared table, breaker, `get_valuation` |
| `src/tools/api_akshare.py` | Modify | `_sina_symbol` helper; `get_prices` Sina failover; `get_market_cap` + `get_financial_metrics` call Tushare |
| `tests/test_api_tushare.py` | Create | Unit tests for the provider (mocked, no real token) |
| `tests/test_akshare_prices_failover.py` | Create | Tests for the Eastmoney→Sina price failover |
| `tests/test_akshare_metrics_valuation.py` | Create | Tests for FinancialMetrics valuation enrichment |

---

## Task 1: Add `tushare` dependency + document `TUSHARE_TOKEN`

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`

- [ ] **Step 1: Add tushare via Poetry (updates pyproject.toml + poetry.lock, installs)**

Run:
```bash
poetry add tushare
```
Expected: resolves and installs `tushare` (1.4.29 or newer 1.4.x); pyproject gains `tushare = "^1.4.29"` (or similar) under `[tool.poetry.dependencies]`.

- [ ] **Step 2: Verify the import works in the project env**

Run:
```bash
poetry run python -c "import tushare as ts; print(ts.__version__)"
```
Expected: prints a version like `1.4.29`.

- [ ] **Step 3: Document `TUSHARE_TOKEN` in `.env.example`**

Append the following block to `.env.example` (the file already exists with `KEY=` + comment pairs; match that style):

```
# Tushare (A-share valuation: market_cap / pe / pb / ps via pro.daily_basic).
# Register at https://tushare.pro. daily_basic requires 2000 points; with fewer,
# the A-share valuation fields stay None and the run degrades gracefully.
TUSHARE_TOKEN=
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml poetry.lock .env.example
git commit -m "deps: add tushare for A-share valuation

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Create `api_tushare.py` skeleton + `_get_pro()` (token-aware, lazy import)

**Files:**
- Create: `src/tools/api_tushare.py`
- Test: `tests/test_api_tushare.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_api_tushare.py`:

```python
"""Tests for the Tushare valuation provider.

No real token or network is required: the SDK is mocked via sys.modules and
``_get_pro`` is monkeypatched to return a fake pro client.
"""
from __future__ import annotations

import sys
import types

import pandas as pd
import pytest

from src.tools import api_tushare


@pytest.fixture
def fresh(monkeypatch):
    """Token enabled, breaker reset, table memo cleared."""
    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")
    monkeypatch.setattr(api_tushare, "_disabled", False)
    monkeypatch.setattr(api_tushare, "_daily_basic_tables", {})
    # Reset any cached pro client from a prior test.
    monkeypatch.setattr(api_tushare._get_pro, "_pro", None, raising=False)
    return monkeypatch


def test_get_pro_returns_none_when_no_token(monkeypatch):
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    assert api_tushare._get_pro() is None


def test_get_pro_returns_cached_client_when_token_set(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")
    fake_ts = types.ModuleType("tushare")
    fake_ts.set_token = lambda token: None
    client = object()
    fake_ts.pro_api = lambda: client
    monkeypatch.setitem(sys.modules, "tushare", fake_ts)
    monkeypatch.setattr(api_tushare._get_pro, "_pro", None, raising=False)

    first = api_tushare._get_pro()
    second = api_tushare._get_pro()
    assert first is client
    assert second is client  # cached → same object, no second pro_api() call
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
poetry run pytest tests/test_api_tushare.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'src.tools.api_tushare'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/tools/api_tushare.py`:

```python
"""A-share valuation provider backed by Tushare pro ``daily_basic``.

Fills the valuation block (market_cap / pe / pb / ps) that akshare cannot
supply reliably: Eastmoney endpoints are persistently blocked and Sina carries
no market cap. Tushare's authenticated ``daily_basic`` is the stable source.

Token & degradation
-------------------
- Reads ``TUSHARE_TOKEN`` from the environment. Absent → this module is a
  no-op (every public call returns ``None``); the rest of the A-share layer
  falls back to its current behaviour.
- On a Tushare *permission / insufficient-points* error the module latches a
  process-wide breaker so we never re-fire the gated endpoint per ticker.
- Transient network errors are NOT breaker-worthy.

All public entry points return ``None`` on failure — they never raise.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd

from src.data.cache import get_cache

logger = logging.getLogger(__name__)

_cache = get_cache()

# Per-trade_date memo of the full-market daily_basic table. One call covers
# every ticker for that date, so the concurrent fan-out shares it (guarded by
# the per-key lock in _cache.fetch_lock).
_daily_basic_tables: dict[str, pd.DataFrame] = {}

# Process-wide breaker: tripped on a Tushare permission error (insufficient
# points). Once tripped, get_valuation short-circuits for the rest of the run.
_disabled: bool = False

# Marks permission-style errors in Tushare exception text / error payloads.
_PERMISSION_TOKENS = (
    "权限", "permission", "积分", "40203", "40001", "40002", "40003",
)


def _get_pro() -> Any:
    """Return a cached ``tushare.pro_api`` client, or ``None`` if no token.

    Imports ``tushare`` lazily so this module loads even when the package or
    token is absent — US-only runs and token-less CI must not break.
    """
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        return None
    cached = getattr(_get_pro, "_pro", None)
    if cached is not None:
        return cached
    import tushare as ts  # lazy: keeps token-less envs dependency-light

    ts.set_token(token)
    client = ts.pro_api()
    _get_pro._pro = client  # type: ignore[attr-defined]
    return client


def _to_float(v) -> float | None:
    """Coerce to float, treating NaN / None / garbage as None."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
poetry run pytest tests/test_api_tushare.py -v
```
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tools/api_tushare.py tests/test_api_tushare.py
git commit -m "feat(api_tushare): token-aware lazy pro client skeleton

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: `_daily_basic_table()` — shared memo, breaker, dedup

**Files:**
- Modify: `src/tools/api_tushare.py`
- Test: `tests/test_api_tushare.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_api_tushare.py`:

```python
def _valuation_frame(ts_code="600519.SH", total_mv=2.0e7, pe=30.0, pb=8.0, ps=15.0):
    """total_mv is in 万元 (2.0e7 万元 == 2.0e11 元)."""
    return pd.DataFrame(
        [
            {
                "ts_code": ts_code,
                "trade_date": "20260707",
                "total_mv": total_mv,
                "pe": pe,
                "pb": pb,
                "ps": ps,
                "circ_mv": total_mv,
            }
        ]
    )


def _fake_pro_with(daily_basic_fn):
    pro = types.SimpleNamespace()
    pro.daily_basic = daily_basic_fn
    return pro


def test_permission_error_trips_breaker_and_second_call_is_free(fresh, monkeypatch):
    calls = {"n": 0}

    def bad(trade_date=""):
        calls["n"] += 1
        raise RuntimeError("抱歉，您权限不足，需要 2000 积分")

    monkeypatch.setattr(api_tushare, "_get_pro", lambda: _fake_pro_with(bad))

    assert api_tushare._daily_basic_table("20260707") is None
    assert api_tushare._disabled is True
    assert api_tushare._daily_basic_table("20260707") is None  # short-circuit
    assert calls["n"] == 1  # breaker prevented a second SDK call


def test_transient_error_does_not_trip_breaker(fresh, monkeypatch):
    def flaky(trade_date=""):
        raise ConnectionError("RemoteDisconnected")

    monkeypatch.setattr(api_tushare, "_get_pro", lambda: _fake_pro_with(flaky))

    assert api_tushare._daily_basic_table("20260707") is None
    assert api_tushare._disabled is False  # transient must NOT latch


def test_empty_frame_returns_none_without_tripping(fresh, monkeypatch):
    monkeypatch.setattr(
        api_tushare, "_get_pro", lambda: _fake_pro_with(lambda trade_date="": pd.DataFrame())
    )
    assert api_tushare._daily_basic_table("20260707") is None
    assert api_tushare._disabled is False


def test_table_is_memoized_per_trade_date(fresh, monkeypatch):
    calls = {"n": 0}

    def single(trade_date=""):
        calls["n"] += 1
        return _valuation_frame()

    monkeypatch.setattr(api_tushare, "_get_pro", lambda: _fake_pro_with(single))

    first = api_tushare._daily_basic_table("20260707")
    second = api_tushare._daily_basic_table("20260707")
    assert first is second  # same cached DataFrame object
    assert calls["n"] == 1


def test_no_token_returns_none_without_calling_sdk(fresh, monkeypatch):
    calls = {"n": 0}

    def boom(trade_date=""):
        calls["n"] += 1
        raise AssertionError("SDK must not be called without a token")

    monkeypatch.setattr(api_tushare, "_get_pro", lambda: None)
    assert api_tushare._daily_basic_table("20260707") is None
    assert calls["n"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
poetry run pytest tests/test_api_tushare.py -v
```
Expected: the 5 new tests FAIL with `AttributeError: module ... has no attribute '_daily_basic_table'` (the 2 from Task 2 still pass).

- [ ] **Step 3: Write minimal implementation**

Append to `src/tools/api_tushare.py` (before the `_to_float` helper is fine — these are module-level functions):

```python
def _is_permission_error(exc: BaseException | None, payload: Any) -> bool:
    """True if Tushare rejected the call for permission / points reasons.

    Tushare may raise OR return a one-row error DataFrame; handle both.
    """
    if exc is not None and any(t in str(exc) for t in _PERMISSION_TOKENS):
        return True
    if isinstance(payload, pd.DataFrame) and not payload.empty:
        cols = {str(c).lower() for c in payload.columns}
        if "code" in cols or "msg" in cols:
            joined = " ".join(str(v) for v in payload.iloc[0].tolist())
            return any(t in joined for t in _PERMISSION_TOKENS)
    return False


def _daily_basic_table(trade_date: str) -> pd.DataFrame | None:
    """Return the full-market daily_basic frame for ``trade_date`` (YYYYMMDD).

    Memoized per trade_date and serialised on a per-date lock so the fan-out
    fires one network call per date. Trips the breaker on a permission error;
    returns ``None`` (without tripping) on empty or transient errors.
    """
    global _disabled
    if _disabled:
        return None
    if trade_date in _daily_basic_tables:
        return _daily_basic_tables[trade_date]

    pro = _get_pro()
    if pro is None:
        return None

    with _cache.fetch_lock(f"tushare:daily_basic:{trade_date}"):
        if _disabled:
            return None
        if trade_date in _daily_basic_tables:
            return _daily_basic_tables[trade_date]
        try:
            df = pro.daily_basic(trade_date=trade_date)
        except Exception as e:  # noqa: BLE001 - Tushare raises varied types
            if _is_permission_error(e, None):
                logger.warning(
                    "tushare daily_basic permission denied (needs 2000 points) "
                    "— disabling Tushare valuation for this run: %s",
                    e,
                )
                _disabled = True
                return None
            # Transient: do not memoize, do not trip — let the caller retry.
            logger.warning(
                "tushare daily_basic transient error for %s: %s", trade_date, e
            )
            return None

        if _is_permission_error(None, df):
            logger.warning(
                "tushare daily_basic returned a permission-error payload "
                "— disabling Tushare valuation for this run"
            )
            _disabled = True
            return None

        if df is None or df.empty:
            return None  # non-trading day / future date — caller walks back

        _daily_basic_tables[trade_date] = df
        return df
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
poetry run pytest tests/test_api_tushare.py -v
```
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tools/api_tushare.py tests/test_api_tushare.py
git commit -m "feat(api_tushare): shared daily_basic table with points-error breaker

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: `get_valuation()` — unit conversion, ratios, trade-date walk-back

**Files:**
- Modify: `src/tools/api_tushare.py`
- Test: `tests/test_api_tushare.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_api_tushare.py`:

```python
def test_get_valuation_converts_units_and_returns_ratios(fresh, monkeypatch):
    monkeypatch.setattr(
        api_tushare,
        "_get_pro",
        lambda: _fake_pro_with(
            lambda trade_date="": _valuation_frame() if trade_date == "20260707" else pd.DataFrame()
        ),
    )

    v = api_tushare.get_valuation("600519.SH", "2026-07-07")
    assert v is not None
    assert v["market_cap"] == pytest.approx(2.0e7 * 1e4)  # 万元 → 元
    assert v["pe"] == 30.0
    assert v["pb"] == 8.0
    assert v["ps"] == 15.0
    assert v["trade_date"] == "20260707"


def test_get_valuation_walks_back_to_nearest_trading_day(fresh, monkeypatch):
    # 2026-07-04 is a Saturday; only Friday 2026-07-03 has data.
    def fake(trade_date=""):
        return _valuation_frame() if trade_date == "20260703" else pd.DataFrame()

    monkeypatch.setattr(api_tushare, "_get_pro", lambda: _fake_pro_with(fake))

    v = api_tushare.get_valuation("600519.SH", "2026-07-04")
    assert v is not None
    assert v["trade_date"] == "20260703"


def test_get_valuation_missing_ticker_returns_none(fresh, monkeypatch):
    monkeypatch.setattr(
        api_tushare, "_get_pro", lambda: _fake_pro_with(lambda trade_date="": _valuation_frame())
    )
    assert api_tushare.get_valuation("999999.SH", "2026-07-07") is None


def test_get_valuation_disabled_short_circuits(monkeypatch):
    monkeypatch.setattr(api_tushare, "_disabled", True)
    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")
    assert api_tushare.get_valuation("600519.SH", "2026-07-07") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
poetry run pytest tests/test_api_tushare.py -v
```
Expected: the 4 new tests FAIL with `AttributeError: ... has no attribute 'get_valuation'`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/tools/api_tushare.py`:

```python
def get_valuation(ticker: str, as_of_date: str) -> dict | None:
    """Point-in-time valuation for ``ticker`` as of the latest trading day
    ≤ ``as_of_date``.

    ``ticker`` is a Tushare ts_code (e.g. ``600519.SH``) — the project's
    internal A-share format, no conversion needed.
    ``as_of_date`` is ``YYYY-MM-DD``.

    Returns ``{"market_cap", "pe", "pb", "ps", "trade_date"}`` or ``None``.
    ``market_cap`` is in CNY (yuan); Tushare ships it in 万元 so we multiply
    by 1e4.
    """
    if _disabled or _get_pro() is None:
        return None

    import datetime as _dt

    target = as_of_date.replace("-", "")
    dt = _dt.datetime.strptime(target, "%Y%m%d")
    # Walk back up to 7 calendar days to find a populated trading day
    # (covers the longest CN holiday closures).
    for back in range(8):
        ymd = (dt - _dt.timedelta(days=back)).strftime("%Y%m%d")
        df = _daily_basic_table(ymd)
        if df is None:
            if _disabled:
                return None
            continue  # empty/non-trading day → try the previous day
        row = df[df["ts_code"] == ticker]
        if row.empty:
            continue
        r = row.iloc[0]
        total_mv_wan = _to_float(r.get("total_mv"))
        return {
            "market_cap": total_mv_wan * 1e4 if total_mv_wan is not None else None,
            "pe": _to_float(r.get("pe")),
            "pb": _to_float(r.get("pb")),
            "ps": _to_float(r.get("ps")),
            "trade_date": ymd,
        }
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
poetry run pytest tests/test_api_tushare.py -v
```
Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tools/api_tushare.py tests/test_api_tushare.py
git commit -m "feat(api_tushare): get_valuation with unit conversion + trade-day walk-back

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: `get_prices` Eastmoney→Sina failover in `api_akshare.py`

**Files:**
- Modify: `src/tools/api_akshare.py`
- Test: `tests/test_akshare_prices_failover.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_akshare_prices_failover.py`:

```python
"""Tests for the Eastmoney→Sina failover in api_akshare.get_prices.

Eastmoney stock_zh_a_hist has been persistently dropping connections; on
failure (or empty) get_prices must fall over to Sina stock_zh_a_daily, whose
columns are English and whose ``date`` is a datetime.date.
"""
from __future__ import annotations

import datetime

import pandas as pd
import pytest

from src.tools import api_akshare


@pytest.fixture
def fresh_cache(monkeypatch):
    from src.data.cache import Cache

    monkeypatch.setattr(api_akshare, "_cache", Cache())


def _sina_row(d, o, h, l, c, v):
    return {
        "date": d,
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": v,
        "amount": 0.0,
        "outstanding_share": 0.0,
        "turnover": 0.0,
    }


def test_hist_failure_falls_over_to_sina(fresh_cache, monkeypatch):
    monkeypatch.setattr(api_akshare.time, "sleep", lambda *_: None)
    sina_df = pd.DataFrame(
        [_sina_row(datetime.date(2026, 7, 6), 1186.0, 1215.0, 1180.0, 1206.91, 4097001.0)]
    )
    monkeypatch.setattr(
        api_akshare.ak, "stock_zh_a_hist", lambda **kw: (_ for _ in ()).throw(ConnectionError("RemoteDisconnected"))
    )
    monkeypatch.setattr(api_akshare.ak, "stock_zh_a_daily", lambda **kw: sina_df)

    prices = api_akshare.get_prices("600519.SH", "2026-07-01", "2026-07-07")
    assert len(prices) == 1
    assert prices[0].close == 1206.91
    assert prices[0].time == "2026-07-06"  # datetime.date stringified


def test_hist_success_does_not_call_sina(fresh_cache, monkeypatch):
    monkeypatch.setattr(api_akshare.time, "sleep", lambda *_: None)
    hist_df = pd.DataFrame(
        [{"日期": "2026-07-06", "开盘": 1.0, "收盘": 2.0, "最高": 3.0, "最低": 0.5, "成交量": 100}]
    )
    monkeypatch.setattr(api_akshare.ak, "stock_zh_a_hist", lambda **kw: hist_df)
    monkeypatch.setattr(
        api_akshare.ak,
        "stock_zh_a_daily",
        lambda **kw: pytest.fail("Sina must not be called when Eastmoney succeeds"),
    )

    prices = api_akshare.get_prices("600519.SH", "2026-07-01", "2026-07-07")
    assert len(prices) == 1
    assert prices[0].close == 2.0


def test_hist_empty_falls_over_to_sina(fresh_cache, monkeypatch):
    monkeypatch.setattr(api_akshare.time, "sleep", lambda *_: None)
    sina_df = pd.DataFrame([_sina_row(datetime.date(2026, 7, 6), 1.0, 2.0, 0.5, 1.5, 10)])
    monkeypatch.setattr(api_akshare.ak, "stock_zh_a_hist", lambda **kw: pd.DataFrame())
    monkeypatch.setattr(api_akshare.ak, "stock_zh_a_daily", lambda **kw: sina_df)

    prices = api_akshare.get_prices("600519.SH", "2026-07-01", "2026-07-07")
    assert len(prices) == 1
    assert prices[0].close == 1.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
poetry run pytest tests/test_akshare_prices_failover.py -v
```
Expected: FAIL — `stock_zh_a_daily` is never called by the current `get_prices`. Concretely `test_hist_failure_falls_over_to_sina` and `test_hist_empty_falls_over_to_sina` fail with `assert 0 == 1` (current code returns `[]` on both). `test_hist_success_does_not_call_sina` already passes — the Eastmoney-success path is unchanged.

- [ ] **Step 3: Write minimal implementation**

In `src/tools/api_akshare.py`:

**3a. Add `_sina_symbol` helper** — insert this function right after the `_with_retry` function (before `get_prices`):

```python
def _sina_symbol(ticker: str) -> str:
    """Build the sh/sz/bj-prefixed symbol Sina expects (e.g. ``sh600519``)."""
    code = a_share_code(ticker)
    if ticker.endswith(".SH"):
        return f"sh{code}"
    if ticker.endswith(".SZ"):
        return f"sz{code}"
    if ticker.endswith(".BJ"):
        return f"bj{code}"
    return code
```

**3b. Replace the `_fetch` closure inside `get_prices`.** Replace this block:

```python
    def _fetch() -> pd.DataFrame:
        try:
            return ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_ak,
                end_date=end_ak,
                adjust="qfq",
            )
        except Exception:
            # Fallback: raw (unadjusted) prices
            return ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_ak,
                end_date=end_ak,
                adjust="",
            )
```

with:

```python
    def _fetch() -> pd.DataFrame:
        # Primary: Eastmoney forward-adjusted. Eastmoney has been persistently
        # dropping connections, so on failure (or empty) fall over to Sina.
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_ak,
                end_date=end_ak,
                adjust="qfq",
            )
            if df is not None and not df.empty:
                return df
        except Exception:
            pass
        # Failover: Sina forward-adjusted.
        return ak.stock_zh_a_daily(
            symbol=_sina_symbol(ticker),
            start_date=start_ak,
            end_date=end_ak,
            adjust="qfq",
        )
```

**3c. Replace the column-map block inside `get_prices`.** Replace:

```python
    # Column map: 日期/开盘/收盘/最高/最低/成交量/成交额/振幅/涨跌幅/涨跌额/换手率
    col_map = {
        "日期": "time",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
    }
    df = df.rename(columns=col_map)
```

with:

```python
    # Column map depends on which source returned. Eastmoney uses Chinese
    # column names; Sina (stock_zh_a_daily) uses English names and returns
    # ``date`` as a datetime.date — str() below stringifies it correctly.
    if "日期" in df.columns:
        df = df.rename(
            columns={
                "日期": "time",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
            }
        )
    elif "date" in df.columns:
        df = df.rename(columns={"date": "time"})
        # open / high / low / close / volume already match the Price fields
```

**3d. Refactor `_fetch_statements` to reuse `_sina_symbol`.** Replace:

```python
    code = a_share_code(ticker)
    # Sina uses sh/sz prefix
    if ticker.endswith(".SH"):
        sina_stock = f"sh{code}"
    elif ticker.endswith(".SZ"):
        sina_stock = f"sz{code}"
    elif ticker.endswith(".BJ"):
        sina_stock = f"bj{code}"
    else:
        sina_stock = code
```

with:

```python
    sina_stock = _sina_symbol(ticker)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
poetry run pytest tests/test_akshare_prices_failover.py -v
```
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tools/api_akshare.py tests/test_akshare_prices_failover.py
git commit -m "feat(api_akshare): fall over get_prices to Sina when Eastmoney fails

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: `get_market_cap` uses Tushare as primary

**Files:**
- Modify: `src/tools/api_akshare.py`
- Test: `tests/test_akshare_spot_dedup.py` (extend) or a new test file

- [ ] **Step 1: Write the failing tests**

Create `tests/test_akshare_market_cap_tushare.py`:

```python
"""Tests that get_market_cap prefers Tushare valuation and falls back when None."""
from __future__ import annotations

import pandas as pd
import pytest

from src.tools import api_akshare, api_tushare  # patch the module directly


@pytest.fixture
def fresh_state(monkeypatch):
    from src.data.cache import Cache

    monkeypatch.setattr(api_akshare, "_cache", Cache())
    monkeypatch.setattr(api_akshare, "_spot_table", None, raising=False)


def test_tushare_value_is_returned_without_hitting_spot(fresh_state, monkeypatch):
    monkeypatch.setattr(
        api_tushare,
        "get_valuation",
        lambda ticker, as_of_date: {"market_cap": 2.0e12, "pe": 30.0, "pb": 8.0, "ps": 15.0, "trade_date": "20260707"},
    )
    monkeypatch.setattr(
        api_akshare,
        "_get_spot_table",
        lambda: pytest.fail("spot table must not be fetched when Tushare resolves"),
    )
    assert api_akshare.get_market_cap("600519.SH", "2026-07-07") == 2.0e12


def test_falls_back_to_spot_when_tushare_returns_none(fresh_state, monkeypatch):
    monkeypatch.setattr(api_tushare, "get_valuation", lambda ticker, as_of_date: None)
    spot = pd.DataFrame({"代码": ["600519"], "总市值": [1.5e12]})
    monkeypatch.setattr(api_akshare, "_get_spot_table", lambda: spot)
    assert api_akshare.get_market_cap("600519.SH", "2026-07-07") == 1.5e12
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
poetry run pytest tests/test_akshare_market_cap_tushare.py -v
```
Expected: `test_tushare_value_is_returned_without_hitting_spot` FAILS — `get_market_cap` does not yet call `api_tushare.get_valuation`, so it calls `_get_spot_table` and trips the `pytest.fail`. (`test_falls_back_to_spot_when_tushare_returns_none` already passes — the fallback path is unchanged.)

- [ ] **Step 3: Write minimal implementation**

In `src/tools/api_akshare.py`:

**3a. Add the import.** Replace:

```python
from src.tools.markets import a_share_code
```

with:

```python
from src.tools import api_tushare
from src.tools.markets import a_share_code
```

**3b. Insert Tushare as primary in `get_market_cap`.** Replace:

```python
    code = a_share_code(ticker)

    # --- Primary: shared all-market spot table (fetched once per process) ---
    spot = _get_spot_table()
```

with:

```python
    code = a_share_code(ticker)

    # --- Primary: Tushare daily_basic (stable, authenticated) ---
    v = api_tushare.get_valuation(ticker, end_date)
    if v and v.get("market_cap"):
        return v["market_cap"]

    # --- Secondary: shared all-market spot table (Eastmoney; currently flaky) ---
    spot = _get_spot_table()
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
poetry run pytest tests/test_akshare_market_cap_tushare.py tests/test_akshare_spot_dedup.py -v
```
Expected: PASS (the 2 new tests + the existing spot-dedup tests still pass — the spot path is now secondary but unchanged in behaviour when Tushare is mocked to None).

- [ ] **Step 5: Commit**

```bash
git add src/tools/api_akshare.py tests/test_akshare_market_cap_tushare.py
git commit -m "feat(api_akshare): use Tushare as primary market-cap source

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: `get_financial_metrics` per-period valuation enrichment

**Files:**
- Modify: `src/tools/api_akshare.py`
- Test: `tests/test_akshare_metrics_valuation.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_akshare_metrics_valuation.py`:

```python
"""Tests that get_financial_metrics fills market_cap/pe/pb/ps from Tushare
for each report period, and leaves them None when Tushare returns None."""
from __future__ import annotations

import pandas as pd
import pytest

from src.tools import api_akshare, api_tushare  # patch the module directly


@pytest.fixture
def fresh_state(monkeypatch):
    from src.data.cache import Cache

    monkeypatch.setattr(api_akshare, "_cache", Cache())


def _fake_abstract():
    # One annual period (2024-12-31) with one indicator; just enough for the
    # function to build a FinancialMetrics record.
    return pd.DataFrame([{"选项": "财务摘要", "指标": "毛利率", "20241231": 91.5}])


def test_metrics_filled_with_tushare_valuation(fresh_state, monkeypatch):
    monkeypatch.setattr(api_akshare.ak, "stock_financial_abstract", lambda symbol: _fake_abstract())
    monkeypatch.setattr(
        api_tushare,
        "get_valuation",
        lambda ticker, as_of_date: {
            "market_cap": 2.0e12,
            "pe": 30.0,
            "pb": 8.0,
            "ps": 15.0,
            "trade_date": as_of_date.replace("-", ""),
        },
    )

    metrics = api_akshare.get_financial_metrics("600519.SH", "2025-12-31", period="annual", limit=5)
    assert len(metrics) >= 1
    m = metrics[0]
    assert m.market_cap == 2.0e12
    assert m.price_to_earnings_ratio == 30.0
    assert m.price_to_book_ratio == 8.0
    assert m.price_to_sales_ratio == 15.0


def test_metrics_valuation_none_keeps_fields_none(fresh_state, monkeypatch):
    monkeypatch.setattr(api_akshare.ak, "stock_financial_abstract", lambda symbol: _fake_abstract())
    monkeypatch.setattr(api_tushare, "get_valuation", lambda ticker, as_of_date: None)

    metrics = api_akshare.get_financial_metrics("600519.SH", "2025-12-31", period="annual", limit=5)
    assert len(metrics) >= 1
    m = metrics[0]
    assert m.market_cap is None
    assert m.price_to_earnings_ratio is None
    assert m.price_to_book_ratio is None
    assert m.price_to_sales_ratio is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
poetry run pytest tests/test_akshare_metrics_valuation.py -v
```
Expected: FAIL — `test_metrics_filled_with_tushare_valuation` fails because the current constructor hardcodes `market_cap=None` etc., so `m.market_cap` is `None`, not `2.0e12`.

- [ ] **Step 3: Write minimal implementation**

In `src/tools/api_akshare.py`, inside `get_financial_metrics`, replace:

```python
    metrics: list[FinancialMetrics] = []
    for pc in eligible:
        report_period = f"{pc[:4]}-{pc[4:6]}-{pc[6:]}"
        metrics.append(
            FinancialMetrics(
                ticker=ticker,
                report_period=report_period,
                period=period,
                currency="CNY",
                market_cap=None,  # handled separately in get_market_cap
                enterprise_value=None,
                price_to_earnings_ratio=None,
                price_to_book_ratio=None,
                price_to_sales_ratio=None,
                enterprise_value_to_ebitda_ratio=None,
```

with:

```python
    metrics: list[FinancialMetrics] = []
    for pc in eligible:
        report_period = f"{pc[:4]}-{pc[4:6]}-{pc[6:]}"
        # Point-in-time valuation as of this report period's date (Tushare
        # daily_basic). None when no token / insufficient points / no data.
        v = api_tushare.get_valuation(ticker, report_period)
        metrics.append(
            FinancialMetrics(
                ticker=ticker,
                report_period=report_period,
                period=period,
                currency="CNY",
                market_cap=(v["market_cap"] if v else None),
                enterprise_value=None,
                price_to_earnings_ratio=(v["pe"] if v else None),
                price_to_book_ratio=(v["pb"] if v else None),
                price_to_sales_ratio=(v["ps"] if v else None),
                enterprise_value_to_ebitda_ratio=None,
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
poetry run pytest tests/test_akshare_metrics_valuation.py tests/test_api_tushare.py tests/test_akshare_prices_failover.py tests/test_akshare_market_cap_tushare.py tests/test_akshare_spot_dedup.py tests/test_akshare_retry.py -v
```
Expected: ALL PASS (full suite for this feature green).

- [ ] **Step 5: Commit**

```bash
git add src/tools/api_akshare.py tests/test_akshare_metrics_valuation.py
git commit -m "feat(api_akshare): fill market_cap/pe/pb/ps per period from Tushare

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Post-implementation: live verification (requires a real token with ≥2000 points)

These are manual checks, not automated tasks — run them once the user has added
`TUSHARE_TOKEN=...` (with ≥2000 points) to `.env`:

1. **Unit sanity check (also confirms the ×1e4 conversion):**
   ```bash
   poetry run python -c "
   from src.tools import api_tushare
   v = api_tushare.get_valuation('600519.SH', '2026-07-07')
   print(v)  # expect market_cap ~2e11..2e12 order, trade_date a recent trading day
   "
   ```
   If Maotai's market cap is off by ~10,000×, the unit conversion is wrong — re-check `total_mv` units against the live payload.

2. **End-to-end:** run a small A-share analysis (e.g. one A-share ticker through the analyst flow) and confirm `market_cap` / `pe` / `pb` / `ps` populate in the produced `FinancialMetrics`.

3. **Degradation:** with the token removed (or <2000 points), confirm the run still completes and those fields are `None`, with exactly one breaker warning in the logs.
