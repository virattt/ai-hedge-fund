# HK/CN Financial Data Enrichment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three gaps in HK/CN financial data: (1) add multi-year historical data to `search_line_items`, (2) compute missing derived metrics (FCF yield, PEG, EV, ROIC, P/S, etc.), (3) fix growth rate calculations to use YoY instead of rolling QoQ.

**Architecture:**
- Task 1 adds a `get_historical_financial_data()` method to `XueqiuSource` that fetches multiple annual periods, and wires it into `search_line_items` in `api.py` so non-US calls return up to `limit` years of history instead of just 1 TTM row.
- Task 2 adds a `_compute_derived_metrics()` helper in `xueqiu_source.py` called after building the base metrics dict, computing fields that can be derived from already-fetched data.
- Task 3 fixes `earnings_growth` and `revenue_growth` in `_build_hk_metrics` to use year-over-year annual comparison instead of rolling QoQ from the TTM indicator field.

**Tech Stack:** Python, Pydantic v2, requests, pytest, akshare, Xueqiu HTTP API

---

## Chunk 1: Multi-Year Historical Data for search_line_items

### Task 1: Add `get_historical_financial_data()` to XueqiuSource

**Files:**
- Modify: `src/markets/sources/xueqiu_source.py`
- Test: `tests/markets/sources/test_xueqiu_source.py`

**Context:**
`_fetch_financial_data(endpoint, symbol, market)` already fetches up to 5 periods by passing `count=5`. The current `get_financial_metrics` only uses `[0]` (most recent). We need a new method that fetches multiple annual periods and returns a list of metrics dicts.

The Xueqiu annual endpoint uses `type=Q4` (year-end reports). For `count=10` it returns up to 10 years. We need to build a metrics dict per year by pairing each year's indicator/income/cash_flow/balance rows by `report_date`.

- [ ] **Step 1: Write failing test for `get_historical_financial_data` (HK)**

Add to `tests/markets/sources/test_xueqiu_source.py`:

```python
class TestXueqiuSourceHistoricalData:
    """Tests for multi-year historical financial data."""

    def _make_income_row(self, report_date_ms, revenue, net_income):
        return {
            "report_date": report_date_ms,
            "tto": [revenue, None],
            "ploashh": [net_income, None],
            "plobtx": [net_income * 1.1, None],
            "gp": [revenue * 0.4, None],
            "rshdevexp": [revenue * 0.05, None],
        }

    def _make_indicator_row(self, report_date_ms, roe, gpm, opm):
        return {
            "report_date": report_date_ms,
            "roe": [roe, None],
            "rota": [roe * 0.5, None],
            "gpm": [gpm, None],
            "opemg": [opm, None],
            "tlia_ta": [45.0, None],
            "beps": [5.0, None],
            "bps": [28.0, None],
            "nocfps": [8.0, None],
            "cro": [1.9, None],
            "qro": [1.8, None],
            "ploashh": [None, None],
            "tto": [None, None],
        }

    def _make_cashflow_row(self, report_date_ms, ocf, capex):
        return {
            "report_date": report_date_ms,
            "nocf": [ocf, None],
            "adtfxda": [-abs(capex), None],
            "ninvcf": [-capex * 0.5, None],
            "nfcgcf": [-ocf * 0.3, None],
        }

    def _make_balance_row(self, report_date_ms, total_assets, equity):
        return {
            "report_date": report_date_ms,
            "ta": [total_assets, None],
            "tlia": [total_assets - equity, None],
            "shhfd": [equity, None],
            "cceq": [equity * 0.2, None],
            "ca": [equity * 0.6, None],
            "clia": [equity * 0.3, None],
        }

    @patch('src.markets.sources.xueqiu_source.XueqiuSource._fetch_financial_data')
    @patch('src.markets.sources.xueqiu_source.XueqiuSource._fetch_quote_valuation')
    @patch('src.markets.sources.xueqiu_source.XueqiuSource._ensure_token')
    def test_get_historical_hk_returns_multiple_years(
        self, mock_token, mock_quote, mock_fetch
    ):
        """get_historical_financial_data returns one dict per year, most recent first."""
        mock_token.return_value = True
        mock_quote.return_value = {"pe_ttm": 15.0, "pe_lyr": 13.0, "pe_forecast": 14.0, "pb": 2.6, "ps_ttm": None}

        # Two years: 2024 and 2023
        ts_2024 = 1735603200000  # 2024-12-31
        ts_2023 = 1703980800000  # 2023-12-31

        def fake_fetch(endpoint, symbol, market):
            if endpoint == "income":
                return [
                    self._make_income_row(ts_2024, 337e9, 35e9),
                    self._make_income_row(ts_2023, 276e9, 13e9),
                ]
            if endpoint == "indicator":
                return [
                    self._make_indicator_row(ts_2024, 22.0, 36.0, 11.0),
                    self._make_indicator_row(ts_2023, 8.0, 30.0, 5.0),
                ]
            if endpoint == "cash_flow":
                return [
                    self._make_cashflow_row(ts_2024, 57e9, 11e9),
                    self._make_cashflow_row(ts_2023, 40e9, 8e9),
                ]
            if endpoint == "balance":
                return [
                    self._make_balance_row(ts_2024, 475e9, 172e9),
                    self._make_balance_row(ts_2023, 400e9, 150e9),
                ]
            return []

        mock_fetch.side_effect = fake_fetch

        source = XueqiuSource()
        results = source.get_historical_financial_data("03690", limit=5)

        assert results is not None
        assert len(results) == 2
        # Most recent first
        assert results[0]["report_period"] == "2024-12-31"
        assert results[1]["report_period"] == "2023-12-31"
        # Check data integrity
        assert abs(results[0]["revenue"] - 337e9) < 1e6
        assert abs(results[1]["revenue"] - 276e9) < 1e6
        assert results[0]["return_on_equity"] == pytest.approx(0.22, abs=0.001)

    @patch('src.markets.sources.xueqiu_source.XueqiuSource._fetch_financial_data')
    @patch('src.markets.sources.xueqiu_source.XueqiuSource._fetch_quote_valuation')
    @patch('src.markets.sources.xueqiu_source.XueqiuSource._ensure_token')
    def test_get_historical_respects_limit(
        self, mock_token, mock_quote, mock_fetch
    ):
        """limit parameter caps the number of returned periods."""
        mock_token.return_value = True
        mock_quote.return_value = {}

        ts_list = [1735603200000 - i * 31536000000 for i in range(5)]

        def fake_fetch(endpoint, symbol, market):
            if endpoint == "income":
                return [self._make_income_row(ts, 100e9 - i * 10e9, 10e9) for i, ts in enumerate(ts_list)]
            if endpoint in ("indicator", "cash_flow", "balance"):
                return []
            return []

        mock_fetch.side_effect = fake_fetch

        source = XueqiuSource()
        results = source.get_historical_financial_data("03690", limit=3)

        assert len(results) == 3

    @patch('src.markets.sources.xueqiu_source.XueqiuSource._fetch_financial_data')
    @patch('src.markets.sources.xueqiu_source.XueqiuSource._ensure_token')
    def test_get_historical_returns_none_on_no_data(self, mock_token, mock_fetch):
        """Returns None when all fetches fail."""
        mock_token.return_value = True
        mock_fetch.return_value = []

        source = XueqiuSource()
        result = source.get_historical_financial_data("03690", limit=5)
        assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/luobotao/.openclaw/workspace/ai-hedge-fund
poetry run pytest tests/markets/sources/test_xueqiu_source.py::TestXueqiuSourceHistoricalData -v 2>&1 | tail -20
```
Expected: FAIL with `AttributeError: 'XueqiuSource' object has no attribute 'get_historical_financial_data'`

