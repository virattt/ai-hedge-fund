# HK/CN Missing Financial Fields Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 6 critical missing fields (D&A, EBIT, interest_expense, total_debt, dividends, share buybacks) for HK/CN stocks so analyst agents (Buffett, Damodaran, Burry, Graham) receive complete data instead of None values.

**Architecture:** Three-layer fix: (1) extend `FinancialMetrics` data model with new fields, (2) extract missing fields from Xueqiu raw API responses in `xueqiu_source.py`, (3) fix `api.py` field_mapping alias for dividends. No new files needed — all changes are targeted edits to existing files.

**Tech Stack:** Python, Pydantic, Xueqiu REST API (雪球财务报表接口)

---

## File Map

| File | Change |
|------|--------|
| `src/data/models.py` | Add 7 new fields to `FinancialMetrics` |
| `src/markets/sources/xueqiu_source.py` | Extract D&A, interest_expense, total_debt, dividends_paid, equity_change from raw API; compute ebit, ebitda, ev_to_ebit, interest_coverage in `_compute_derived_metrics` |
| `src/tools/api.py` | Keep existing `field_mapping` (already works via fallback); no change needed for pass-through fields |
| `tests/markets/sources/test_xueqiu_source.py` | Add tests for new fields using existing `_make_source` pattern |
| `tests/test_models.py` | New test file for model field assertions |

---

## Known Xueqiu Raw Field Names

**HK Cash Flow (`cash_flow` endpoint) — to verify in Task 6:**
- `da` — 折旧与摊销 (Depreciation & Amortization)
- `finexp` — 财务费用/利息支出 (Finance/Interest Expense)
- `cdp` — 支付股利 (Dividends paid, typically negative)
- `csi` — 股票发行所得 (Cash from share issuance, positive)
- `crpcs` — 股票回购支出 (Cash used for share repurchase, typically negative)

**HK Balance Sheet (`balance` endpoint) — to verify in Task 6:**
- `std` — 短期借款 (Short-term debt)
- `ltd` — 长期借款 (Long-term debt)

**CN Cash Flow (`cash_flow` endpoint) — to verify in Task 6:**
- `depreciation_and_amortization` — D&A
- `interest_expense` — 利息支出
- `cash_paid_for_dividend_profit` — 支付股利 (positive outflow amount)
- `cash_received_from_issuing_shares` — 发行股票 (positive inflow)
- `cash_paid_for_repurchasing_shares` — 回购股票 (positive outflow amount)

**CN Balance Sheet (`balance` endpoint) — to verify in Task 6:**
- `short_term_loan` — 短期借款
- `long_term_loan` — 长期借款

> **Note:** Exact field names must be verified against live API response during Task 6. Use the debug script in Task 6 Step 2 to print raw keys if any field returns None.

---

## Task 1: Extend FinancialMetrics Data Model

**Files:**
- Modify: `src/data/models.py:63-91`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_models.py`:

```python
from src.data.models import FinancialMetrics


def test_financial_metrics_has_new_fields():
    m = FinancialMetrics(ticker="TEST", report_period="2024-12-31", period="annual", currency="HKD")
    # New fields added in this task
    assert hasattr(m, "depreciation_and_amortization")
    assert hasattr(m, "ebit")
    assert hasattr(m, "ebitda")
    assert hasattr(m, "interest_expense")
    assert hasattr(m, "total_debt")
    assert hasattr(m, "issuance_or_purchase_of_equity_shares")
    assert hasattr(m, "ev_to_ebit")
    # All default to None
    assert m.depreciation_and_amortization is None
    assert m.ebit is None
    assert m.ebitda is None
    assert m.ev_to_ebit is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/luobotao/.openclaw/workspace/ai-hedge-fund
poetry run pytest tests/test_models.py::test_financial_metrics_has_new_fields -v
```
Expected: `FAIL` with `AssertionError` (attributes missing)

- [ ] **Step 3: Add new fields to FinancialMetrics**

In `src/data/models.py`, after line 91 (after `operating_cash_flow_per_share`), add:

```python
    # Fields needed by Buffett, Damodaran, Burry, Graham agents
    depreciation_and_amortization: float | None = None
    ebit: float | None = None
    ebitda: float | None = None
    ev_to_ebit: float | None = None
    interest_expense: float | None = None
    total_debt: float | None = None
    issuance_or_purchase_of_equity_shares: float | None = None
