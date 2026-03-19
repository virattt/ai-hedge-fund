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

        def mock_fetch_multi(endpoint, symbol, market, count="10"):
            mapping = {
                "indicator": [self.MOCK_INDICATOR],
                "income": [self.MOCK_INCOME],
                "cash_flow": [self.MOCK_CASH_FLOW],
                "balance": [self.MOCK_BALANCE],
            }
            return mapping.get(endpoint, [])

        mocker.patch.object(source, "_fetch_financial_data", side_effect=mock_fetch)
        mocker.patch.object(source, "_fetch_financial_data_multi", side_effect=mock_fetch_multi)
        return source

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

        def mock_fetch_multi(endpoint, symbol, market, count="10"):
            mapping = {
                "indicator": [self.MOCK_INDICATOR],
                "income": [self.MOCK_INCOME],
                "cash_flow": [self.MOCK_CASH_FLOW],
                "balance": [self.MOCK_BALANCE],
            }
            return mapping.get(endpoint, [])

        mocker.patch.object(source, "_fetch_financial_data", side_effect=mock_fetch)
        mocker.patch.object(source, "_fetch_financial_data_multi", side_effect=mock_fetch_multi)
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

    def test_cn_revenue_growth_none_without_prior_period(self, mocker):
        """revenue_growth is None when only one income period is available (no YoY comparison)."""
        result = self._make_source(mocker).get_financial_metrics("SH600519", "2025-01-01")
        assert result["revenue_growth"] is None

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

    @patch('src.markets.sources.xueqiu_source.XueqiuSource._fetch_financial_data_multi')
    @patch('src.markets.sources.xueqiu_source.XueqiuSource._fetch_quote_valuation')
    @patch('src.markets.sources.xueqiu_source.XueqiuSource._ensure_token')
    def test_get_historical_hk_returns_multiple_years(
        self, mock_token, mock_quote, mock_fetch_multi
    ):
        """get_historical_financial_data returns one dict per year, most recent first."""
        mock_token.return_value = True
        mock_quote.return_value = {"pe_ttm": 15.0, "pe_lyr": 13.0, "pe_forecast": 14.0, "pb": 2.6, "ps_ttm": None}

        # Two years: 2024 and 2023
        ts_2024 = 1735603200000  # 2024-12-31
        ts_2023 = 1703980800000  # 2023-12-31

        def fake_fetch_multi(endpoint, symbol, market, count="10"):
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

        mock_fetch_multi.side_effect = fake_fetch_multi

        from src.markets.sources.xueqiu_source import XueqiuSource
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

    @patch('src.markets.sources.xueqiu_source.XueqiuSource._fetch_financial_data_multi')
    @patch('src.markets.sources.xueqiu_source.XueqiuSource._fetch_quote_valuation')
    @patch('src.markets.sources.xueqiu_source.XueqiuSource._ensure_token')
    def test_get_historical_respects_limit(
        self, mock_token, mock_quote, mock_fetch_multi
    ):
        """limit parameter caps the number of returned periods."""
        mock_token.return_value = True
        mock_quote.return_value = {}

        ts_list = [1735603200000 - i * 31536000000 for i in range(5)]

        def fake_fetch_multi(endpoint, symbol, market, count="10"):
            if endpoint == "income":
                return [self._make_income_row(ts, 100e9 - i * 10e9, 10e9) for i, ts in enumerate(ts_list)]
            return []

        mock_fetch_multi.side_effect = fake_fetch_multi

        from src.markets.sources.xueqiu_source import XueqiuSource
        source = XueqiuSource()
        results = source.get_historical_financial_data("03690", limit=3)

        assert len(results) == 3

    @patch('src.markets.sources.xueqiu_source.XueqiuSource._fetch_financial_data_multi')
    @patch('src.markets.sources.xueqiu_source.XueqiuSource._ensure_token')
    def test_get_historical_returns_none_on_no_data(self, mock_token, mock_fetch_multi):
        """Returns None when all fetches fail."""
        mock_token.return_value = True
        mock_fetch_multi.return_value = []

        from src.markets.sources.xueqiu_source import XueqiuSource
        source = XueqiuSource()
        result = source.get_historical_financial_data("03690", limit=5)
        assert result is None


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
            "earnings_growth": -0.10,
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
            "debt_to_equity": None,
        }
        source._compute_derived_metrics(metrics)
        assert metrics["debt_to_equity"] == pytest.approx(303e9 / 172e9, rel=1e-4)

    def test_skips_when_missing_inputs(self):
        from src.markets.sources.xueqiu_source import XueqiuSource
        source = XueqiuSource()
        metrics = {}
        source._compute_derived_metrics(metrics)
        assert metrics.get("free_cash_flow_yield") is None
        assert metrics.get("enterprise_value") is None


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
