"""雪球(Xueqiu)数据源，支持港股和A股完整财务报表数据。"""
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
    TOKEN_INIT_URL = "https://xueqiu.com/service/v5/stock/screener/quote/list" "?page=1&size=1&order=desc&order_by=percent&market=CN&type=sh_sz"

    def __init__(self):
        super().__init__("Xueqiu")
        self._session: Optional[requests.Session] = None
        self._token_initialized = False

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(
                {
                    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " "AppleWebKit/537.36 (KHTML, like Gecko) " "Chrome/120.0.0.0 Safari/537.36"),
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Referer": "https://xueqiu.com/",
                }
            )
        return self._session

    def _ensure_token(self) -> bool:
        """确保 xq_a_token cookie 已生成。首次调用时触发初始化。"""
        if self._token_initialized:
            return True
        try:
            r = self.session.get(self.TOKEN_INIT_URL, timeout=10)
            # Xueqiu sets cookies even with 400 status, so check cookies first
            if "xq_a_token" in self.session.cookies:
                self._token_initialized = True
                self.logger.debug("[Xueqiu] Token initialized successfully")
                return True
            self.logger.warning(f"[Xueqiu] Token init failed: status={r.status_code}, " f"has_token={'xq_a_token' in self.session.cookies}")
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
        # Note: market_cap is only available for the most recent period.
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

    def _fetch_quote_valuation(self, symbol: str) -> Dict:
        """
        从雪球行情接口获取实时估值数据。
        财务报表接口不提供估值比率，需单独请求。

        返回字段：
          pe_ttm      - 滚动市盈率（过去12个月净利润）
          pe_lyr      - 静态市盈率（最近完整财年净利润）
          pe_forecast - 动态市盈率（分析师预测）
          pb          - 市净率
          ps_ttm      - 市销率TTM（雪球通常为None）
        """
        url = "https://stock.xueqiu.com/v5/stock/quote.json"
        params = {"symbol": symbol, "extend": "detail"}
        try:
            r = self.session.get(url, params=params, timeout=10)
            if r.status_code != 200:
                self.logger.warning(f"[Xueqiu] quote for {symbol} returned {r.status_code}")
                return {}
            data = r.json()
            quote = data.get("data", {}).get("quote", {})
            return {
                "pe_ttm": self._safe_float(quote.get("pe_ttm")),
                "pe_lyr": self._safe_float(quote.get("pe_lyr")),
                "pe_forecast": self._safe_float(quote.get("pe_forecast")),
                "pb": self._safe_float(quote.get("pb")),
                "ps_ttm": self._safe_float(quote.get("ps_ttm")),
            }
        except Exception as e:
            self.logger.warning(f"[Xueqiu] Error fetching quote for {symbol}: {e}")
            return {}

    def _fetch_financial_data(self, endpoint: str, symbol: str, market: str) -> List[Dict]:
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
                self.logger.warning(f"[Xueqiu] {endpoint} for {symbol} returned {r.status_code}")
                return []
            data = r.json()
            return data.get("data", {}).get("list", []) or []
        except Exception as e:
            self.logger.error(f"[Xueqiu] Error fetching {endpoint} for {symbol}: {e}")
            return []

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

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Dict]:
        """雪球不提供历史价格数据，返回空列表。"""
        return []

    def get_company_news(
        self,
        ticker: str,
        end_date: str,
        start_date: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """雪球不提供新闻数据，返回空列表。"""
        return []

    def _detect_market_and_symbol(self, ticker: str) -> tuple:
        """根据 ticker 格式判断市场并返回标准化 symbol。"""
        if (len(ticker) == 6 and ticker.isdigit()) or ticker.startswith(("SH", "SZ")):
            market = "CN"
            symbol = ticker if ticker.startswith(("SH", "SZ")) else self._to_xueqiu_symbol(ticker, "CN")
        else:
            market = "HK"
            symbol = ticker.zfill(5)
        return market, symbol

    def get_financial_metrics(self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10) -> Optional[Dict]:
        """获取港股或A股财务指标，聚合四张报表数据。失败返回 None。"""
        if not self._ensure_token():
            self.logger.warning("[Xueqiu] Cannot get token, skipping")
            return None

        market, symbol = self._detect_market_and_symbol(ticker)

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

        # Fetch real-time valuation ratios (pe_ttm, pe_lyr, pe_forecast, pb) from quote API
        # 财务报表接口不含估值比率，需单独请求行情接口获取
        quote_valuation = self._fetch_quote_valuation(symbol)

        if market == "HK":
            metrics = self._build_hk_metrics(ticker, indicator, income, cash_flow, balance, quote_valuation)
        else:
            metrics = self._build_cn_metrics(ticker, indicator, income, cash_flow, balance, quote_valuation)

        non_null = sum(1 for v in metrics.values() if v is not None and v != "")
        self.logger.info(f"[Xueqiu] ✓ Got {market} financial metrics for {symbol}: " f"{non_null}/{len(metrics)} fields populated")
        return metrics

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

    def _build_hk_metrics(
        self,
        ticker: str,
        indicator: Dict,
        income: Dict,
        cash_flow: Dict,
        balance: Dict,
        quote_valuation: Optional[Dict] = None,
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

        # Calculate net_margin from income statement (雪球indicator无直接净利润率字段)
        net_income_val = ev(income.get("ploashh")) or ev(indicator.get("ploashh"))
        revenue_val = ev(income.get("tto")) or ev(indicator.get("tto"))
        net_margin_calc = (net_income_val / revenue_val) if (net_income_val is not None and revenue_val and revenue_val != 0) else None

        report_period = self._parse_report_period(indicator.get("report_date") or income.get("report_date") or cash_flow.get("report_date") or balance.get("report_date"))

        qv = quote_valuation or {}
        result = {
            "ticker": ticker,
            "report_period": report_period,
            "period": "ttm",
            "currency": "HKD",
            # Valuation ratios (from real-time quote API)
            "price_to_earnings_ratio": qv.get("pe_ttm"),       # 滚动市盈率（TTM）
            "price_to_earnings_ratio_lyr": qv.get("pe_lyr"),   # 静态市盈率（最近完整财年）
            "price_to_earnings_ratio_forward": qv.get("pe_forecast"),  # 动态市盈率（分析师预测）
            "price_to_book_ratio": qv.get("pb"),
            "price_to_sales_ratio": qv.get("ps_ttm"),
            # Profitability (% → decimal)
            "return_on_equity": roe_raw / 100 if roe_raw is not None else None,
            "return_on_assets": roa_raw / 100 if roa_raw is not None else None,
            "gross_margin": gpm_raw / 100 if gpm_raw is not None else None,
            "operating_margin": opm_raw / 100 if opm_raw is not None else None,
            "net_margin": net_margin_calc,
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
        self._compute_derived_metrics(result)
        return result

    def _build_cn_metrics(
        self,
        ticker: str,
        indicator: Dict,
        income: Dict,
        cash_flow: Dict,
        balance: Dict,
        quote_valuation: Optional[Dict] = None,
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

        report_period = self._parse_report_period(indicator.get("report_date") or income.get("report_date"))

        qv = quote_valuation or {}
        result = {
            "ticker": ticker,
            "report_period": report_period,
            "period": "ttm",
            "currency": "CNY",
            # Valuation ratios (from real-time quote API)
            "price_to_earnings_ratio": qv.get("pe_ttm"),       # 滚动市盈率（TTM）
            "price_to_earnings_ratio_lyr": qv.get("pe_lyr"),   # 静态市盈率（最近完整财年）
            "price_to_earnings_ratio_forward": qv.get("pe_forecast"),  # 动态市盈率（分析师预测）
            "price_to_book_ratio": qv.get("pb"),
            "price_to_sales_ratio": qv.get("ps_ttm"),
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
        self._compute_derived_metrics(result)
        return result
