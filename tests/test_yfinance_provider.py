import pandas as pd
import pytest

from src.data.providers.yfinance import YFinanceProvider


class FakeTicker:
    def __init__(self):
        self.history_calls = []
        self.info = {
            "currency": "USD",
            "marketCap": 10_000.0,
            "enterpriseValue": 12_000.0,
            "trailingPE": 20.0,
            "priceToBook": 2.0,
            "priceToSalesTrailing12Months": 10.0,
            "enterpriseToRevenue": 12.0,
            "enterpriseToEbitda": 15.0,
            "grossMargins": 0.4,
            "operatingMargins": 0.3,
            "profitMargins": 0.1,
            "returnOnEquity": 0.2,
            "returnOnAssets": 0.1,
            "revenueGrowth": 0.25,
            "earningsGrowth": 0.2,
            "debtToEquity": 20.0,
            "currentRatio": 2.0,
            "quickRatio": 1.5,
            "trailingEps": 5.0,
            "bookValue": 50.0,
            "payoutRatio": 0.1,
        }
        self.fast_info = {"market_cap": 10_000.0}
        self.financials = pd.DataFrame(
            {
                pd.Timestamp("2024-12-31"): {
                    "Total Revenue": 1000.0,
                    "Gross Profit": 400.0,
                    "Operating Income": 300.0,
                    "Net Income": 100.0,
                    "Diluted EPS": 5.0,
                    "EBITDA": 800.0,
                    "EBIT": 300.0,
                    "Research And Development": 120.0,
                    "Operating Expense": 100.0,
                },
                pd.Timestamp("2023-12-31"): {
                    "Total Revenue": 800.0,
                    "Gross Profit": 280.0,
                    "Operating Income": 160.0,
                    "Net Income": 80.0,
                    "Diluted EPS": 4.0,
                    "EBITDA": 600.0,
                    "EBIT": 160.0,
                    "Research And Development": 90.0,
                    "Operating Expense": 120.0,
                },
            }
        )
        self.balance_sheet = pd.DataFrame(
            {
                pd.Timestamp("2024-12-31"): {
                    "Total Assets": 2000.0,
                    "Total Liabilities Net Minority Interest": 1500.0,
                    "Current Assets": 600.0,
                    "Current Liabilities": 300.0,
                    "Cash And Cash Equivalents": 200.0,
                    "Total Debt": 100.0,
                    "Stockholders Equity": 500.0,
                    "Ordinary Shares Number": 20.0,
                },
                pd.Timestamp("2023-12-31"): {
                    "Total Assets": 1500.0,
                    "Total Liabilities Net Minority Interest": 1100.0,
                    "Current Assets": 500.0,
                    "Current Liabilities": 250.0,
                    "Cash And Cash Equivalents": 150.0,
                    "Total Debt": 120.0,
                    "Stockholders Equity": 400.0,
                    "Ordinary Shares Number": 20.0,
                },
            }
        )
        self.cashflow = pd.DataFrame(
            {
                pd.Timestamp("2024-12-31"): {
                    "Free Cash Flow": 150.0,
                    "Operating Cash Flow": 250.0,
                    "Capital Expenditure": -100.0,
                    "Depreciation And Amortization": 50.0,
                    "Cash Dividends Paid": -10.0,
                },
                pd.Timestamp("2023-12-31"): {
                    "Free Cash Flow": 100.0,
                    "Operating Cash Flow": 180.0,
                    "Capital Expenditure": -80.0,
                    "Depreciation And Amortization": 45.0,
                    "Cash Dividends Paid": -8.0,
                },
            }
        )
        self.quarterly_financials = self.financials
        self.quarterly_balance_sheet = self.balance_sheet
        self.quarterly_cashflow = self.cashflow
        self.news = [
            {
                "content": {
                    "title": "Fake beats expectations",
                    "provider": {"displayName": "Market News"},
                    "canonicalUrl": {"url": "https://example.test/news"},
                    "pubDate": "2024-12-30T12:00:00Z",
                }
            }
        ]
        self.insider_transactions = pd.DataFrame(
            [
                {
                    "Start Date": "2024-12-15",
                    "Insider": "Jane Doe",
                    "Position": "CEO",
                    "Shares": 10.0,
                    "Value": 1000.0,
                    "Transaction": "Sale",
                }
            ]
        )

    def history(self, **kwargs):
        self.history_calls.append(kwargs)
        return pd.DataFrame(
            {
                "Open": [100.0, 102.0],
                "High": [103.0, 104.0],
                "Low": [99.0, 101.0],
                "Close": [102.0, 103.0],
                "Volume": [1000, 1100],
            },
            index=[pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")],
        )


@pytest.fixture()
def fake_provider(monkeypatch):
    provider = YFinanceProvider()
    fake = FakeTicker()
    monkeypatch.setattr(provider, "_ticker", lambda ticker: fake)
    return provider, fake


def test_yfinance_prices_map_history_to_price_models(fake_provider):
    provider, fake = fake_provider

    prices = provider.get_prices("FAKE_PRICE", "2024-01-02", "2024-01-03")

    assert [p.close for p in prices] == [102.0, 103.0]
    assert prices[0].volume == 1000
    assert fake.history_calls[0]["start"] == "2024-01-02"
    assert fake.history_calls[0]["end"] == "2024-01-04"


def test_yfinance_line_items_map_statement_aliases(fake_provider):
    provider, _ = fake_provider

    line_items = provider.search_line_items(
        "FAKE_LINE_ITEMS",
        ["revenue", "gross_margin", "free_cash_flow", "book_value_per_share"],
        "2024-12-31",
        period="annual",
        limit=2,
    )

    assert len(line_items) == 2
    assert line_items[0].ticker == "FAKE_LINE_ITEMS"
    assert line_items[0].revenue == 1000.0
    assert line_items[0].gross_margin == 0.4
    assert line_items[0].free_cash_flow == 150.0
    assert line_items[0].book_value_per_share == 25.0


def test_yfinance_financial_metrics_compute_ratios_and_growth(fake_provider, monkeypatch):
    provider, _ = fake_provider
    monkeypatch.setattr(provider, "_historical_close", lambda ticker_obj, end_date: 50.0)

    metrics = provider.get_financial_metrics("FAKE_METRICS", "2024-12-31", period="annual", limit=2)

    assert len(metrics) == 2
    latest = metrics[0]
    assert latest.ticker == "FAKE_METRICS"
    assert latest.market_cap == 1000.0
    assert latest.enterprise_value == 900.0
    assert latest.price_to_earnings_ratio == 10.0
    assert latest.price_to_book_ratio == 2.0
    assert latest.price_to_sales_ratio == 1.0
    assert latest.enterprise_value_to_revenue_ratio == 0.9
    assert latest.enterprise_value_to_ebitda_ratio == 1.125
    assert latest.gross_margin == 0.4
    assert latest.operating_margin == 0.3
    assert latest.net_margin == 0.1
    assert latest.return_on_equity == 0.2
    assert latest.debt_to_equity == 0.2
    assert latest.current_ratio == 2.0
    assert latest.revenue_growth == 0.25
    assert latest.free_cash_flow_yield == 0.15
    assert latest.payout_ratio == 0.1


def test_yfinance_ttm_uses_trailing_quarters(fake_provider):
    provider, fake = fake_provider
    quarters = [
        pd.Timestamp("2024-12-31"),
        pd.Timestamp("2024-09-30"),
        pd.Timestamp("2024-06-30"),
        pd.Timestamp("2024-03-31"),
        pd.Timestamp("2023-12-31"),
    ]
    fake.quarterly_financials = pd.DataFrame(
        {
            quarters[0]: {"Total Revenue": 400.0, "Gross Profit": 200.0, "Operating Income": 120.0, "Net Income": 80.0},
            quarters[1]: {"Total Revenue": 300.0, "Gross Profit": 120.0, "Operating Income": 90.0, "Net Income": 60.0},
            quarters[2]: {"Total Revenue": 200.0, "Gross Profit": 80.0, "Operating Income": 60.0, "Net Income": 40.0},
            quarters[3]: {"Total Revenue": 100.0, "Gross Profit": 40.0, "Operating Income": 30.0, "Net Income": 20.0},
            quarters[4]: {"Total Revenue": 50.0, "Gross Profit": 20.0, "Operating Income": 15.0, "Net Income": 10.0},
        }
    )
    fake.quarterly_balance_sheet = pd.DataFrame(
        {
            quarters[0]: {"Stockholders Equity": 1000.0, "Ordinary Shares Number": 50.0, "Current Assets": 500.0, "Current Liabilities": 250.0},
            quarters[1]: {"Stockholders Equity": 900.0, "Ordinary Shares Number": 50.0, "Current Assets": 450.0, "Current Liabilities": 225.0},
            quarters[2]: {"Stockholders Equity": 800.0, "Ordinary Shares Number": 50.0, "Current Assets": 400.0, "Current Liabilities": 200.0},
            quarters[3]: {"Stockholders Equity": 700.0, "Ordinary Shares Number": 50.0, "Current Assets": 350.0, "Current Liabilities": 175.0},
            quarters[4]: {"Stockholders Equity": 650.0, "Ordinary Shares Number": 50.0, "Current Assets": 325.0, "Current Liabilities": 160.0},
        }
    )
    fake.quarterly_cashflow = pd.DataFrame(
        {
            quarters[0]: {"Free Cash Flow": 40.0},
            quarters[1]: {"Free Cash Flow": 30.0},
            quarters[2]: {"Free Cash Flow": 20.0},
            quarters[3]: {"Free Cash Flow": 10.0},
            quarters[4]: {"Free Cash Flow": 5.0},
        }
    )

    line_items = provider.search_line_items(
        "FAKE_TTM",
        ["revenue", "gross_margin", "free_cash_flow", "book_value_per_share"],
        "2024-12-31",
        limit=1,
    )
    metrics = provider.get_financial_metrics("FAKE_TTM", "2024-12-31", limit=2)

    assert line_items[0].period == "ttm"
    assert line_items[0].revenue == 1000.0
    assert line_items[0].gross_margin == 0.44
    assert line_items[0].free_cash_flow == 100.0
    assert line_items[0].book_value_per_share == 20.0
    assert metrics[0].period == "ttm"
    assert metrics[0].revenue_growth == (1000.0 - 650.0) / 650.0
    assert metrics[0].current_ratio == 2.0


def test_yfinance_financial_metrics_preserve_zero_values(fake_provider, monkeypatch):
    provider, _ = fake_provider
    monkeypatch.setattr(provider, "_historical_close", lambda ticker_obj, end_date: 50.0)
    monkeypatch.setattr(
        provider,
        "_line_item_records",
        lambda *args, **kwargs: [
            {
                "ticker": "FAKE_ZERO",
                "report_period": "2024-12-31",
                "period": "annual",
                "currency": "USD",
                "revenue": 1000.0,
                "gross_profit": 0.0,
                "operating_income": 0.0,
                "net_income": 0.0,
                "free_cash_flow": 0.0,
                "total_assets": 2000.0,
                "current_assets": 0.0,
                "current_liabilities": 300.0,
                "total_debt": 0.0,
                "shareholders_equity": 500.0,
                "outstanding_shares": 20.0,
                "earnings_per_share": 0.0,
            },
            {
                "ticker": "FAKE_ZERO",
                "report_period": "2023-12-31",
                "period": "annual",
                "currency": "USD",
                "revenue": 1000.0,
                "net_income": 0.0,
            },
        ],
    )

    latest = provider.get_financial_metrics("FAKE_ZERO", "2024-12-31", period="annual", limit=2)[0]

    assert latest.gross_margin == 0.0
    assert latest.operating_margin == 0.0
    assert latest.net_margin == 0.0
    assert latest.return_on_equity == 0.0
    assert latest.current_ratio == 0.0
    assert latest.debt_to_equity == 0.0
    assert latest.revenue_growth == 0.0
    assert latest.earnings_growth == 0.0
    assert latest.earnings_per_share == 0.0
    assert latest.free_cash_flow_yield == 0.0


def test_yfinance_financial_metrics_return_empty_when_statements_missing(fake_provider):
    provider, fake = fake_provider
    fake.financials = pd.DataFrame()
    fake.balance_sheet = pd.DataFrame()
    fake.cashflow = pd.DataFrame()
    fake.quarterly_financials = pd.DataFrame()
    fake.quarterly_balance_sheet = pd.DataFrame()
    fake.quarterly_cashflow = pd.DataFrame()

    assert provider.get_financial_metrics("FAKE_EMPTY", "2024-12-31", period="annual") == []
    assert provider.get_market_cap("FAKE_EMPTY", "2024-12-31") is None


def test_yfinance_historical_market_cap_uses_close_and_shares(fake_provider, monkeypatch):
    provider, _ = fake_provider
    monkeypatch.setattr(provider, "_historical_close", lambda ticker_obj, end_date: 50.0)

    market_cap = provider.get_market_cap("FAKE_MARKET_CAP", "2024-12-31")

    assert market_cap == 1000.0


def test_yfinance_news_and_insider_transactions(fake_provider):
    provider, _ = fake_provider

    news = provider.get_company_news("FAKE_NEWS", "2024-12-31", start_date="2024-12-01", limit=10)
    trades = provider.get_insider_trades("FAKE_TRADES", "2024-12-31", start_date="2024-12-01", limit=10)

    assert news[0].title == "Fake beats expectations"
    assert news[0].source == "Market News"
    assert trades[0].name == "Jane Doe"
    assert trades[0].transaction_price_per_share == 100.0


def test_yfinance_insider_trades_filter_dates_before_limit(fake_provider):
    provider, fake = fake_provider
    fake.insider_transactions = pd.DataFrame(
        [
            {
                "Start Date": "2023-01-15",
                "Insider": "Old Seller",
                "Position": "Director",
                "Shares": 5.0,
                "Value": 250.0,
                "Transaction": "Sale",
            },
            {
                "Start Date": "2024-12-15",
                "Insider": "Jane Doe",
                "Position": "CEO",
                "Shares": 10.0,
                "Value": 1000.0,
                "Transaction": "Sale",
            },
        ]
    )

    trades = provider.get_insider_trades("FAKE_TRADES_FILTER", "2024-12-31", start_date="2024-12-01", limit=1)

    assert len(trades) == 1
    assert trades[0].name == "Jane Doe"
