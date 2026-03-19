# XueqiuSource 实现计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增雪球(Xueqiu)数据源，为港股和A股补充完整的财务报表数据（现金流量表、资产负债表明细），解决当前港股财务数据严重缺失（26/51字段）的问题。

**Architecture:** 分两步：①先扩展 `FinancialMetrics` 模型，新增现金流、资产负债表等字段；②新建 `XueqiuSource` 类继承 `DataSource` 基类，通过雪球公开API获取四张财务报表并聚合。雪球API需先调用screener接口触发token（无需登录账号）。港股和A股使用不同API路径（`/hk/` vs `/cn/`）。将XueqiuSource加入HKStockAdapter（第一优先级）和CNStockAdapter（第二优先级）。

**Tech Stack:** Python requests, 雪球公开API (stock.xueqiu.com), Pydantic

---

## Chunk 1: 扩展 FinancialMetrics 模型

### Task 1: 在 FinancialMetrics 中新增财务报表字段

**Files:**
- Modify: `src/data/models.py:18-72`
- Test: `tests/test_models.py`（如不存在则创建）

当前 `FinancialMetrics` 缺少的关键字段（均来自雪球财务报表）：
- 现金流: `operating_cash_flow`, `capital_expenditure`, `investing_cash_flow`, `financing_cash_flow`
- 资产负债表: `cash_and_equivalents`, `current_assets`, `current_liabilities`
- 利润表: `gross_profit`, `operating_income`, `research_and_development`
- 每股: `operating_cash_flow_per_share`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_models.py
from src.data.models import FinancialMetrics


def test_financial_metrics_has_cash_flow_fields():
    m = FinancialMetrics(
        ticker="03690", report_period="2024-12-31",
        period="ttm", currency="HKD",
        operating_cash_flow=57146784000.0,
        capital_expenditure=10999490000.0,
        investing_cash_flow=10205252000.0,
        financing_cash_flow=-30414660000.0,
    )
    assert m.operating_cash_flow == 57146784000.0
    assert m.capital_expenditure == 10999490000.0
    assert m.investing_cash_flow == 10205252000.0
    assert m.financing_cash_flow == -30414660000.0


def test_financial_metrics_has_balance_sheet_fields():
    m = FinancialMetrics(
        ticker="03690", report_period="2024-12-31",
        period="ttm", currency="HKD",
        cash_and_equivalents=90383717000.0,
        current_assets=209734861000.0,
        current_liabilities=107935640000.0,
    )
    assert m.cash_and_equivalents == 90383717000.0
    assert m.current_assets == 209734861000.0
    assert m.current_liabilities == 107935640000.0


def test_financial_metrics_has_income_statement_fields():
    m = FinancialMetrics(
        ticker="03690", report_period="2024-12-31",
        period="ttm", currency="HKD",
        gross_profit=129784594000.0,
        operating_income=37985429000.0,
        research_and_development=21053601000.0,
    )
    assert m.gross_profit == 129784594000.0
    assert m.operating_income == 37985429000.0
    assert m.research_and_development == 21053601000.0


def test_financial_metrics_new_fields_default_to_none():
    m = FinancialMetrics(
        ticker="AAPL", report_period="2024-12-31",
        period="ttm", currency="USD",
    )
    assert m.operating_cash_flow is None
    assert m.capital_expenditure is None
    assert m.cash_and_equivalents is None
    assert m.gross_profit is None
    assert m.research_and_development is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/luobotao/.openclaw/workspace/ai-hedge-fund
poetry run pytest tests/test_models.py -v 2>&1 | head -30
```
期望: `ValidationError` 或 `TypeError`（字段不存在）

- [ ] **Step 3: 扩展 FinancialMetrics 模型**

在 `src/data/models.py` 的 `FinancialMetrics` 类中，在 `outstanding_shares` 字段后追加：

```python
    # Cash flow statement fields
    operating_cash_flow: float | None = None
    capital_expenditure: float | None = None
    investing_cash_flow: float | None = None
    financing_cash_flow: float | None = None

    # Balance sheet detail fields
    cash_and_equivalents: float | None = None
    current_assets: float | None = None
    current_liabilities: float | None = None

    # Income statement detail fields
    gross_profit: float | None = None
    operating_income: float | None = None
    research_and_development: float | None = None

    # Per share metrics
    operating_cash_flow_per_share: float | None = None
```

- [ ] **Step 4: 运行测试确认通过**

```bash
poetry run pytest tests/test_models.py -v
```
期望: 所有 4 个测试 PASS

- [ ] **Step 5: 确认现有测试不受影响**

```bash
poetry run pytest tests/ -v --tb=short -q 2>&1 | tail -15
```
期望: 无新增失败

- [ ] **Step 6: Commit**

```bash
git add src/data/models.py tests/test_models.py
git commit -m "feat: add cash flow, balance sheet, and income statement fields to FinancialMetrics"
```

---

## Chunk 2: XueqiuSource 核心实现

### Task 2: 新建 XueqiuSource 文件骨架和 token 初始化

**Files:**
- Create: `src/markets/sources/xueqiu_source.py`
- Test: `tests/markets/sources/test_xueqiu_source.py`

雪球API工作机制：
- 先调用 screener 接口触发 `xq_a_token` cookie 生成（无需登录）
- 之后所有请求复用同一 session，token 自动附带
- 当请求返回 `error_code: 400016` 时需重新初始化

- [ ] **Step 1: 写失败测试**

```python
# tests/markets/sources/test_xueqiu_source.py
import pytest
from unittest.mock import patch, MagicMock
from src.markets.sources.xueqiu_source import XueqiuSource