```

Note: `interest_coverage` already exists at line 50 — do not add it again.

- [ ] **Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/test_models.py::test_financial_metrics_has_new_fields -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/data/models.py tests/test_models.py
git commit -m "feat: add D&A, EBIT, EBITDA, ev_to_ebit, interest_expense, total_debt, equity_change fields to FinancialMetrics"
```

---

## Task 2: Extract New Fields in Xueqiu HK Metrics

**Files:**
- Modify: `src/markets/sources/xueqiu_source.py:409-507` (`_build_hk_metrics`)
- Modify: `tests/markets/sources/test_xueqiu_source.py` (add to `TestXueqiuSourceHKFinancialMetrics`)

- [ ] **Step 1: Write failing tests for HK new fields**

In `tests/markets/sources/test_xueqiu_source.py`, add these class-level mock data dicts and test method to `TestXueqiuSourceHKFinancialMetrics` (after the existing `MOCK_BALANCE` dict, before `_make_source`):

```python
    MOCK_CASH_FLOW_WITH_NEW_FIELDS = {
        "nocf": [43700000000.0, 0.10],
        "adtfxda": [-5000000000.0, 0.05],
        "ninvcf": [-10000000000.0, 0.02],
        "nfcgcf": [-8000000000.0, 0.01],
        "da": [3000000000.0, 0.08],
        "finexp": [1500000000.0, 0.03],
        "cdp": [-2000000000.0, -0.05],
        "csi": [500000000.0, 0.01],
        "crpcs": [-1000000000.0, 0.02],
        "report_date": 1735574400000,
    }
    MOCK_BALANCE_WITH_DEBT = {
        "ta": [500000000000.0, 0.05],
        "tlia": [234000000000.0, 0.03],
        "shhfd": [266000000000.0, 0.07],
        "cceq": [50000000000.0, 0.10],
        "ca": [120000000000.0, 0.04],
        "clia": [62000000000.0, 0.02],
        "std": [20000000000.0, 0.01],
        "ltd": [30000000000.0, 0.02],
        "report_date": 1735574400000,
    }

    def _make_source_with_new_fields(self, mocker):
        """Like _make_source but uses MOCK_CASH_FLOW_WITH_NEW_FIELDS and MOCK_BALANCE_WITH_DEBT."""
        source = XueqiuSource()
        source._token_initialized = True

        def mock_fetch(endpoint, symbol, market):
            mapping = {
                "indicator": [self.MOCK_INDICATOR],
                "income": [self.MOCK_INCOME],
                "cash_flow": [self.MOCK_CASH_FLOW_WITH_NEW_FIELDS],
                "balance": [self.MOCK_BALANCE_WITH_DEBT],
            }
            return mapping.get(endpoint, [])

        def mock_fetch_multi(endpoint, symbol, market, count="10"):
            mapping = {
                "indicator": [self.MOCK_INDICATOR],
                "income": [self.MOCK_INCOME],
                "cash_flow": [self.MOCK_CASH_FLOW_WITH_NEW_FIELDS],
                "balance": [self.MOCK_BALANCE_WITH_DEBT],
            }
            return mapping.get(endpoint, [])

        mocker.patch.object(source, "_fetch_financial_data", side_effect=mock_fetch)
        mocker.patch.object(source, "_fetch_financial_data_multi", side_effect=mock_fetch_multi)
        return source

    def test_hk_metrics_extracts_depreciation(self, mocker):
        result = self._make_source_with_new_fields(mocker).get_financial_metrics("03690", "2025-01-01")
        assert result is not None
        assert result["depreciation_and_amortization"] == pytest.approx(3000000000.0)

    def test_hk_metrics_extracts_interest_expense(self, mocker):
        result = self._make_source_with_new_fields(mocker).get_financial_metrics("03690", "2025-01-01")
        assert result["interest_expense"] == pytest.approx(1500000000.0)

    def test_hk_metrics_extracts_total_debt(self, mocker):
        result = self._make_source_with_new_fields(mocker).get_financial_metrics("03690", "2025-01-01")
        assert result["total_debt"] == pytest.approx(50000000000.0)  # std(20B) + ltd(30B)

    def test_hk_metrics_extracts_dividends_as_positive(self, mocker):
        result = self._make_source_with_new_fields(mocker).get_financial_metrics("03690", "2025-01-01")
        assert result["dividends"] == pytest.approx(2000000000.0)  # abs(cdp=-2B)

    def test_hk_metrics_extracts_equity_change(self, mocker):
        result = self._make_source_with_new_fields(mocker).get_financial_metrics("03690", "2025-01-01")
        # csi=500M (positive inflow) + crpcs=-1000M (negative outflow) = -500M net
        assert result["issuance_or_purchase_of_equity_shares"] == pytest.approx(-500000000.0)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py::TestXueqiuSourceHKFinancialMetrics::test_hk_metrics_extracts_depreciation -v
```
Expected: FAIL (field returns None)

