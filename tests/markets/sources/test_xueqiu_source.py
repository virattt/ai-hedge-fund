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
        assert source._to_xueqiu_symbol("600519", "CN") == "SH600519"
        assert source._to_xueqiu_symbol("600000", "CN") == "SH600000"

    def test_to_xueqiu_symbol_cn_sz(self):
        source = XueqiuSource()
        assert source._to_xueqiu_symbol("000001", "CN") == "SZ000001"
        assert source._to_xueqiu_symbol("000002", "CN") == "SZ000002"

    def test_to_xueqiu_symbol_cn_gem(self):
        source = XueqiuSource()
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


class TestXueqiuSourceHKFinancialMetrics:
    MOCK_INDICATOR = {
        "roe": [22.06, 1.23],
        "rota": [11.60, 1.25],
        "gpm": [38.44, 0.09],
        "opemg": [11.30, 1.20],
        "cro": [1.94, 0.07],
        "qro": [1.93, 0.07],
        "tlia_ta": [46.79, -0.03],
        "beps": [5.85, 1.62],
        "bps": [28.56, 0.17],
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