class TestXueqiuSourceInit:
    def test_supports_hk_market(self):
        source = XueqiuSource()
        assert source.supports_market("HK") is True

    def test_supports_cn_market(self):
        source = XueqiuSource()
        assert source.supports_market("CN") is True

    def test_does_not_support_us_market(self):
        source = XueqiuSource()
        assert source.supports_market("US") is False

    def test_source_name(self):
        source = XueqiuSource()
        assert source.name == "Xueqiu"

    def test_to_xueqiu_symbol_hk(self):
        source = XueqiuSource()
        assert source._to_xueqiu_symbol("03690", "HK") == "03690"
        assert source._to_xueqiu_symbol("00700", "HK") == "00700"

    def test_to_xueqiu_symbol_cn_sh(self):
        source = XueqiuSource()
        # 6开头 → 上交所
        assert source._to_xueqiu_symbol("600519", "CN") == "SH600519"
        assert source._to_xueqiu_symbol("600000", "CN") == "SH600000"

    def test_to_xueqiu_symbol_cn_sz(self):
        source = XueqiuSource()
        # 0开头 → 深交所
        assert source._to_xueqiu_symbol("000001", "CN") == "SZ000001"
        assert source._to_xueqiu_symbol("000002", "CN") == "SZ000002"

    def test_to_xueqiu_symbol_cn_gem(self):
        source = XueqiuSource()
        # 3开头（创业板）→ 深交所
        assert source._to_xueqiu_symbol("300750", "CN") == "SZ300750"

    def test_get_prices_returns_empty_list(self):
        source = XueqiuSource()
        assert source.get_prices("03690", "2024-01-01", "2024-12-31") == []

    def test_get_company_news_returns_empty_list(self):
        source = XueqiuSource()
        assert source.get_company_news("03690", "2024-12-31") == []

    def test_returns_none_when_token_init_fails(self, mocker):
        source = XueqiuSource()
        mocker.patch.object(source, "_ensure_token", return_value=False)
        result = source.get_financial_metrics("03690", "2025-01-01")
        assert result is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py -v 2>&1 | head -20