- [ ] **Step 3: Add field extraction to `_build_hk_metrics`**

In `src/markets/sources/xueqiu_source.py`, in `_build_hk_metrics`, after the existing `capex`/`fcf` calculation block (after line ~431), add:

```python
        # D&A and interest expense from cash flow
        da = ev(cash_flow.get("da"))
        interest_exp = ev(cash_flow.get("finexp"))

        # Dividends paid: cdp is typically negative — store as positive amount
        cdp_raw = ev(cash_flow.get("cdp"))
        dividends_paid = abs(cdp_raw) if cdp_raw is not None else None

        # Net equity change: csi (positive inflow) + crpcs (negative outflow)
        csi = ev(cash_flow.get("csi"))
        crpcs = ev(cash_flow.get("crpcs"))
        if csi is not None or crpcs is not None:
            issuance_or_purchase = (csi or 0.0) + (crpcs or 0.0)
        else:
            issuance_or_purchase = None

        # Total debt = short-term debt + long-term debt
        std = ev(balance.get("std"))
        ltd = ev(balance.get("ltd"))
        if std is not None or ltd is not None:
            total_debt = (std or 0.0) + (ltd or 0.0)
        else:
            total_debt = None
```

Then add these fields to the `result` dict in `_build_hk_metrics`, after the `# Cash flow` section:

```python
            # Fields for DCF and value investing agents
            "depreciation_and_amortization": da,
            "interest_expense": interest_exp,
            "dividends": dividends_paid,
            "issuance_or_purchase_of_equity_shares": issuance_or_purchase,
            "total_debt": total_debt,
```