- [ ] **Step 3: Implement `get_historical_financial_data` in XueqiuSource**

Add after the existing `get_financial_metrics` method in `src/markets/sources/xueqiu_source.py`:

```python
def get_historical_financial_data(
    self, ticker: str, limit: int = 10
) -> Optional[List[Dict]]:
    """
    获取港股或A股多年历史财务数据，返回按年度排列的指标列表（最新在前）。

    与 get_financial_metrics 不同，此方法返回最多 limit 年的年度数据，
    用于 search_line_items 的历史多期查询。

    Returns:
        list of metric dicts (most recent first), or None if no data.
    """
    if not self._ensure_token():
        self.logger.warning("[Xueqiu] Cannot get token, skipping historical data")
        return None

    market, symbol = self._detect_market_and_symbol(ticker)

    # Fetch up to limit annual periods (type=Q4 = year-end reports)
    count = str(min(limit, 10))  # Xueqiu caps at ~10

    indicator_list = self._fetch_financial_data_multi("indicator", symbol, market, count)
    income_list = self._fetch_financial_data_multi("income", symbol, market, count)
    cash_flow_list = self._fetch_financial_data_multi("cash_flow", symbol, market, count)
    balance_list = self._fetch_financial_data_multi("balance", symbol, market, count)

    if not any([indicator_list, income_list, cash_flow_list, balance_list]):
        self.logger.warning(f"[Xueqiu] No historical data for {symbol}")
        return None

    # Index by report_date for alignment across statement types
    def index_by_date(rows: List[Dict]) -> Dict[int, Dict]:
        result = {}
        for row in rows:
            rd = row.get("report_date")
            if rd is not None:
                result[int(rd)] = row
        return result

    indicator_by_date = index_by_date(indicator_list)
    income_by_date = index_by_date(income_list)
    cashflow_by_date = index_by_date(cash_flow_list)
    balance_by_date = index_by_date(balance_list)

    # Use income list as the primary date spine (most likely to be complete)
    # Fall back to indicator list if income is empty
    spine = income_list or indicator_list
    if not spine:
        return None

    # Fetch valuation ratios once (real-time, applies to most recent only)
    quote_valuation = self._fetch_quote_valuation(symbol)

    results = []
    for i, row in enumerate(spine[:limit]):
        rd = row.get("report_date")
        if rd is None:
            continue
        rd_int = int(rd)

        indicator = indicator_by_date.get(rd_int, {})
        income = income_by_date.get(rd_int, row)  # row IS income if spine=income_list
        cash_flow = cashflow_by_date.get(rd_int, {})
        balance = balance_by_date.get(rd_int, {})

        # Only apply real-time valuation to the most recent period
        qv = quote_valuation if i == 0 else {}

        if market == "HK":
            metrics = self._build_hk_metrics(ticker, indicator, income, cash_flow, balance, qv)
        else:
            metrics = self._build_cn_metrics(ticker, indicator, income, cash_flow, balance, qv)

        results.append(metrics)

    return results if results else None
```

Also add `_fetch_financial_data_multi` (a variant that accepts a configurable count):

```python
def _fetch_financial_data_multi(
    self, endpoint: str, symbol: str, market: str, count: str = "10"
) -> List[Dict]:
    """
    从雪球财务API获取多期数据（可配置条数）。
    与 _fetch_financial_data 相同，但 count 参数可自定义。
    """
    mkt = market.lower()
    url = f"{self.BASE_URL}/{mkt}/{endpoint}.json"
    params = {"symbol": symbol, "type": "Q4", "is_detail": "true", "count": count}
    try:
        r = self.session.get(url, params=params, timeout=10)
        if r.status_code != 200:
            self.logger.warning(f"[Xueqiu] {endpoint} for {symbol} returned {r.status_code}")
            return []
        data = r.json()
        return data.get("data", {}).get("list", []) or []
    except Exception as e:
        self.logger.error(f"[Xueqiu] Error fetching {endpoint} for {symbol}: {e}")
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py::TestXueqiuSourceHistoricalData -v 2>&1 | tail -15
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/markets/sources/xueqiu_source.py tests/markets/sources/test_xueqiu_source.py
git commit -m "feat: add get_historical_financial_data to XueqiuSource for multi-year data"
```

