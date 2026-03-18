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
    TOKEN_INIT_URL = "https://xueqiu.com/service/v5/stock/screener/quote/list" "?page=1&size=1&order=desc&orderby=percent&market=CN&type=sh_sz"

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
            if r.status_code == 200 and "xq_a_token" in self.session.cookies:
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

        if market == "HK":
            metrics = self._build_hk_metrics(ticker, indicator, income, cash_flow, balance)
        else:
            metrics = self._build_cn_metrics(ticker, indicator, income, cash_flow, balance)

        non_null = sum(1 for v in metrics.values() if v is not None and v != "")
        self.logger.info(f"[Xueqiu] ✓ Got {market} financial metrics for {symbol}: " f"{non_null}/{len(metrics)} fields populated")
        return metrics

    def _build_hk_metrics(
        self,
        ticker: str,
        indicator: Dict,
        income: Dict,
        cash_flow: Dict,
        balance: Dict,
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

        report_period = self._parse_report_period(indicator.get("report_date") or income.get("report_date") or cash_flow.get("report_date") or balance.get("report_date"))

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
        self,
        ticker: str,
        indicator: Dict,
        income: Dict,
        cash_flow: Dict,
        balance: Dict,
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