- [ ] **Step 4: Run new tests to verify they pass**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py::TestXueqiuSourceHKFinancialMetrics::test_hk_metrics_extracts_depreciation tests/markets/sources/test_xueqiu_source.py::TestXueqiuSourceHKFinancialMetrics::test_hk_metrics_extracts_interest_expense tests/markets/sources/test_xueqiu_source.py::TestXueqiuSourceHKFinancialMetrics::test_hk_metrics_extracts_total_debt tests/markets/sources/test_xueqiu_source.py::TestXueqiuSourceHKFinancialMetrics::test_hk_metrics_extracts_dividends_as_positive tests/markets/sources/test_xueqiu_source.py::TestXueqiuSourceHKFinancialMetrics::test_hk_metrics_extracts_equity_change -v
```
Expected: All PASS

- [ ] **Step 5: Run full xueqiu test suite to check no regressions**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py -v
```
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/markets/sources/xueqiu_source.py tests/markets/sources/test_xueqiu_source.py
git commit -m "feat: extract D&A, interest_expense, dividends, total_debt, equity_change from Xueqiu HK"
```

---

## Task 3: Extract New Fields in Xueqiu CN Metrics

**Files:**
- Modify: `src/markets/sources/xueqiu_source.py:509-599` (`_build_cn_metrics`)
- Modify: `tests/markets/sources/test_xueqiu_source.py` (add `TestXueqiuSourceCNNewFields`)

**CN sign convention note:** For CN stocks, `cash_paid_for_repurchasing_shares` is stored as a positive outflow amount (not signed negative). The implementation subtracts it: `equity_net = issued - repurchased`.

- [ ] **Step 1: Write failing tests for CN new fields**

In `tests/markets/sources/test_xueqiu_source.py`, add a new test class after `TestXueqiuSourceCNFinancialMetrics`:

```python
class TestXueqiuSourceCNNewFields:
    MOCK_CN_INDICATOR = {
        "avg_roe": [15.0, 0.05],
        "net_interest_of_total_assets": [8.0, 0.02],
        "gross_selling_rate": [45.0, 0.01],
        "net_selling_rate": [12.0, 0.03],
        "asset_liab_ratio": [40.0, -0.01],
        "current_ratio": [2.1, 0.05],
        "quick_ratio": [1.8, 0.04],
        "basic_eps": [3.5, 0.10],
        "np_per_share": [25.0, 0.08],
        "operate_cash_flow_ps": [5.0, 0.06],
        "report_date": 1735574400000,
    }
    MOCK_CN_INCOME = {
        "total_revenue": [200000000000.0, 0.15],
        "net_profit": [24000000000.0, 0.12],
        "operate_profit": [28000000000.0, 0.10],
        "gross_profit": [90000000000.0, 0.14],
        "research_and_development_costs": [5000000000.0, 0.20],
        "report_date": 1735574400000,
    }
    MOCK_CN_CASH_FLOW = {
        "ncf_from_oa": [30000000000.0, 0.08],
        "cash_paid_for_assets": [5000000000.0, 0.05],
        "ncf_from_ia": [-8000000000.0, 0.02],
        "ncf_from_fa": [-5000000000.0, 0.01],
        "depreciation_and_amortization": [2000000000.0, 0.06],
        "interest_expense": [800000000.0, 0.03],
        "cash_paid_for_dividend_profit": [1500000000.0, -0.02],   # positive outflow
        "cash_received_from_issuing_shares": [300000000.0, 0.01],  # positive inflow
        "cash_paid_for_repurchasing_shares": [600000000.0, 0.02],  # positive outflow
        "report_date": 1735574400000,
    }
    MOCK_CN_BALANCE = {
        "total_assets": [300000000000.0, 0.05],
        "total_liab": [120000000000.0, 0.03],
        "total_holders_equity": [180000000000.0, 0.07],
        "currency_funds": [40000000000.0, 0.10],
        "total_current_assets": [80000000000.0, 0.04],
        "total_current_liab": [38000000000.0, 0.02],
        "short_term_loan": [15000000000.0, 0.01],
        "long_term_loan": [25000000000.0, 0.02],
        "report_date": 1735574400000,
    }

    def _make_cn_source(self, mocker):
        source = XueqiuSource()
        source._token_initialized = True

        def mock_fetch(endpoint, symbol, market):
            mapping = {
                "indicator": [self.MOCK_CN_INDICATOR],
                "income": [self.MOCK_CN_INCOME],
                "cash_flow": [self.MOCK_CN_CASH_FLOW],
                "balance": [self.MOCK_CN_BALANCE],
            }
            return mapping.get(endpoint, [])

        def mock_fetch_multi(endpoint, symbol, market, count="10"):
            mapping = {
                "indicator": [self.MOCK_CN_INDICATOR],
                "income": [self.MOCK_CN_INCOME],
                "cash_flow": [self.MOCK_CN_CASH_FLOW],
                "balance": [self.MOCK_CN_BALANCE],
            }
            return mapping.get(endpoint, [])

        mocker.patch.object(source, "_fetch_financial_data", side_effect=mock_fetch)
        mocker.patch.object(source, "_fetch_financial_data_multi", side_effect=mock_fetch_multi)
        return source

    def test_cn_metrics_extracts_depreciation(self, mocker):
        result = self._make_cn_source(mocker).get_financial_metrics("600519", "2025-01-01")
        assert result is not None
        assert result["depreciation_and_amortization"] == pytest.approx(2000000000.0)

    def test_cn_metrics_extracts_interest_expense(self, mocker):
        result = self._make_cn_source(mocker).get_financial_metrics("600519", "2025-01-01")
        assert result["interest_expense"] == pytest.approx(800000000.0)

    def test_cn_metrics_extracts_dividends(self, mocker):
        result = self._make_cn_source(mocker).get_financial_metrics("600519", "2025-01-01")
        assert result["dividends"] == pytest.approx(1500000000.0)

    def test_cn_metrics_extracts_total_debt(self, mocker):
        result = self._make_cn_source(mocker).get_financial_metrics("600519", "2025-01-01")
        assert result["total_debt"] == pytest.approx(40000000000.0)  # 15B + 25B

    def test_cn_metrics_extracts_equity_change(self, mocker):
        result = self._make_cn_source(mocker).get_financial_metrics("600519", "2025-01-01")
        # issued=300M - repurchased=600M = -300M net
        assert result["issuance_or_purchase_of_equity_shares"] == pytest.approx(-300000000.0)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py::TestXueqiuSourceCNNewFields -v
