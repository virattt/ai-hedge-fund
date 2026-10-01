"""YFinanceClient contract tests — stubbed yfinance, no network.

Pins the same guarantees as the FD contract tests, translated to Yahoo:

1. Fail-loud: infrastructure failures raise YFClientError; only "no data
   exists" (no bars in range, an ETF without statements) returns empty.
2. Point-in-time: a metrics row is served only once its filing_date (the
   earnings announcement that published it) is on or before end_date.
"""

import pandas as pd
import pytest
from yfinance.exceptions import YFPricesMissingError

from hedge_fund.data import YFClientError, YFinanceClient
from hedge_fund.data import yfinance_client as yfc

Q_ENDS = ["2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"]


def _frame(rows: dict[str, list], cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame(rows, index=pd.to_datetime(cols)).T


class FakeTicker:
    def __init__(self, *, q_ends=Q_ENDS, quote_type="EQUITY", history=None, announcements=None):
        n = len(q_ends)
        self.quarterly_income_stmt = _frame({
            "Total Revenue": [100.0] * n, "Gross Profit": [40.0] * n,
            "Operating Income": [30.0] * n, "Net Income": [20.0] * n,
            "Diluted EPS": [2.0] * n,
        }, q_ends) if n else pd.DataFrame()
        self.quarterly_balance_sheet = _frame({
            "Stockholders Equity": [400.0] * n, "Total Debt": [200.0] * n,
            "Total Assets": [1000.0] * n, "Current Assets": [300.0] * n,
            "Current Liabilities": [150.0] * n, "Ordinary Shares Number": [10.0] * n,
        }, q_ends) if n else pd.DataFrame()
        self.quarterly_cashflow = _frame({"Free Cash Flow": [15.0] * n}, q_ends) if n else pd.DataFrame()
        self.income_stmt = self.balance_sheet = self.cashflow = pd.DataFrame()
        self.info = {"quoteType": quote_type, "longName": "Test Co", "sector": "Tech"}
        self._history = history
        self._announcements = announcements if announcements is not None else [
            ("2026-07-30 16:00", 1.9, 2.0), ("2026-04-30 16:00", 2.1, 2.0),
            ("2026-01-29 16:00", 2.0, 2.0), ("2025-10-30 16:00", 1.8, 2.0),
        ]

    def history(self, **kwargs):
        if isinstance(self._history, Exception):
            raise self._history
        if self._history is not None:
            return self._history
        idx = pd.date_range("2025-06-01", "2026-09-30", freq="B", tz="America/New_York")
        closes = [float(i) for i in range(1, len(idx) + 1)]
        return pd.DataFrame({"Open": closes, "High": closes, "Low": closes,
                             "Close": closes, "Volume": [1000] * len(idx)}, index=idx)

    def get_earnings_dates(self, limit=12):
        idx = pd.DatetimeIndex([pd.Timestamp(t, tz="America/New_York") for t, _, _ in self._announcements])
        return pd.DataFrame({
            "EPS Estimate": [e for _, e, _ in self._announcements],
            "Reported EPS": [r for _, _, r in self._announcements],
        }, index=idx)


@pytest.fixture
def stub(monkeypatch):
    def install(ticker: FakeTicker) -> YFinanceClient:
        monkeypatch.setattr(yfc.yf, "Ticker", lambda symbol: ticker)
        return YFinanceClient()
    return install


# ---------------------------------------------------------------------------
# Fail-loud contract
# ---------------------------------------------------------------------------

def test_no_bars_in_range_is_empty_not_error(stub):
    client = stub(FakeTicker(history=YFPricesMissingError("TEST", "")))
    assert client.get_prices("TEST", "2026-09-26", "2026-09-27") == []


def test_price_infrastructure_failure_raises(stub):
    client = stub(FakeTicker(history=ConnectionError("network down")))
    with pytest.raises(YFClientError):
        client.get_prices("TEST", "2026-01-01", "2026-02-01")


def test_equity_without_statements_raises(stub):
    client = stub(FakeTicker(q_ends=[]))
    with pytest.raises(YFClientError):
        client.get_financial_metrics("TEST", "2026-10-01")


def test_etf_without_statements_is_empty(stub):
    client = stub(FakeTicker(q_ends=[], quote_type="ETF"))
    assert client.get_financial_metrics("SPY", "2026-10-01") == []


def test_unsupported_feeds_raise_instead_of_returning_empty(stub):
    client = stub(FakeTicker())
    with pytest.raises(NotImplementedError):
        client.get_news("TEST", "2026-10-01")
    with pytest.raises(NotImplementedError):
        client.get_insider_trades("TEST", "2026-10-01")


# ---------------------------------------------------------------------------
# Metrics construction + point-in-time
# ---------------------------------------------------------------------------

def test_ttm_rows_sum_four_quarters_and_file_on_announcement(stub):
    client = stub(FakeTicker())
    rows = client.get_financial_metrics("TEST", "2026-10-01", limit=20)

    # 5 consecutive quarters -> TTM rows at the two newest quarter ends.
    assert [r.report_period for r in rows] == ["2026-06-30", "2026-03-31"]
    latest = rows[0]
    assert latest.filing_date == "2026-07-30"     # first announcement after period end
    assert latest.earnings_per_share == pytest.approx(8.0)
    assert latest.net_margin == pytest.approx(0.2)
    assert latest.return_on_equity == pytest.approx(80 / 400)
    assert latest.debt_to_equity == pytest.approx(0.5)
    assert latest.book_value_per_share == pytest.approx(40.0)
    assert latest.free_cash_flow_per_share == pytest.approx(6.0)
    # Same quarter a year earlier exists (2025-06-30): single-quarter YoY.
    assert latest.revenue_growth == pytest.approx(0.0)


def test_rows_are_hidden_until_filed(stub):
    client = stub(FakeTicker())
    assert [r.report_period for r in client.get_financial_metrics("TEST", "2026-07-29")] == ["2026-03-31"]
    assert client.get_financial_metrics("TEST", "2026-04-29") == []


def test_market_cap_uses_close_on_filing_date(stub):
    ticker = FakeTicker()
    client = stub(ticker)
    bars = ticker.history()
    expected_close = bars.loc[bars.index.strftime("%Y-%m-%d") <= "2026-07-30", "Close"].iloc[-1]
    latest = client.get_financial_metrics("TEST", "2026-10-01")[0]
    assert latest.market_cap == pytest.approx(10.0 * expected_close)
    assert latest.price_to_earnings_ratio == pytest.approx(round(expected_close / 8.0, 4))


def test_gap_in_quarters_yields_no_ttm_row(stub):
    # 2025-12-31 missing: no window of four consecutive quarters remains.
    client = stub(FakeTicker(q_ends=["2025-06-30", "2025-09-30", "2026-03-31", "2026-06-30"]))
    assert client.get_financial_metrics("TEST", "2026-10-01") == []


def test_filing_date_falls_back_to_statutory_lag(stub):
    client = stub(FakeTicker(announcements=[]))
    rows = client.get_financial_metrics("TEST", "2026-10-01")
    assert rows[0].filing_date == "2026-08-14"    # 2026-06-30 + 45 days


# ---------------------------------------------------------------------------
# Earnings history
# ---------------------------------------------------------------------------

def test_earnings_history_maps_surprise_and_fiscal_quarter(stub):
    # Fiscal quarters ending Jan/Apr/Jul/Oct (a Walmart-style calendar).
    client = stub(FakeTicker(
        q_ends=["2025-07-31", "2025-10-31", "2026-01-31", "2026-04-30", "2026-07-31"],
        announcements=[("2026-08-20 06:00", 0.74, 0.81), ("2026-05-21 06:00", 0.66, 0.66),
                       ("2026-11-19 06:00", 0.64, float("nan"))],   # upcoming: dropped
    ))
    records = client.get_earnings_history("TEST", limit=8)
    assert [(r.report_period, r.filing_date, r.source_type, r.quarterly.eps_surprise)
            for r in records] == [
        ("2026-07-31", "2026-08-20", "8-K", "BEAT"),
        ("2026-04-30", "2026-05-21", "8-K", "MEET"),
    ]


def test_quarter_end_before():
    from datetime import date
    assert yfc._quarter_end_before(date(2026, 7, 30), 0) == date(2026, 6, 30)
    assert yfc._quarter_end_before(date(2026, 2, 19), 1) == date(2026, 1, 31)
    assert yfc._quarter_end_before(date(2026, 1, 2), 0) == date(2025, 12, 31)