```
期望: `ModuleNotFoundError: No module named 'src.markets.sources.xueqiu_source'`

- [ ] **Step 3: 实现骨架**

创建 `src/markets/sources/xueqiu_source.py`：

```python
"""雪球(Xueqiu)数据源，支持港股和A股完整财务报表数据。"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests

from src.markets.sources.base import DataSource


class XueqiuSource(DataSource):
    """
    雪球数据源，提供港股和A股的完整财务报表数据。

    雪球API无需登录，但需先调用screener接口触发 xq_a_token cookie 生成。
    Token有效期约30天，存储在session中自动复用。

    支持的数据类型:
    - 财务指标 (indicator): ROE, 毛利率, 流动比率等
    - 利润表 (income): 营收, 净利润, 毛利润, 研发费用等
    - 现金流量表 (cash_flow): 经营/投资/融资现金流, 资本支出
    - 资产负债表 (balance): 总资产, 总负债, 现金及等价物等

    港股 symbol: "03690"（5位数字）
    A股 symbol: "SH600519" 或 "SZ000001"
    """

    BASE_URL = "https://stock.xueqiu.com/v5/stock/finance"
    TOKEN_INIT_URL = (
        "https://xueqiu.com/service/v5/stock/screener/quote/list"
        "?page=1&size=1&order=desc&orderby=percent&market=CN&type=sh_sz"
    )

    def __init__(self):
        super().__init__("Xueqiu")
        self._session: Optional[requests.Session] = None
        self._token_initialized = False

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://xueqiu.com/",
            })
        return self._session

    def _ensure_token(self) -> bool:
        """确保 xq_a_token cookie 已生成。首次调用时触发初始化。"""
        if self._token_initialized:
            return True
        try:
            r = self.session.get(self.TOKEN_INIT_URL, timeout=10)
            if r.status_code == 200 and "xq_a_token" in self.session.cookies:
                self._token_initialized = True
                self.logger.debug("[Xueqiu] Token initialized successfully")
                return True
            self.logger.warning(
                f"[Xueqiu] Token init failed: status={r.status_code}, "
                f"has_token={'xq_a_token' in self.session.cookies}"
            )
            return False
        except Exception as e:
            self.logger.error(f"[Xueqiu] Token init error: {e}")
            return False

    def supports_market(self, market: str) -> bool:
        return market.upper() in ("HK", "CN")

    def _to_xueqiu_symbol(self, ticker: str, market: str) -> str:
        """
        将内部 ticker 转换为雪球 symbol 格式。
        HK: "03690" → "03690"（保持5位）
        CN: "600519" → "SH600519"，"000001" → "SZ000001"，"300750" → "SZ300750"
        """
        if market.upper() == "HK":
            return ticker.zfill(5)
        # CN: 6开头 → 上交所，其他（0/3开头）→ 深交所
        if ticker.startswith("6"):
            return f"SH{ticker}"
        return f"SZ{ticker}"

    def _safe_float(self, value) -> Optional[float]:
        """安全转换为 float，失败返回 None。"""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _extract_value(self, field_data) -> Optional[float]:
        """
        雪球财务数据格式为 [当期值, 同比增长率]，取第一个元素。
        注意: report_date 是整数时间戳，不应通过此方法提取。
        """
        if field_data is None:
            return None
        if isinstance(field_data, list) and len(field_data) >= 1:
            return self._safe_float(field_data[0])
        return self._safe_float(field_data)

    def _parse_report_period(self, report_date_ms) -> str:
        """将毫秒时间戳转换为 YYYY-MM-DD 格式。"""
        if not report_date_ms:
            return ""
        try:
            dt = datetime.fromtimestamp(int(report_date_ms) / 1000, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return ""

    def _fetch_financial_data(
        self, endpoint: str, symbol: str, market: str
    ) -> List[Dict]:
        """
        从雪球财务API获取数据。
        endpoint: "indicator" | "income" | "cash_flow" | "balance"
        返回 list of period dicts，最新期在前。失败返回空列表。
        """
        mkt = market.lower()
        url = f"{self.BASE_URL}/{mkt}/{endpoint}.json"
        params = {"symbol": symbol, "type": "Q4", "is_detail": "true", "count": "5"}
        try:
            r = self.session.get(url, params=params, timeout=10)
            if r.status_code != 200:
                self.logger.warning(
                    f"[Xueqiu] {endpoint} for {symbol} returned {r.status_code}"
                )
                return []
            data = r.json()
            return data.get("data", {}).get("list", []) or []
        except Exception as e:
            self.logger.error(f"[Xueqiu] Error fetching {endpoint} for {symbol}: {e}")
            return []

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Dict]:
        """雪球不提供历史价格数据，返回空列表。"""
        return []

    def get_company_news(
        self, ticker: str, end_date: str,
        start_date: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """雪球不提供新闻数据，返回空列表。"""
        return []

    def get_financial_metrics(
        self, ticker: str, end_date: str,
        period: str = "ttm", limit: int = 10
    ) -> Optional[Dict]:
        """获取港股或A股财务指标，聚合四张报表数据。失败返回 None。"""
        if not self._ensure_token():
            self.logger.warning("[Xueqiu] Cannot get token, skipping")
            return None

        # 判断市场：纯6位数字 = CN，SH/SZ前缀 = CN，其他 = HK
        if (len(ticker) == 6 and ticker.isdigit()) or ticker.startswith(("SH", "SZ")):
            market = "CN"
            symbol = ticker if ticker.startswith(("SH", "SZ")) else self._to_xueqiu_symbol(ticker, "CN")
        else:
            market = "HK"
            symbol = ticker.zfill(5)

        self.logger.info(f"[Xueqiu] Fetching financial metrics for {symbol} ({market})")

        indicator_list = self._fetch_financial_data("indicator", symbol, market)
        income_list = self._fetch_financial_data("income", symbol, market)
        cash_flow_list = self._fetch_financial_data("cash_flow", symbol, market)
        balance_list = self._fetch_financial_data("balance", symbol, market)

        indicator = indicator_list[0] if indicator_list else {}
        income = income_list[0] if income_list else {}
        cash_flow = cash_flow_list[0] if cash_flow_list else {}
        balance = balance_list[0] if balance_list else {}

        if not any([indicator, income, cash_flow, balance]):
            self.logger.warning(f"[Xueqiu] No financial data available for {symbol}")
            return None

        if market == "HK":
            metrics = self._build_hk_metrics(ticker, indicator, income, cash_flow, balance)
        else:
            metrics = self._build_cn_metrics(ticker, indicator, income, cash_flow, balance)

        non_null = sum(1 for v in metrics.values() if v is not None and v != "")
        self.logger.info(
            f"[Xueqiu] ✓ Got {market} financial metrics for {symbol}: "
            f"{non_null}/{len(metrics)} fields populated"
        )
        return metrics

    def _build_hk_metrics(
        self, ticker: str, indicator: Dict, income: Dict,
        cash_flow: Dict, balance: Dict,
    ) -> Dict:
        """港股四张报表聚合。百分比字段除以100转为小数。"""
        ev = self._extract_value

        roe_raw = ev(indicator.get("roe"))
        roa_raw = ev(indicator.get("rota"))
        gpm_raw = ev(indicator.get("gpm"))
        opm_raw = ev(indicator.get("opemg"))
        debt_to_assets_raw = ev(indicator.get("tlia_ta"))

        ocf = ev(cash_flow.get("nocf"))
        capex_raw = ev(cash_flow.get("adtfxda"))  # 原始值通常为负
        capex = abs(capex_raw) if capex_raw is not None else None
        fcf = (ocf - capex) if (ocf is not None and capex is not None) else None

        report_period = self._parse_report_period(
            indicator.get("report_date") or income.get("report_date")
            or cash_flow.get("report_date") or balance.get("report_date")
        )

        return {
            "ticker": ticker,
            "report_period": report_period,
            "period": "ttm",
            "currency": "HKD",
            # Profitability (% → decimal)
            "return_on_equity": roe_raw / 100 if roe_raw is not None else None,
            "return_on_assets": roa_raw / 100 if roa_raw is not None else None,
            "gross_margin": gpm_raw / 100 if gpm_raw is not None else None,
            "operating_margin": opm_raw / 100 if opm_raw is not None else None,
            # Liquidity & Leverage
            "current_ratio": ev(indicator.get("cro")),
            "quick_ratio": ev(indicator.get("qro")),
            "debt_to_assets": debt_to_assets_raw / 100 if debt_to_assets_raw is not None else None,
            # Per share
            "earnings_per_share": ev(indicator.get("beps")),
            "book_value_per_share": ev(indicator.get("bps")),
            "operating_cash_flow_per_share": ev(indicator.get("nocfps")),
            # Income statement
            "revenue": ev(income.get("tto")) or ev(indicator.get("tto")),
            "net_income": ev(income.get("ploashh")) or ev(indicator.get("ploashh")),
            "operating_income": ev(income.get("plobtx")),
            "gross_profit": ev(income.get("gp")),
            "research_and_development": ev(income.get("rshdevexp")),
            # Cash flow
            "operating_cash_flow": ocf,
            "capital_expenditure": capex,
            "investing_cash_flow": ev(cash_flow.get("ninvcf")),
            "financing_cash_flow": ev(cash_flow.get("nfcgcf")),
            "free_cash_flow": fcf,
            # Balance sheet
            "total_assets": ev(balance.get("ta")),
            "total_liabilities": ev(balance.get("tlia")),
            "shareholders_equity": ev(balance.get("shhfd")),
            "cash_and_equivalents": ev(balance.get("cceq")),
            "current_assets": ev(balance.get("ca")),
            "current_liabilities": ev(balance.get("clia")),
        }

    def _build_cn_metrics(
        self, ticker: str, indicator: Dict, income: Dict,
        cash_flow: Dict, balance: Dict,
    ) -> Dict:
        """A股四张报表聚合。百分比字段除以100转为小数。"""
        ev = self._extract_value

        roe_raw = ev(indicator.get("avg_roe"))
        roa_raw = ev(indicator.get("net_interest_of_total_assets"))
        gpm_raw = ev(indicator.get("gross_selling_rate"))
        npm_raw = ev(indicator.get("net_selling_rate"))
        debt_to_assets_raw = ev(indicator.get("asset_liab_ratio"))
        rev_growth_raw = ev(indicator.get("operating_income_yoy"))
        earn_growth_raw = ev(indicator.get("net_profit_atsopc_yoy"))

        ocf = ev(cash_flow.get("ncf_from_oa"))
        # A股 cash_paid_for_assets 为正值（支出金额）
        capex = ev(cash_flow.get("cash_paid_for_assets"))
        fcf = (ocf - capex) if (ocf is not None and capex is not None) else None

        report_period = self._parse_report_period(
            indicator.get("report_date") or income.get("report_date")
        )

        return {
            "ticker": ticker,
            "report_period": report_period,
            "period": "ttm",
            "currency": "CNY",
            # Profitability (% → decimal)
            "return_on_equity": roe_raw / 100 if roe_raw is not None else None,
            "return_on_assets": roa_raw / 100 if roa_raw is not None else None,
            "gross_margin": gpm_raw / 100 if gpm_raw is not None else None,
            "net_margin": npm_raw / 100 if npm_raw is not None else None,
            # Liquidity & Leverage (% → decimal)
            "current_ratio": ev(indicator.get("current_ratio")),
            "quick_ratio": ev(indicator.get("quick_ratio")),
            "debt_to_assets": debt_to_assets_raw / 100 if debt_to_assets_raw is not None else None,
            # Growth (% → decimal)
            "revenue_growth": rev_growth_raw / 100 if rev_growth_raw is not None else None,
            "earnings_growth": earn_growth_raw / 100 if earn_growth_raw is not None else None,
            # Per share
            "earnings_per_share": ev(indicator.get("basic_eps")),
            "book_value_per_share": ev(indicator.get("np_per_share")),
            "operating_cash_flow_per_share": ev(indicator.get("operate_cash_flow_ps")),
            # Income statement
            "revenue": ev(income.get("total_revenue")) or ev(indicator.get("total_revenue")),
            "net_income": ev(income.get("net_profit")) or ev(indicator.get("net_profit_atsopc")),
            "operating_income": ev(income.get("operate_profit")),
            "gross_profit": ev(income.get("gross_profit")),
            "research_and_development": ev(income.get("research_and_development_costs")),
            # Cash flow
            "operating_cash_flow": ocf,
            "capital_expenditure": capex,
            "investing_cash_flow": ev(cash_flow.get("ncf_from_ia")),
            "financing_cash_flow": ev(cash_flow.get("ncf_from_fa")),
            "free_cash_flow": fcf,
            # Balance sheet
            "total_assets": ev(balance.get("total_assets")),
            "total_liabilities": ev(balance.get("total_liab")),
            "shareholders_equity": ev(balance.get("total_holders_equity")),
            "cash_and_equivalents": ev(balance.get("currency_funds")),
            "current_assets": ev(balance.get("total_current_assets")),
            "current_liabilities": ev(balance.get("total_current_liab")),
        }
```

- [ ] **Step 4: 运行骨架测试**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py::TestXueqiuSourceInit -v
```
期望: 所有 10 个测试 PASS

- [ ] **Step 5: Commit**

```bash
git add src/markets/sources/xueqiu_source.py tests/markets/sources/test_xueqiu_source.py
git commit -m "feat: add XueqiuSource skeleton with token init, symbol conversion, and both market implementations"
```

---

### Task 3: 测试港股财务指标聚合逻辑

**Files:**
- Test: `tests/markets/sources/test_xueqiu_source.py`

- [ ] **Step 1: 追加港股测试**

```python
# 追加到 tests/markets/sources/test_xueqiu_source.py

class TestXueqiuSourceHKFinancialMetrics:
    MOCK_INDICATOR = {
        "roe": [22.06, 1.23], "rota": [11.60, 1.25],
        "gpm": [38.44, 0.09], "opemg": [11.30, 1.20],
        "cro": [1.94, 0.07], "qro": [1.93, 0.07],
        "tlia_ta": [46.79, -0.03],
        "beps": [5.85, 1.62], "bps": [28.56, 0.17],
        "nocfps": [9.45, 0.46],
        "tto": [337591576000.0, 0.22],
        "ploashh": [35807179000.0, 1.58],
        "report_date": 1735574400000,
    }
    MOCK_INCOME = {
        "tto": [337591576000.0, 0.22],
        "gp": [129784594000.0, 0.34],
        "rshdevexp": [21053601000.0, -0.007],
        "ploashh": [35807179000.0, 1.58],
        "plobtx": [37985429000.0, 1.71],
        "report_date": 1735574400000,
    }
    MOCK_CASH_FLOW = {
        "nocf": [57146784000.0, 0.41],
        "ninvcf": [10205252000.0, 1.41],
        "nfcgcf": [-30414660000.0, -9.94],
        "adtfxda": [-10999490000.0, -0.60],
        "report_date": 1735574400000,
    }
    MOCK_BALANCE = {
        "ta": [324354917000.0, None],
        "tlia": [151750839000.0, None],
        "shhfd": [172662960000.0, None],
        "cceq": [90383717000.0, None],
        "ca": [209734861000.0, None],
        "clia": [107935640000.0, None],
        "report_date": 1735574400000,
    }

    def _make_source(self, mocker):
        source = XueqiuSource()
        source._token_initialized = True
        def mock_fetch(endpoint, symbol, market):
            mapping = {
                "indicator": [self.MOCK_INDICATOR],
                "income": [self.MOCK_INCOME],
                "cash_flow": [self.MOCK_CASH_FLOW],
                "balance": [self.MOCK_BALANCE],
            }
            return mapping.get(endpoint, [])
        mocker.patch.object(source, "_fetch_financial_data", side_effect=mock_fetch)
        return source

    def test_returns_dict_with_required_fields(self, mocker):
        result = self._make_source(mocker).get_financial_metrics("03690", "2025-01-01")
        assert result is not None
        assert result["ticker"] == "03690"
        assert result["currency"] == "HKD"
        assert result["period"] == "ttm"

    def test_roe_converted_to_decimal(self, mocker):
        result = self._make_source(mocker).get_financial_metrics("03690", "2025-01-01")
        assert result["return_on_equity"] == pytest.approx(0.2206, abs=0.001)

    def test_gross_margin_converted_to_decimal(self, mocker):
        result = self._make_source(mocker).get_financial_metrics("03690", "2025-01-01")
        assert result["gross_margin"] == pytest.approx(0.3844, abs=0.001)

    def test_operating_cash_flow_populated(self, mocker):
        result = self._make_source(mocker).get_financial_metrics("03690", "2025-01-01")
        assert result["operating_cash_flow"] == pytest.approx(57146784000.0)

    def test_capital_expenditure_is_positive(self, mocker):
        """资本支出存储为正数（原始值为负，取绝对值）"""
        result = self._make_source(mocker).get_financial_metrics("03690", "2025-01-01")
        assert result["capital_expenditure"] == pytest.approx(10999490000.0)

    def test_free_cash_flow_calculated(self, mocker):
        result = self._make_source(mocker).get_financial_metrics("03690", "2025-01-01")
        assert result["free_cash_flow"] == pytest.approx(57146784000.0 - 10999490000.0)

    def test_total_assets_from_balance_sheet(self, mocker):
        result = self._make_source(mocker).get_financial_metrics("03690", "2025-01-01")
        assert result["total_assets"] == pytest.approx(324354917000.0)

    def test_cash_and_equivalents_from_balance_sheet(self, mocker):
        result = self._make_source(mocker).get_financial_metrics("03690", "2025-01-01")
        assert result["cash_and_equivalents"] == pytest.approx(90383717000.0)

    def test_research_and_development_from_income(self, mocker):
        result = self._make_source(mocker).get_financial_metrics("03690", "2025-01-01")
        assert result["research_and_development"] == pytest.approx(21053601000.0)

    def test_partial_data_cash_flow_missing_returns_none_fields(self, mocker):
        """当现金流量表缺失时，相关字段应为 None，但整体不应返回 None"""
        source = XueqiuSource()
        source._token_initialized = True
        def mock_fetch(endpoint, symbol, market):
            if endpoint == "indicator":
                return [self.MOCK_INDICATOR]
            return []
        mocker.patch.object(source, "_fetch_financial_data", side_effect=mock_fetch)
        result = source.get_financial_metrics("03690", "2025-01-01")
        assert result is not None
        assert result["operating_cash_flow"] is None
        assert result["free_cash_flow"] is None

    def test_returns_none_when_all_fetches_fail(self, mocker):
        source = XueqiuSource()
        source._token_initialized = True
        mocker.patch.object(source, "_fetch_financial_data", return_value=[])
        assert source.get_financial_metrics("03690", "2025-01-01") is None
```

- [ ] **Step 2: 运行港股测试**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py::TestXueqiuSourceHKFinancialMetrics -v
```
期望: 所有 11 个测试 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/markets/sources/test_xueqiu_source.py
git commit -m "test: add HK financial metrics tests for XueqiuSource"
```

---

### Task 4: 测试A股财务指标聚合逻辑

**Files:**
- Test: `tests/markets/sources/test_xueqiu_source.py`

- [ ] **Step 1: 追加A股测试**

```python
# 追加到 tests/markets/sources/test_xueqiu_source.py

class TestXueqiuSourceCNFinancialMetrics:
    MOCK_INDICATOR = {
        "avg_roe": [36.02, 0.054],
        "net_interest_of_total_assets": [31.26, 0.063],
        "gross_selling_rate": [91.93, -0.0004],
        "net_selling_rate": [52.27, -0.004],
        "current_ratio": [4.45, -0.037],
        "quick_ratio": [3.47, -0.055],
        "asset_liab_ratio": [19.04, 0.059],
        "basic_eps": [68.64, 0.154],
        "np_per_share": [185.56, 0.081],
        "operate_cash_flow_ps": [73.61, 0.388],
        "total_revenue": [174144069958.25, 0.157],
        "net_profit_atsopc": [86228146421.62, 0.154],
        "operating_income_yoy": [15.71, -0.174],
        "net_profit_atsopc_yoy": [15.38, -0.197],
        "report_date": 1735574400000,
    }
    MOCK_INCOME = {
        "total_revenue": [174144069958.25, 0.157],
        "gross_profit": [159894069958.25, 0.161],
        "research_and_development_costs": [1000000000.0, 0.05],
        "net_profit": [86228146421.62, 0.154],
        "operate_profit": [108000000000.0, 0.15],
        "report_date": 1735574400000,
    }
    MOCK_CASH_FLOW = {
        "ncf_from_oa": [92463692168.43, 0.388],
        "ncf_from_ia": [-1785202630.71, 0.816],
        "ncf_from_fa": [-71067506484.81, -0.207],
        "cash_paid_for_assets": [4678712053.56, 0.786],
        "report_date": 1735574400000,
    }
    MOCK_BALANCE = {
        "total_assets": [298944579918.7, None],
        "total_liab": [56933264798.1, None],
        "total_holders_equity": [242011315120.6, None],
        "currency_funds": [59295822956.89, None],
        "total_current_assets": [251726674636.66, None],
        "total_current_liab": [56515990618.96, None],
        "report_date": 1735574400000,
    }

    def _make_source(self, mocker):
        source = XueqiuSource()
        source._token_initialized = True
        def mock_fetch(endpoint, symbol, market):
            mapping = {
                "indicator": [self.MOCK_INDICATOR],
                "income": [self.MOCK_INCOME],
                "cash_flow": [self.MOCK_CASH_FLOW],
                "balance": [self.MOCK_BALANCE],
            }
            return mapping.get(endpoint, [])
        mocker.patch.object(source, "_fetch_financial_data", side_effect=mock_fetch)
        return source

    def test_cn_returns_cny_currency(self, mocker):
        result = self._make_source(mocker).get_financial_metrics("SH600519", "2025-01-01")
        assert result is not None
        assert result["currency"] == "CNY"
        assert result["ticker"] == "SH600519"

    def test_cn_roe_converted_to_decimal(self, mocker):
        result = self._make_source(mocker).get_financial_metrics("SH600519", "2025-01-01")
        assert result["return_on_equity"] == pytest.approx(0.3602, abs=0.001)

    def test_cn_gross_margin_converted_to_decimal(self, mocker):
        result = self._make_source(mocker).get_financial_metrics("SH600519", "2025-01-01")
        assert result["gross_margin"] == pytest.approx(0.9193, abs=0.001)

    def test_cn_operating_cash_flow_populated(self, mocker):
        result = self._make_source(mocker).get_financial_metrics("SH600519", "2025-01-01")
        assert result["operating_cash_flow"] == pytest.approx(92463692168.43)

    def test_cn_free_cash_flow_calculated(self, mocker):
        result = self._make_source(mocker).get_financial_metrics("SH600519", "2025-01-01")
        assert result["free_cash_flow"] == pytest.approx(92463692168.43 - 4678712053.56)

    def test_cn_revenue_growth_converted_to_decimal(self, mocker):
        result = self._make_source(mocker).get_financial_metrics("SH600519", "2025-01-01")
        assert result["revenue_growth"] == pytest.approx(0.1571, abs=0.001)

    def test_cn_cash_and_equivalents_from_balance(self, mocker):
        result = self._make_source(mocker).get_financial_metrics("SH600519", "2025-01-01")
        assert result["cash_and_equivalents"] == pytest.approx(59295822956.89)

    def test_cn_pure_digit_ticker_routed_correctly(self, mocker):
        """纯6位数字 ticker 应被识别为 CN 市场"""
        source = XueqiuSource()
        source._token_initialized = True
        captured = {}
        def mock_fetch(endpoint, symbol, market):
            captured["market"] = market
            captured["symbol"] = symbol
            return []
        mocker.patch.object(source, "_fetch_financial_data", side_effect=mock_fetch)
        source.get_financial_metrics("600519", "2025-01-01")
        assert captured.get("market") == "CN"
        assert captured.get("symbol") == "SH600519"
```

- [ ] **Step 2: 运行A股测试**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py::TestXueqiuSourceCNFinancialMetrics -v
```
期望: 所有 8 个测试 PASS

- [ ] **Step 3: 运行全部 XueqiuSource 测试**

```bash
poetry run pytest tests/markets/sources/test_xueqiu_source.py -v
```
期望: 所有测试 PASS

- [ ] **Step 4: Commit**

```bash
git add tests/markets/sources/test_xueqiu_source.py
git commit -m "test: add CN financial metrics tests for XueqiuSource"
```

---

## Chunk 3: 集成到适配器

### Task 5: 集成到 HKStockAdapter

**Files:**
- Modify: `src/markets/hk_stock.py`
- Modify: `src/markets/sources/__init__.py`
- Test: `tests/markets/test_hk_stock_adapter.py`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/markets/test_hk_stock_adapter.py

class TestHKAdapterIncludesXueqiu:
    def test_xueqiu_source_in_data_sources(self):
        from src.markets.hk_stock import HKStockAdapter
        from src.markets.sources.xueqiu_source import XueqiuSource
        adapter = HKStockAdapter()
        assert any(isinstance(s, XueqiuSource) for s in adapter.data_sources)

    def test_xueqiu_before_akshare_in_priority(self):
        from src.markets.hk_stock import HKStockAdapter
        from src.markets.sources.xueqiu_source import XueqiuSource
        from src.markets.sources.akshare_source import AKShareSource
        adapter = HKStockAdapter()
        names = [type(s).__name__ for s in adapter.data_sources]
        assert names.index("XueqiuSource") < names.index("AKShareSource")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
poetry run pytest tests/markets/test_hk_stock_adapter.py::TestHKAdapterIncludesXueqiu -v 2>&1 | head -15
```

- [ ] **Step 3: 修改 HKStockAdapter**

在 `src/markets/hk_stock.py` 中添加 import 并调整 data_sources 列表：

```python
# 新增 import（加在现有 import 之后）
from src.markets.sources.xueqiu_source import XueqiuSource

# 修改 __init__ 中的 data_sources 列表
data_sources = [
    XueqiuSource(),       # Primary for financials: most complete statements
    SinaFinanceSource(),  # Primary for prices: free, stable, real-time
    AKShareSource(),      # Fallback
]
```

- [ ] **Step 4: 注册到 `__init__.py`**

查看 `src/markets/sources/__init__.py` 当前内容，添加：

```python
from src.markets.sources.xueqiu_source import XueqiuSource
```

并在 `__all__` 列表中加入 `"XueqiuSource"`。

- [ ] **Step 5: 运行 HK 适配器测试**

```bash
poetry run pytest tests/markets/test_hk_stock_adapter.py -v --tb=short
```
期望: 所有测试 PASS（包括已有测试）

- [ ] **Step 6: Commit**

```bash
git add src/markets/hk_stock.py src/markets/sources/__init__.py tests/markets/test_hk_stock_adapter.py
git commit -m "feat: add XueqiuSource to HKStockAdapter as primary financial data source"
```

---

### Task 6: 集成到 CNStockAdapter

**Files:**
- Modify: `src/markets/cn_stock.py`
- Test: `tests/markets/test_cn_stock_adapter.py`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/markets/test_cn_stock_adapter.py

class TestCNAdapterIncludesXueqiu:
    def test_xueqiu_source_in_data_sources(self):
        from src.markets.cn_stock import CNStockAdapter
        from src.markets.sources.xueqiu_source import XueqiuSource
        adapter = CNStockAdapter()
        assert any(isinstance(s, XueqiuSource) for s in adapter.data_sources)

    def test_xueqiu_after_eastmoney_in_priority(self):
        from src.markets.cn_stock import CNStockAdapter
        from src.markets.sources.xueqiu_source import XueqiuSource
        from src.markets.sources.eastmoney_curl_source import EastmoneyCurlSource
        adapter = CNStockAdapter()
        names = [type(s).__name__ for s in adapter.data_sources]
        assert names.index("XueqiuSource") > names.index("EastmoneyCurlSource")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
poetry run pytest tests/markets/test_cn_stock_adapter.py::TestCNAdapterIncludesXueqiu -v 2>&1 | head -15
```

- [ ] **Step 3: 修改 CNStockAdapter**

在 `src/markets/cn_stock.py` 中添加 import 并调整 data_sources 列表：

```python
# 新增 import
from src.markets.sources.xueqiu_source import XueqiuSource

# 修改 data_sources 列表
data_sources = [
    EastmoneyCurlSource(),  # Primary: Most comprehensive, bypasses anti-bot
    XueqiuSource(),         # Secondary: Complete financial statements
    TushareSource(),        # Fallback 1: Requires token
    AKShareSource(),        # Fallback 2: Free, good coverage
    SinaFinanceSource(),    # Fallback 3: Free, stable
]
```

- [ ] **Step 4: 运行 CN 适配器测试**

```bash
poetry run pytest tests/markets/test_cn_stock_adapter.py -v --tb=short
```
期望: 所有测试 PASS

- [ ] **Step 5: Commit**

```bash
git add src/markets/cn_stock.py tests/markets/test_cn_stock_adapter.py
git commit -m "feat: add XueqiuSource to CNStockAdapter as secondary financial data source"
```

---

## Chunk 4: 端到端验证

### Task 7: 端到端验证数据质量改善

**Files:**
- No code changes, validation only

- [ ] **Step 1: 运行完整测试套件**

```bash
poetry run pytest tests/ -q --tb=short 2>&1 | tail -20
```
期望: 无新增失败

- [ ] **Step 2: 验证港股关键字段（之前全部缺失）**

```bash
poetry run python -c "
from src.tools.api import get_financial_metrics

# 清除缓存以强制重新获取
from src.data.dual_cache import _get_dual_cache
# 直接测试
ticker = '3690.HK'
metrics = get_financial_metrics(ticker, '2025-01-01', period='ttm', limit=1)
if not metrics:
    print('❌ 无数据')
    exit(1)
m = metrics[0]
checks = [
    ('operating_cash_flow', m.operating_cash_flow),
    ('capital_expenditure', m.capital_expenditure),
    ('free_cash_flow', m.free_cash_flow),
    ('cash_and_equivalents', m.cash_and_equivalents),
    ('total_assets', m.total_assets),
    ('gross_margin', m.gross_margin),
    ('research_and_development', m.research_and_development),
    ('current_ratio', m.current_ratio),
    ('quick_ratio', m.quick_ratio),
    ('gross_profit', m.gross_profit),
]
print('=== 3690.HK 新增字段验证 ===')
passed = 0
for name, val in checks:
    status = '✅' if val is not None else '❌'
    if val is not None:
        passed += 1
    print(f'{status} {name}: {val}')
print(f'\n通过: {passed}/{len(checks)}')
" 2>&1 | grep -E "✅|❌|通过|===|无数据"
```
期望: 通过率 ≥ 8/10（部分字段可能因雪球API返回格式变化而缺失）

- [ ] **Step 3: 验证A股数据质量**

```bash
poetry run python -c "
from src.tools.api import get_financial_metrics

ticker = '600519.SH'
metrics = get_financial_metrics(ticker, '2025-01-01', period='ttm', limit=1)
if not metrics:
    print('❌ 无数据')
    exit(1)
m = metrics[0]
checks = [
    ('operating_cash_flow', m.operating_cash_flow),
    ('free_cash_flow', m.free_cash_flow),
    ('cash_and_equivalents', m.cash_and_equivalents),
    ('research_and_development', m.research_and_development),
    ('gross_margin', m.gross_margin),
    ('current_ratio', m.current_ratio),
]
print('=== 600519.SH 新增字段验证 ===')
for name, val in checks:
    print(f'{'✅' if val is not None else '❌'} {name}: {val}')
" 2>&1 | grep -E "✅|❌|==="
```

- [ ] **Step 4: 运行现有验证脚本确认不回归**

```bash
poetry run python verify_cn_stocks.py 2>&1 | grep -E "通过率|✅|❌"
```
期望: `通过率: 4/4 (100%)`

- [ ] **Step 5: 最终提交**

```bash
git add -A
git commit -m "feat: complete XueqiuSource integration - HK/CN financial data now includes cash flow and balance sheet details"
```

---

## 实现注意事项

### 雪球 API 特性
- **Token 获取**: 先 GET `TOKEN_INIT_URL`，响应会在 session cookie 中设置 `xq_a_token`
- **Token 失效**: 返回 `{"error_code": "400016"}` 时，将 `_token_initialized = False` 并重新调用 `_ensure_token()`
- **Rate Limit**: 未公开，建议请求间隔 ≥ 0.5s；实测并发无问题

### 字段百分比规范
所有百分比字段（ROE、毛利率等）存入 `FinancialMetrics` 时**必须为小数**（0.3602 = 36.02%），与现有 AKShare/EastMoney 实现保持一致。

### 数据合并策略
`DataValidator.validate_financial_metrics` 对多源相同字段取加权平均。XueqiuSource 提供的字段（如 `operating_cash_flow`）在其他源缺失时直接采用，在多源都有时参与加权，这是期望行为。

### 港股资产负债表字段缩写
雪球港股 `balance.json` 返回缩写字段（`ta`, `tlia`, `cceq` 等），A股返回完整英文字段（`total_assets` 等）。两套映射已分别在 `_build_hk_metrics` 和 `_build_cn_metrics` 中实现。