```
Expected: All FAIL

- [ ] **Step 3: Add field extraction to `_build_cn_metrics`**

In `src/markets/sources/xueqiu_source.py`, in `_build_cn_metrics`, after the existing `capex`/`fcf` calculation block (after line ~531), add:

```python
        # D&A and interest expense from cash flow
        da = ev(cash_flow.get("depreciation_and_amortization"))
        interest_exp = ev(cash_flow.get("interest_expense"))

        # Dividends paid (stored as positive outflow amount in CN)
        dividends_raw = ev(cash_flow.get("cash_paid_for_dividend_profit"))
        dividends_paid = abs(dividends_raw) if dividends_raw is not None else None

        # Net equity change: issuance (positive inflow) - repurchase (positive outflow)
        issued = ev(cash_flow.get("cash_received_from_issuing_shares"))
        repurchased = ev(cash_flow.get("cash_paid_for_repurchasing_shares"))
        if issued is not None or repurchased is not None:
            issuance_or_purchase = (issued or 0.0) - (repurchased or 0.0)
        else:
            issuance_or_purchase = None

        # Total debt = short-term loan + long-term loan
        std = ev(balance.get("short_term_loan"))
        ltd = ev(balance.get("long_term_loan"))
        if std is not None or ltd is not None:
            total_debt = (std or 0.0) + (ltd or 0.0)
        else:
            total_debt = None
```

Then add to the `result` dict in `_build_cn_metrics`, after the `# Cash flow` section:

```python
            # Fields for DCF and value investing agents
            "depreciation_and_amortization": da,
            "interest_expense": interest_exp,
            "dividends": dividends_paid,
            "issuance_or_purchase_of_equity_shares": issuance_or_purchase,
            "total_debt": total_debt,
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py::TestXueqiuSourceCNNewFields -v
```
Expected: All PASS

- [ ] **Step 5: Run full test suite**

```bash
poetry run pytest tests/ -v --tb=short
```
Expected: All PASS (or pre-existing failures only)

- [ ] **Step 6: Commit**

```bash
git add src/markets/sources/xueqiu_source.py tests/markets/sources/test_xueqiu_source.py
git commit -m "feat: extract D&A, interest_expense, dividends, total_debt, equity_change from Xueqiu CN"
```

---

## Task 4: Add EBIT, EBITDA, ev_to_ebit, interest_coverage to Derived Metrics

**Files:**
- Modify: `src/markets/sources/xueqiu_source.py:91-156` (`_compute_derived_metrics`)
- Modify: `tests/markets/sources/test_xueqiu_source.py` (add `TestXueqiuDerivedMetrics`)

**EBIT semantic note:** For HK/CN stocks, `operating_income` is used as the EBIT proxy (pre-interest, pre-tax, includes D&A). This is standard practice for these markets. The guard `if metrics.get("ebit") is None` ensures a real EBIT value from another source is never overwritten.

**Insertion point:** The new code is appended at the end of `_compute_derived_metrics`, inside the same method body, after the existing `debt_to_equity` calculation (line ~155). The local variable `ev` (enterprise_value) is already bound at line ~127 and will be in scope.

- [ ] **Step 1: Write failing tests**

In `tests/markets/sources/test_xueqiu_source.py`, add a new test class:

