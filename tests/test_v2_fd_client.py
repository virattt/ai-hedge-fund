from v2.data.client import FDClient
from v2.data.models import CompanyFacts, FinancialMetrics


class DummyFDClient(FDClient):
    def __init__(self, facts=None, metrics=None):
        self._facts = facts
        self._metrics = metrics or []

    def get_company_facts(self, ticker: str):
        return self._facts

    def get_financial_metrics(self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10):
        return self._metrics


def test_company_facts_accepts_market_cap():
    facts = CompanyFacts(ticker="AAPL", market_cap=3_000_000_000_000)

    assert facts.market_cap == 3_000_000_000_000


def test_get_market_cap_uses_company_facts_first():
    client = DummyFDClient(
        facts=CompanyFacts(ticker="AAPL", market_cap=3_000_000_000_000),
        metrics=[FinancialMetrics(ticker="AAPL", report_period="2024-12-31", period="ttm", market_cap=1)],
    )

    assert client.get_market_cap("AAPL", "2024-12-31") == 3_000_000_000_000


def test_get_market_cap_falls_back_to_financial_metrics():
    client = DummyFDClient(
        facts=CompanyFacts(ticker="AAPL"),
        metrics=[FinancialMetrics(ticker="AAPL", report_period="2024-12-31", period="ttm", market_cap=1_000_000)],
    )

    assert client.get_market_cap("AAPL", "2024-12-31") == 1_000_000