---

### Task 2: Wire historical data into `search_line_items` for non-US stocks

**Files:**
- Modify: `src/tools/api.py`
- Test: `tests/tools/test_api_integration.py`

**Context:**
Currently `search_line_items` for non-US stocks calls `get_financial_metrics` which returns 1 item. We need it to call `XueqiuSource.get_historical_financial_data` (via the market router/adapter) when `period == "annual"` and `limit > 1`.

The cleanest approach: add a `get_historical_financial_metrics` method to `MarketAdapter` base class, implemented in `HKStockAdapter` and `CNStockAdapter` by delegating to the Xueqiu source. Then `api.py` calls this when appropriate.

- [ ] **Step 1: Write failing test for `search_line_items` returning multi-year data**

Add to `tests/tools/test_api_integration.py`. **First add imports at the top of the file if not present:**
```python
from unittest.mock import patch, MagicMock
```

Then add the test class:

```python
class TestSearchLineItemsNonUS:
    """Tests for search_line_items with HK/CN stocks returning historical data."""

    @patch('src.tools.api._get_market_router')
    def test_hk_search_line_items_annual_returns_multiple_years(self, mock_router):
        """search_line_items for HK stock with period=annual returns multiple LineItems."""
        from src.tools.api import search_line_items

        mock_adapter = MagicMock()
        mock_adapter.get_historical_financial_metrics.return_value = [
            {
                "ticker": "03690",
                "report_period": "2024-12-31",
                "period": "annual",
                "currency": "HKD",
                "revenue": 337e9,
                "net_income": 35e9,
                "free_cash_flow": 43e9,
                "earnings_per_share": 5.85,
                "operating_margin": 0.11,
                "debt_to_equity": 0.89,
            },
            {
                "ticker": "03690",
                "report_period": "2023-12-31",
                "period": "annual",
                "currency": "HKD",
                "revenue": 276e9,
                "net_income": 13e9,
                "free_cash_flow": 20e9,
                "earnings_per_share": 2.2,
                "operating_margin": 0.05,
                "debt_to_equity": 0.95,
            },
        ]
        mock_router.return_value.get_adapter.return_value = mock_adapter

        results = search_line_items(
            "3690.HK",
            ["revenue", "net_income", "free_cash_flow", "earnings_per_share"],
            "2026-03-18",
            period="annual",
            limit=5,
        )

        assert len(results) == 2
        assert results[0].report_period == "2024-12-31"
        assert results[1].report_period == "2023-12-31"
        assert abs(results[0].revenue - 337e9) < 1e6
        assert abs(results[1].revenue - 276e9) < 1e6

    @patch('src.tools.api._get_market_router')
    def test_hk_search_line_items_ttm_returns_single_item(self, mock_router):
        """search_line_items for HK stock with period=ttm returns single TTM LineItem."""
        from src.tools.api import search_line_items, get_financial_metrics as gfm

        mock_adapter = MagicMock()
        mock_adapter.get_financial_metrics.return_value = {
            "ticker": "03690",
            "report_period": "2024-12-31",
            "period": "ttm",
            "currency": "HKD",
            "revenue": 334e9,
            "net_income": 33e9,
        }
        mock_router.return_value.get_adapter.return_value = mock_adapter

        with patch('src.tools.api.get_financial_metrics') as mock_gfm:
            from src.data.models import FinancialMetrics
            mock_gfm.return_value = [FinancialMetrics(
                ticker="03690", report_period="2024-12-31",
                period="ttm", currency="HKD",
                revenue=334e9, net_income=33e9,
            )]
            results = search_line_items(
                "3690.HK",
                ["revenue", "net_income"],
                "2026-03-18",
                period="ttm",
                limit=1,
            )

        assert len(results) == 1
        assert results[0].period == "ttm"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/tools/test_api_integration.py::TestSearchLineItemsNonUS -v 2>&1 | tail -15
```
Expected: FAIL — `mock_adapter.get_historical_financial_metrics` not called (method doesn't exist yet)

- [ ] **Step 3: Add `get_historical_financial_metrics` to MarketAdapter base**

Add to `src/markets/base.py` after `get_financial_metrics`:

```python
def get_historical_financial_metrics(
    self, ticker: str, end_date: str, limit: int = 10
) -> Optional[List[Dict]]:
    """
    Get multiple years of annual financial metrics.

    Default implementation: returns single-period data wrapped in a list.
    Subclasses (HKStockAdapter, CNStockAdapter) override this to use
    XueqiuSource.get_historical_financial_data() for richer history.

    Args:
        ticker: Stock ticker
        end_date: End date (YYYY-MM-DD) — data up to this date
        limit: Max number of annual periods to return

    Returns:
        List of metric dicts (most recent first), or None
    """
    single = self.get_financial_metrics(ticker, end_date)
    return [single] if single else None
```

- [ ] **Step 4: Override in HKStockAdapter**

Add to `src/markets/hk_stock.py`:

```python
def get_historical_financial_metrics(
    self, ticker: str, end_date: str, limit: int = 10
) -> Optional[List[Dict]]:
    """
    Get multi-year annual financial data via XueqiuSource.

    Falls back to single-period data if Xueqiu returns nothing.
    """
    normalized = self.normalize_ticker(ticker)

    # Try Xueqiu first (best historical coverage for HK)
    for source in self.active_sources:
        if source.name == "Xueqiu":
            try:
                results = source.get_historical_financial_data(normalized, limit=limit)
                if results:
                    self.logger.info(
                        f"[HKStock] ✓ Got {len(results)} historical periods from Xueqiu for {normalized}"
                    )
                    return results
            except Exception as e:
                self.logger.warning(f"[HKStock] Xueqiu historical failed for {normalized}: {e}")
            break

    # Fallback: single period
    self.logger.warning(f"[HKStock] Falling back to single-period data for {normalized}")
    return super().get_historical_financial_metrics(ticker, end_date, limit)
```

- [ ] **Step 5: Override in CNStockAdapter**

Add to `src/markets/cn_stock.py`:

```python
def get_historical_financial_metrics(
    self, ticker: str, end_date: str, limit: int = 10
) -> Optional[List[Dict]]:
    """
    Get multi-year annual financial data via XueqiuSource.

    Falls back to single-period data if Xueqiu returns nothing.
    """
    normalized = self.normalize_ticker(ticker)

    # Try Xueqiu first (best historical coverage for CN)
    for source in self.active_sources:
        if source.name == "Xueqiu":
            try:
                results = source.get_historical_financial_data(normalized, limit=limit)
                if results:
                    self.logger.info(
                        f"[CNStock] ✓ Got {len(results)} historical periods from Xueqiu for {normalized}"
                    )
                    return results
            except Exception as e:
                self.logger.warning(f"[CNStock] Xueqiu historical failed for {normalized}: {e}")
            break

    # Fallback: single period
    self.logger.warning(f"[CNStock] Falling back to single-period data for {normalized}")
    return super().get_historical_financial_metrics(ticker, end_date, limit)
```

- [ ] **Step 6: Update `search_line_items` in `api.py` to use historical data for annual period**

Replace the non-US branch of `search_line_items` (lines 338-377):

```python
    else:
        # 非美股：使用 MarketRouter
        try:
            adapter = _get_market_router().get_adapter(ticker)
        except Exception as e:
            logger.warning("No adapter for %s: %s", ticker, e)
            return []

        if period == "annual" and limit > 1:
            # 历史多期年度数据
            metrics_list = adapter.get_historical_financial_metrics(ticker, end_date, limit=limit)
            if not metrics_list:
                return []
            period_label = "annual"
        else:
            # 单期TTM数据（向后兼容）
            single = adapter.get_financial_metrics(ticker, end_date)
            if not single:
                return []
            metrics_list = [single]
            period_label = period

        # 将每个 metrics dict 转换为 LineItem
        line_items_result = []
        for metrics_dict in metrics_list:
            line_item_dict = {
                "ticker": metrics_dict.get("ticker", ticker),
                "report_period": metrics_dict.get("report_period", ""),
                "period": metrics_dict.get("period", period_label),
                "currency": metrics_dict.get("currency", "USD"),
            }
            # 映射请求的字段（field_mapping 处理别名）
            field_mapping = {
                "dividends_and_other_cash_distributions": "dividends",
            }
            for requested_field in line_items:
                mapped = field_mapping.get(requested_field, requested_field)
                line_item_dict[requested_field] = metrics_dict.get(mapped)

            line_items_result.append(LineItem(**line_item_dict))

        return line_items_result[:limit]
```

Also update `_get_market_router()` usage — we need `get_adapter(ticker)` method. Check if it exists:

```bash
grep -n "get_adapter\|def get_" src/markets/router.py
```

If `get_adapter` doesn't exist, add it to `src/markets/router.py` (the existing attribute is `self.adapters`, not `self._adapters`):

```python
def get_adapter(self, ticker: str):
    """Return the adapter for a given ticker, raising ValueError if none found."""
    for adapter in self.adapters:
        if hasattr(adapter, 'supports_ticker') and adapter.supports_ticker(ticker):
            return adapter
    raise ValueError(f"No adapter found for ticker: {ticker}")
```

- [ ] **Step 7: Run tests**

```bash
poetry run pytest tests/tools/test_api_integration.py::TestSearchLineItemsNonUS -v 2>&1 | tail -15
```
Expected: 2 passed

- [ ] **Step 8: Run full existing test suite to check for regressions**

```bash
poetry run pytest tests/markets/ tests/tools/ -q --timeout=30 2>&1 | tail -15
```
Expected: no new failures beyond pre-existing ones

- [ ] **Step 9: Commit**

```bash
git add src/tools/api.py src/markets/base.py src/markets/hk_stock.py src/markets/cn_stock.py src/markets/router.py tests/tools/test_api_integration.py
git commit -m "feat: wire multi-year historical data into search_line_items for HK/CN stocks"
```

---

## Chunk 2: Derived Metrics & Growth Rate Fix

### Task 3: Compute missing derived metrics

**Files:**
- Modify: `src/markets/sources/xueqiu_source.py`
- Test: `tests/markets/sources/test_xueqiu_source.py`

**Context:**
The following metrics are None in current output but can be computed from fields already fetched:

| Field | Formula |
|-------|---------|
| `free_cash_flow_yield` | `free_cash_flow / market_cap` |
| `free_cash_flow_per_share` | `free_cash_flow / shares_outstanding` |
| `price_to_sales_ratio` | `market_cap / revenue` |
| `enterprise_value` | `market_cap + total_liabilities - cash_and_equivalents` |
| `enterprise_value_to_ebitda_ratio` | `enterprise_value / (operating_income + depreciation_amortization)` — skip if no D&A |
| `enterprise_value_to_revenue_ratio` | `enterprise_value / revenue` |
| `peg_ratio` | `price_to_earnings_ratio / (earnings_growth * 100)` — only if earnings_growth > 0 |
| `return_on_invested_capital` (ROIC) | `operating_income * (1 - 0.25) / (shareholders_equity + total_liabilities - cash_and_equivalents)` |
| `debt_to_equity` | `total_liabilities / shareholders_equity` (already computed via AKShare estimate; add direct calculation) |
| `interest_coverage` | skip — requires interest expense not available |

- [ ] **Step 1: Write failing tests for derived metrics**

Add to `tests/markets/sources/test_xueqiu_source.py`:

```python
class TestXueqiuDerivedMetrics:
    """Tests for computed derived metrics in _compute_derived_metrics."""

    def test_free_cash_flow_yield(self):
        from src.markets.sources.xueqiu_source import XueqiuSource
        source = XueqiuSource()
        metrics = {
            "free_cash_flow": 43e9,
            "market_cap": 450e9,
        }
        source._compute_derived_metrics(metrics)
        assert metrics["free_cash_flow_yield"] == pytest.approx(43e9 / 450e9, rel=1e-4)

    def test_free_cash_flow_per_share(self):
        from src.markets.sources.xueqiu_source import XueqiuSource
        source = XueqiuSource()
        metrics = {
            "free_cash_flow": 43e9,
            "shares_outstanding": 6174383320.0,
        }
        source._compute_derived_metrics(metrics)
        assert metrics["free_cash_flow_per_share"] == pytest.approx(43e9 / 6174383320.0, rel=1e-4)

    def test_price_to_sales_ratio(self):
        from src.markets.sources.xueqiu_source import XueqiuSource
        source = XueqiuSource()
        metrics = {
            "market_cap": 450e9,
            "revenue": 337e9,
        }
        source._compute_derived_metrics(metrics)
        assert metrics["price_to_sales_ratio"] == pytest.approx(450e9 / 337e9, rel=1e-4)

    def test_enterprise_value(self):
        from src.markets.sources.xueqiu_source import XueqiuSource
        source = XueqiuSource()
        metrics = {
            "market_cap": 450e9,
            "total_liabilities": 303e9,
            "cash_and_equivalents": 90e9,
        }
        source._compute_derived_metrics(metrics)
        assert metrics["enterprise_value"] == pytest.approx(450e9 + 303e9 - 90e9, rel=1e-4)

    def test_enterprise_value_to_revenue(self):
        from src.markets.sources.xueqiu_source import XueqiuSource
        source = XueqiuSource()
        metrics = {
            "market_cap": 450e9,
            "total_liabilities": 303e9,
            "cash_and_equivalents": 90e9,
            "revenue": 337e9,
        }
        source._compute_derived_metrics(metrics)
        ev = 450e9 + 303e9 - 90e9
        assert metrics["enterprise_value_to_revenue_ratio"] == pytest.approx(ev / 337e9, rel=1e-4)

    def test_peg_ratio_positive_growth(self):
        from src.markets.sources.xueqiu_source import XueqiuSource
        source = XueqiuSource()
        metrics = {
            "price_to_earnings_ratio": 20.0,
            "earnings_growth": 0.25,  # 25% growth
        }
        source._compute_derived_metrics(metrics)
        # PEG = PE / (growth_rate_as_percent) = 20 / 25 = 0.8
        assert metrics["peg_ratio"] == pytest.approx(0.8, rel=1e-4)

    def test_peg_ratio_skipped_for_negative_growth(self):
        from src.markets.sources.xueqiu_source import XueqiuSource
        source = XueqiuSource()
        metrics = {
            "price_to_earnings_ratio": 20.0,
            "earnings_growth": -0.10,  # negative growth
        }
        source._compute_derived_metrics(metrics)
        assert metrics.get("peg_ratio") is None

    def test_roic(self):
        from src.markets.sources.xueqiu_source import XueqiuSource
        source = XueqiuSource()
        metrics = {
            "operating_income": 37e9,
            "shareholders_equity": 172e9,
            "total_liabilities": 303e9,
            "cash_and_equivalents": 90e9,
        }
        source._compute_derived_metrics(metrics)
        invested_capital = 172e9 + 303e9 - 90e9
        nopat = 37e9 * (1 - 0.25)
        expected_roic = nopat / invested_capital
        assert metrics["return_on_invested_capital"] == pytest.approx(expected_roic, rel=1e-4)

    def test_debt_to_equity_direct(self):
        from src.markets.sources.xueqiu_source import XueqiuSource
        source = XueqiuSource()
        metrics = {
            "total_liabilities": 303e9,
            "shareholders_equity": 172e9,
            "debt_to_equity": None,  # not yet set
        }
        source._compute_derived_metrics(metrics)
        assert metrics["debt_to_equity"] == pytest.approx(303e9 / 172e9, rel=1e-4)

    def test_skips_when_missing_inputs(self):
        from src.markets.sources.xueqiu_source import XueqiuSource
        source = XueqiuSource()
        metrics = {}  # empty
        source._compute_derived_metrics(metrics)
        # Should not raise, all derived fields remain absent or None
        assert metrics.get("free_cash_flow_yield") is None
        assert metrics.get("enterprise_value") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py::TestXueqiuDerivedMetrics -v 2>&1 | tail -15
```
Expected: FAIL with `AttributeError: 'XueqiuSource' object has no attribute '_compute_derived_metrics'`

- [ ] **Step 3: Implement `_compute_derived_metrics` in XueqiuSource**

Add to `src/markets/sources/xueqiu_source.py` after `_safe_float`:

```python
def _compute_derived_metrics(self, metrics: Dict) -> None:
    """
    在 metrics dict 上原地计算衍生指标。
    仅在输入字段有效时才写入结果，避免用 None 覆盖已有值。
    """
    def get(field):
        return metrics.get(field)

    def safe_div(a, b):
        if a is not None and b and b != 0:
            return a / b
        return None

    # free_cash_flow_yield = FCF / market_cap
    # Note: market_cap is only available for the most recent period (from AKShare/quote API).
    # For historical periods, market_cap will be None and these ratios will remain None.
    if metrics.get("free_cash_flow_yield") is None:
        metrics["free_cash_flow_yield"] = safe_div(get("free_cash_flow"), get("market_cap"))

    # free_cash_flow_per_share = FCF / shares_outstanding
    if metrics.get("free_cash_flow_per_share") is None:
        shares = get("shares_outstanding") or get("outstanding_shares")
        metrics["free_cash_flow_per_share"] = safe_div(get("free_cash_flow"), shares)

    # price_to_sales_ratio = market_cap / revenue
    if metrics.get("price_to_sales_ratio") is None:
        metrics["price_to_sales_ratio"] = safe_div(get("market_cap"), get("revenue"))

    # enterprise_value = market_cap + total_liabilities - cash_and_equivalents
    if metrics.get("enterprise_value") is None:
        mc = get("market_cap")
        tl = get("total_liabilities")
        cash = get("cash_and_equivalents")
        if mc is not None and tl is not None and cash is not None:
            metrics["enterprise_value"] = mc + tl - cash

    ev = metrics.get("enterprise_value")

    # enterprise_value_to_revenue_ratio = EV / revenue
    if metrics.get("enterprise_value_to_revenue_ratio") is None:
        metrics["enterprise_value_to_revenue_ratio"] = safe_div(ev, get("revenue"))

    # enterprise_value_to_ebitda_ratio: skip (no D&A data available)

    # peg_ratio = PE / (earnings_growth_percent) — only for positive growth
    if metrics.get("peg_ratio") is None:
        pe = get("price_to_earnings_ratio")
        eg = get("earnings_growth")
        if pe is not None and eg is not None and eg > 0:
            metrics["peg_ratio"] = pe / (eg * 100)

    # return_on_invested_capital = NOPAT / invested_capital
    # NOPAT = operating_income * (1 - effective_tax_rate=0.25)
    # invested_capital = equity + total_liabilities - cash
    if metrics.get("return_on_invested_capital") is None:
        oi = get("operating_income")
        eq = get("shareholders_equity")
        tl = get("total_liabilities")
        cash = get("cash_and_equivalents")
        if oi is not None and eq is not None and tl is not None and cash is not None:
            invested_capital = eq + tl - cash
            if invested_capital > 0:
                metrics["return_on_invested_capital"] = oi * 0.75 / invested_capital

    # debt_to_equity = total_liabilities / shareholders_equity (direct calculation)
    if metrics.get("debt_to_equity") is None:
        metrics["debt_to_equity"] = safe_div(get("total_liabilities"), get("shareholders_equity"))
```

- [ ] **Step 4: Call `_compute_derived_metrics` at the end of `_build_hk_metrics` and `_build_cn_metrics`**

In `_build_hk_metrics`, before the `return` statement:
```python
        self._compute_derived_metrics(result_dict)
        return result_dict
```

Change the current `return { ... }` to assign to a variable first:
```python
        result = { ... }  # existing dict literal
        self._compute_derived_metrics(result)
        return result
```

Do the same for `_build_cn_metrics`.

- [ ] **Step 5: Run derived metrics tests**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py::TestXueqiuDerivedMetrics -v 2>&1 | tail -15
```
Expected: all pass

- [ ] **Step 6: Run full Xueqiu test suite to check no regressions**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py -v 2>&1 | tail -20
```
Expected: all pass (or same failures as before)

- [ ] **Step 7: Commit**

```bash
git add src/markets/sources/xueqiu_source.py tests/markets/sources/test_xueqiu_source.py
git commit -m "feat: add _compute_derived_metrics for FCF yield, EV, PEG, ROIC, P/S"
```

---

### Task 4: Fix earnings_growth and revenue_growth to use YoY

**Files:**
- Modify: `src/markets/sources/xueqiu_source.py`
- Test: `tests/markets/sources/test_xueqiu_source.py`

**Context:**
Current problem: `_build_hk_metrics` uses `earnings_growth` from AKShare's `净利润滚动环比增长(%)` (rolling QoQ), which shows -106.74% for Meituan because a recent quarter was negative. The correct metric is **year-over-year annual growth**: `(current_year_net_income - prior_year_net_income) / abs(prior_year_net_income)`.

For single-period TTM metrics, we can compute YoY growth by fetching the 2 most recent annual periods and comparing. For historical data (Task 1), each period already has the prior year available.

The fix: in `get_financial_metrics` (single-period), fetch 2 years of income data and compute YoY growth explicitly. In `_build_hk_metrics` and `_build_cn_metrics`, accept optional `prior_period` dicts for growth calculation.

- [ ] **Step 1: Write failing tests for YoY growth**

Add to `tests/markets/sources/test_xueqiu_source.py`:

```python
class TestXueqiuYoYGrowth:
    """Tests for year-over-year growth rate calculations."""

    def test_hk_earnings_growth_yoy_positive(self):
        """earnings_growth is YoY: (current - prior) / abs(prior)."""
        from src.markets.sources.xueqiu_source import XueqiuSource
        source = XueqiuSource()

        current_income = {"ploashh": [35e9, None], "tto": [337e9, None]}
        prior_income = {"ploashh": [13e9, None], "tto": [276e9, None]}

        result = source._build_hk_metrics(
            "03690", {}, current_income, {}, {},
            prior_income=prior_income
        )
        # earnings_growth = (35e9 - 13e9) / 13e9 ≈ 1.692
        assert result["earnings_growth"] == pytest.approx((35e9 - 13e9) / 13e9, rel=1e-3)

    def test_hk_revenue_growth_yoy(self):
        """revenue_growth is YoY: (current_rev - prior_rev) / abs(prior_rev)."""
        from src.markets.sources.xueqiu_source import XueqiuSource
        source = XueqiuSource()

        current_income = {"ploashh": [35e9, None], "tto": [337e9, None]}
        prior_income = {"ploashh": [13e9, None], "tto": [276e9, None]}

        result = source._build_hk_metrics(
            "03690", {}, current_income, {}, {},
            prior_income=prior_income
        )
        # revenue_growth = (337e9 - 276e9) / 276e9 ≈ 0.221
        assert result["revenue_growth"] == pytest.approx((337e9 - 276e9) / 276e9, rel=1e-3)

    def test_hk_growth_none_when_no_prior(self):
        """earnings_growth and revenue_growth are None when prior_income not provided."""
        from src.markets.sources.xueqiu_source import XueqiuSource
        source = XueqiuSource()

        current_income = {"ploashh": [35e9, None], "tto": [337e9, None]}

        result = source._build_hk_metrics("03690", {}, current_income, {}, {})
        assert result["earnings_growth"] is None
        assert result["revenue_growth"] is None

    def test_hk_growth_handles_prior_zero_revenue(self):
        """revenue_growth is None when prior revenue is 0."""
        from src.markets.sources.xueqiu_source import XueqiuSource
        source = XueqiuSource()

        current_income = {"ploashh": [35e9, None], "tto": [337e9, None]}
        prior_income = {"ploashh": [0, None], "tto": [0, None]}

        result = source._build_hk_metrics(
            "03690", {}, current_income, {}, {},
            prior_income=prior_income
        )
        assert result["revenue_growth"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py::TestXueqiuYoYGrowth -v 2>&1 | tail -15
```
Expected: FAIL — `_build_hk_metrics` doesn't accept `prior_income` kwarg yet

- [ ] **Step 3: Update `_build_hk_metrics` to accept `prior_income` and compute YoY growth**

Change the signature:
```python
def _build_hk_metrics(
    self,
    ticker: str,
    indicator: Dict,
    income: Dict,
    cash_flow: Dict,
    balance: Dict,
    quote_valuation: Optional[Dict] = None,
    prior_income: Optional[Dict] = None,   # <-- new
) -> Dict:
```

Replace the current `earnings_growth` line (which reads from indicator's rolling QoQ field) with:

```python
        # YoY growth: requires prior year income data
        ev_prior = self._extract_value
        if prior_income:
            prior_ni = ev_prior(prior_income.get("ploashh"))
            prior_rev = ev_prior(prior_income.get("tto"))
            if prior_ni is not None and prior_ni != 0 and net_income_val is not None:
                earnings_growth_yoy = (net_income_val - prior_ni) / abs(prior_ni)
            else:
                earnings_growth_yoy = None
            if prior_rev is not None and prior_rev != 0 and revenue_val is not None:
                revenue_growth_yoy = (revenue_val - prior_rev) / abs(prior_rev)
            else:
                revenue_growth_yoy = None

        # Note: net_income_val and revenue_val must be extracted before this block.
        # Use: net_income_val = ev(income.get("ploashh")) or ev(indicator.get("ploashh"))
        #      revenue_val = ev(income.get("tto")) or ev(indicator.get("tto"))
        # (These are already computed earlier in _build_hk_metrics for net_margin_calc)
        else:
            earnings_growth_yoy = None
            revenue_growth_yoy = None
```

Then in the returned dict, use `earnings_growth_yoy` and `revenue_growth_yoy` instead of the old indicator-based values.

- [ ] **Step 4: Update `get_historical_financial_data` to pass prior_income**

In `get_historical_financial_data`, when building metrics for period `i`, pass `income_list[i+1]` as `prior_income` if available:

```python
        for i, row in enumerate(spine[:limit]):
            # ... existing date alignment code ...

            # Prior year income for YoY growth calculation
            prior_income_row = None
            if i + 1 < len(spine):
                prior_rd = spine[i + 1].get("report_date")
                if prior_rd:
                    prior_income_row = income_by_date.get(int(prior_rd))

            if market == "HK":
                metrics = self._build_hk_metrics(
                    ticker, indicator, income, cash_flow, balance, qv,
                    prior_income=prior_income_row
                )
```

- [ ] **Step 5: Update `get_financial_metrics` (single-period) to fetch 2 years and compute YoY**

In `get_financial_metrics`, change the income fetch to get 2 periods:

```python
        # Fetch 2 annual periods for YoY growth calculation
        income_list = self._fetch_financial_data_multi("income", symbol, market, count="2")
        # ... other fetches remain count="5" ...

        income = income_list[0] if income_list else {}
        prior_income = income_list[1] if len(income_list) > 1 else None

        if market == "HK":
            metrics = self._build_hk_metrics(
                ticker, indicator, income, cash_flow, balance, quote_valuation,
                prior_income=prior_income
            )
```

Note: `_fetch_financial_data_multi` must exist (added in Task 1). If Task 1 hasn't been done yet, use `_fetch_financial_data` with a modified count — but since tasks run in order, this is fine.

- [ ] **Step 6: Apply same YoY fix to `_build_cn_metrics`**

Same pattern as HK: add `prior_income: Optional[Dict] = None` parameter, compute YoY growth from income statement instead of indicator's rolling QoQ fields.

For CN, the income fields are: `net_profit` (or `net_profit_atsopc`) and `total_revenue`.

```python
        if prior_income:
            prior_ni = ev(prior_income.get("net_profit")) or ev(prior_income.get("net_profit_atsopc"))
            prior_rev = ev(prior_income.get("total_revenue"))
            earnings_growth_yoy = (net_income_val - prior_ni) / abs(prior_ni) if (prior_ni and prior_ni != 0 and net_income_val is not None) else None
            revenue_growth_yoy = (revenue_val - prior_rev) / abs(prior_rev) if (prior_rev and prior_rev != 0 and revenue_val is not None) else None
        else:
            earnings_growth_yoy = None
            revenue_growth_yoy = None
```

- [ ] **Step 7: Run all growth tests**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py::TestXueqiuYoYGrowth -v 2>&1 | tail -15
```
Expected: all pass

- [ ] **Step 8: Run full test suite**

```bash
poetry run pytest tests/markets/ tests/tools/ -q --timeout=30 2>&1 | tail -15
```
Expected: no new failures

- [ ] **Step 9: Commit**

```bash
git add src/markets/sources/xueqiu_source.py tests/markets/sources/test_xueqiu_source.py
git commit -m "fix: use YoY annual growth for earnings_growth and revenue_growth instead of rolling QoQ"
```

---

## Chunk 3: Validation & End-to-End Smoke Test

### Task 5: End-to-end smoke test with real Meituan data

**Files:**
- Test: `tests/integration/test_financial_data_e2e.py` (new file, skipped in CI)

**Context:**
A quick manual smoke test to verify the full pipeline works with real data. This test is marked `@pytest.mark.skip` so it doesn't run in CI but can be run manually.

- [ ] **Step 1: Create smoke test file**

```python
# tests/integration/test_financial_data_e2e.py
"""
End-to-end smoke tests for HK/CN financial data enrichment.
These tests hit real external APIs and are skipped in CI.
Run manually: poetry run pytest tests/integration/test_financial_data_e2e.py -v -s
"""
import pytest
from src.tools.api import search_line_items, get_financial_metrics


@pytest.mark.skip(reason="Hits real APIs — run manually")
class TestMeituanE2E:

    def test_search_line_items_annual_returns_multiple_years(self):
        """search_line_items with period=annual should return 5+ years for Meituan."""
        results = search_line_items(
            "3690.HK",
            ["revenue", "net_income", "free_cash_flow", "earnings_per_share", "earnings_growth"],
            "2026-03-18",
            period="annual",
            limit=5,
        )
        assert len(results) >= 3, f"Expected ≥3 years, got {len(results)}"
        # Most recent should be 2024
        assert "2024" in results[0].report_period
        # Revenue should be positive
        assert results[0].revenue > 0

    def test_search_line_items_earnings_growth_is_yoy(self):
        """earnings_growth should be positive for 2024 (358B vs 138B in 2023 = +158%)."""
        results = search_line_items(
            "3690.HK",
            ["net_income", "earnings_growth", "revenue_growth"],
            "2026-03-18",
            period="annual",
            limit=2,
        )
        assert len(results) >= 2
        # 2024 earnings_growth should be strongly positive (~1.58)
        assert results[0].earnings_growth > 0.5, (
            f"Expected earnings_growth > 0.5, got {results[0].earnings_growth}"
        )

    def test_derived_metrics_populated(self):
        """Derived metrics (FCF yield, EV, PEG, ROIC) should be non-None."""
        results = get_financial_metrics("3690.HK", "2026-03-18")
        assert results
        m = results[0]
        assert m.free_cash_flow_yield is not None, "free_cash_flow_yield should be computed"
        assert m.enterprise_value is not None, "enterprise_value should be computed"
        assert m.return_on_invested_capital is not None, "ROIC should be computed"
        assert m.price_to_sales_ratio is not None, "P/S should be computed"
        # Sanity checks
        assert 0 < m.free_cash_flow_yield < 0.5
        assert m.enterprise_value > 0

    def test_cn_stock_historical_data(self):
        """CN stock (Moutai) should also return multi-year historical data."""
        results = search_line_items(
            "600519",
            ["revenue", "net_income", "earnings_growth"],
            "2026-03-18",
            period="annual",
            limit=5,
        )
        assert len(results) >= 3
        assert results[0].revenue > 0
```

- [ ] **Step 2: Run smoke tests manually to verify**

```bash
poetry run pytest tests/integration/test_financial_data_e2e.py -v -s -k "not skip" --no-header 2>&1 | tail -30
```

Or to force-run skipped tests:
```bash
poetry run pytest tests/integration/test_financial_data_e2e.py -v -s --run-skipped 2>&1 | tail -30
```

Or override skip manually for local testing:
```bash
poetry run python -c "
from src.tools.api import search_line_items
results = search_line_items('3690.HK', ['revenue','net_income','earnings_growth'], '2026-03-18', period='annual', limit=5)
print(f'Got {len(results)} periods')
for r in results:
    print(f'  {r.report_period}: revenue={r.revenue:.0f}, ni={r.net_income:.0f}, growth={r.earnings_growth}')
"
```

Expected output:
```
Got 5 periods
  2024-12-31: revenue=337591576000, ni=35807179000, growth=1.58...
  2023-12-31: revenue=276744954000, ni=13855828000, growth=...
  ...
```

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_financial_data_e2e.py
git commit -m "test: add end-to-end smoke tests for HK/CN financial data enrichment"
```

---

### Task 6: Final regression check

- [ ] **Step 1: Run backtesting tests (they don't hit external APIs)**

```bash
poetry run pytest tests/backtesting/ -q 2>&1 | tail -10
```
Expected: all pass (same as before)

- [ ] **Step 2: Run markets + tools tests**

```bash
poetry run pytest tests/markets/ tests/tools/ -q --timeout=30 2>&1 | tail -15
```
Expected: no new failures beyond pre-existing ones

- [ ] **Step 3: Final commit summary**

```bash
git log --oneline -6
```
Should show 5 commits from this feature:
1. `feat: add get_historical_financial_data to XueqiuSource`
2. `feat: wire multi-year historical data into search_line_items`
3. `feat: add _compute_derived_metrics for FCF yield, EV, PEG, ROIC, P/S`
4. `fix: use YoY annual growth for earnings_growth and revenue_growth`
5. `test: add end-to-end smoke tests for HK/CN financial data enrichment`