```python
class TestXueqiuDerivedMetrics:
    def test_ebit_computed_from_operating_income(self):
        source = XueqiuSource()
        metrics = {"operating_income": 38000000000.0}
        source._compute_derived_metrics(metrics)
        assert metrics["ebit"] == pytest.approx(38000000000.0)

    def test_ebit_not_overwritten_if_already_set(self):
        source = XueqiuSource()
        metrics = {"ebit": 99.0, "operating_income": 38000000000.0}
        source._compute_derived_metrics(metrics)
        assert metrics["ebit"] == pytest.approx(99.0)  # not overwritten

    def test_ebitda_computed_from_ebit_and_da(self):
        source = XueqiuSource()
        metrics = {"operating_income": 38000000000.0, "depreciation_and_amortization": 3000000000.0}
        source._compute_derived_metrics(metrics)
        assert metrics["ebitda"] == pytest.approx(41000000000.0)

    def test_ev_to_ebit_computed(self):
        source = XueqiuSource()
        metrics = {
            "market_cap": 500000000000.0,
            "total_liabilities": 150000000000.0,
            "cash_and_equivalents": 50000000000.0,
            "operating_income": 38000000000.0,
        }
        source._compute_derived_metrics(metrics)
        # EV = 500B + 150B - 50B = 600B; ev_to_ebit = 600B / 38B ≈ 15.79
        assert metrics["ev_to_ebit"] == pytest.approx(600000000000.0 / 38000000000.0, rel=0.01)

    def test_interest_coverage_computed(self):
        source = XueqiuSource()
        metrics = {"operating_income": 38000000000.0, "interest_expense": 1500000000.0}
        source._compute_derived_metrics(metrics)
        assert metrics["interest_coverage"] == pytest.approx(38000000000.0 / 1500000000.0, rel=0.01)

    def test_interest_coverage_none_when_no_interest(self):
        source = XueqiuSource()
        metrics = {"operating_income": 38000000000.0}
        source._compute_derived_metrics(metrics)
        assert metrics.get("interest_coverage") is None

    def test_ev_to_ebitda_computed(self):
        source = XueqiuSource()
        metrics = {
            "market_cap": 500000000000.0,
            "total_liabilities": 150000000000.0,
            "cash_and_equivalents": 50000000000.0,
            "operating_income": 38000000000.0,
            "depreciation_and_amortization": 3000000000.0,
        }
        source._compute_derived_metrics(metrics)
        # EV = 600B; EBITDA = 38B + 3B = 41B; ratio = 600B / 41B
        assert metrics["enterprise_value_to_ebitda_ratio"] == pytest.approx(600e9 / 41e9, rel=0.01)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py::TestXueqiuDerivedMetrics -v
```
Expected: All FAIL

- [ ] **Step 3: Add EBIT, EBITDA, ev_to_ebit, interest_coverage to `_compute_derived_metrics`**

In `src/markets/sources/xueqiu_source.py`, at the end of `_compute_derived_metrics` (after the `debt_to_equity` block, still inside the method), add:

```python
        # ebit = operating_income (pre-interest, pre-tax proxy for HK/CN stocks)
        if metrics.get("ebit") is None:
            oi = get("operating_income")
            if oi is not None:
                metrics["ebit"] = oi

        ebit = metrics.get("ebit")

        # ebitda = ebit + depreciation_and_amortization
        if metrics.get("ebitda") is None:
            da = get("depreciation_and_amortization")
            if ebit is not None and da is not None:
                metrics["ebitda"] = ebit + da

        ebitda = metrics.get("ebitda")

        # enterprise_value_to_ebitda_ratio = EV / EBITDA
        if metrics.get("enterprise_value_to_ebitda_ratio") is None:
            metrics["enterprise_value_to_ebitda_ratio"] = safe_div(ev, ebitda)

        # ev_to_ebit = EV / EBIT (Michael Burry's key metric)
        if metrics.get("ev_to_ebit") is None:
            metrics["ev_to_ebit"] = safe_div(ev, ebit)

        # interest_coverage = EBIT / interest_expense
        if metrics.get("interest_coverage") is None:
            ie = get("interest_expense")
            metrics["interest_coverage"] = safe_div(ebit, ie)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py::TestXueqiuDerivedMetrics -v
```
Expected: All PASS

- [ ] **Step 5: Run full test suite**

```bash
poetry run pytest tests/ -v --tb=short
```
Expected: All PASS (or pre-existing failures only)

- [ ] **Step 6: Commit**

```bash
git add src/markets/sources/xueqiu_source.py tests/markets/sources/test_xueqiu_source.py
git commit -m "feat: compute EBIT, EBITDA, ev_to_ebit, interest_coverage in _compute_derived_metrics"
```

---

## Task 5: Verify Against Live Data (Smoke Test)

**Files:** None — runtime verification only

The `api.py` `field_mapping` already works correctly for pass-through fields via its fallback `field_mapping.get(requested_field, requested_field)`. The only alias needed (`dividends_and_other_cash_distributions` → `dividends`) is already in place. No changes to `api.py` are needed.

- [ ] **Step 1: Run smoke test against 3690.HK**

```bash
cd /Users/luobotao/.openclaw/workspace/ai-hedge-fund
poetry run python -c "
from src.tools.api import search_line_items, get_financial_metrics
from datetime import date

ticker = '3690.HK'
end_date = str(date.today())

# Test get_financial_metrics (returns list[FinancialMetrics] for all markets)
raw = get_financial_metrics(ticker, end_date)
if raw:
    m = raw[0] if isinstance(raw, list) else raw
    print('=== FinancialMetrics ===')
    for field in ['depreciation_and_amortization', 'ebit', 'ebitda', 'ev_to_ebit',
                  'interest_expense', 'total_debt', 'dividends', 'interest_coverage']:
        val = m.get(field) if isinstance(m, dict) else getattr(m, field, 'N/A')
        print(f'  {field}: {val}')
else:
    print('No metrics returned')

# Test search_line_items (all agent-requested fields)
items = search_line_items(
    ticker,
    ['depreciation_and_amortization', 'ebit', 'interest_expense',
     'total_debt', 'dividends_and_other_cash_distributions',
     'issuance_or_purchase_of_equity_shares', 'free_cash_flow', 'net_income'],
    end_date, period='ttm', limit=1
)
if items:
    item = items[0]
    print('\n=== LineItems ===')
    for field in ['depreciation_and_amortization', 'ebit', 'interest_expense',
                  'total_debt', 'dividends_and_other_cash_distributions',
                  'issuance_or_purchase_of_equity_shares', 'free_cash_flow']:
        print(f'  {field}: {getattr(item, field, None)}')
else:
    print('No line items returned')
"
```

Expected: All 6 critical fields show non-None values.

- [ ] **Step 2: If any field is still None, print raw Xueqiu API keys to find correct field names**

```bash
poetry run python -c "
from src.markets.sources.xueqiu_source import XueqiuSource
src = XueqiuSource()
src._ensure_token()
print('=== HK Cash Flow keys ===')
cf = src._fetch_financial_data('cash_flow', '03690', 'HK')
if cf:
    print('All keys:', sorted(cf[0].keys()))
    for k in ['da', 'finexp', 'cdp', 'csi', 'crpcs']:
        print(f'  {k}: {cf[0].get(k)}')
print('=== HK Balance keys ===')
bl = src._fetch_financial_data('balance', '03690', 'HK')
if bl:
    print('All keys:', sorted(bl[0].keys()))
    for k in ['std', 'ltd']:
        print(f'  {k}: {bl[0].get(k)}')
"
```

- [ ] **Step 3: If field names are wrong, update `_build_hk_metrics` with correct names, re-run smoke test**

- [ ] **Step 4: Repeat Steps 2-3 for CN stocks if needed (use symbol `SH600519`, market `CN`)**

- [ ] **Step 5: Final full test run**

```bash
poetry run pytest tests/ -v --tb=short
```

- [ ] **Step 6: Final commit if any field name corrections were made**

```bash
git add src/markets/sources/xueqiu_source.py
git commit -m "fix: correct Xueqiu raw field names for HK/CN missing financial data (verified against live API)"
```

---

## Summary of Changes

| Layer | File | What Changes |
|-------|------|-------------|
| Data Model | `src/data/models.py` | +7 new fields: `depreciation_and_amortization`, `ebit`, `ebitda`, `ev_to_ebit`, `interest_expense`, `total_debt`, `issuance_or_purchase_of_equity_shares` |
| HK Source | `xueqiu_source.py:_build_hk_metrics` | Extract D&A (`da`), interest (`finexp`), dividends (`cdp`), equity change (`csi`+`crpcs`), total_debt (`std`+`ltd`) |
| CN Source | `xueqiu_source.py:_build_cn_metrics` | Extract same fields using CN-specific Xueqiu key names |
| Derived | `xueqiu_source.py:_compute_derived_metrics` | Compute `ebit`, `ebitda`, `ev_to_ebit`, `interest_coverage`, `enterprise_value_to_ebitda_ratio` |
| Pipeline | `src/tools/api.py` | No change needed — existing fallback in `field_mapping` already handles pass-through fields |

**Agent Impact After Fix:**
- Warren Buffett: 8/12 → 11/12 fields (D&A, dividends, equity_change now available)
- Aswath Damodaran: 4/8 → 8/8 fields (EBIT, interest_expense, total_debt, D&A now available)
- Michael Burry: 6/8 → 8/8 fields (total_debt, equity_change now available)
- Ben Graham: 9/10 → 10/10 fields (dividends now available)
