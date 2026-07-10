"""Tests for composite data provider."""

from unittest.mock import MagicMock, patch

import pytest

from integrations.data.composite import CompositeDataClient
from integrations.data.config import DataConfig
from integrations.data.finnhub_client import FinnhubDataClient, _eps_surprise
from integrations.data.line_items import extract_line_item


@pytest.fixture
def config():
    return DataConfig(
        provider="composite",
        alpaca_api_key="alpaca-key",
        alpaca_secret_key="alpaca-secret",
        finnhub_api_key="finnhub-key",
    )


class TestFinnhubHelpers:
    def test_eps_surprise_beat(self):
        assert _eps_surprise(1.5, 1.4) == "BEAT"

    def test_eps_surprise_miss(self):
        assert _eps_surprise(1.2, 1.4) == "MISS"

    def test_eps_surprise_meet(self):
        assert _eps_surprise(1.0, 1.0) == "MEET"


class TestLineItems:
    def test_extract_revenue(self):
        report = {
            "ic": [
                {"concept": "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax", "value": 100_000_000},
            ]
        }
        assert extract_line_item(report, "revenue") == 100_000_000

    def test_compute_free_cash_flow(self):
        report = {
            "cf": [
                {"concept": "us-gaap_NetCashProvidedByUsedInOperatingActivities", "value": 50_000_000},
                {"concept": "us-gaap_PaymentsToAcquirePropertyPlantAndEquipment", "value": 10_000_000},
            ]
        }
        assert extract_line_item(report, "free_cash_flow") == 40_000_000


class TestSearchLineItems:
    def test_all_requested_keys_present_even_when_missing(self, config):
        client = FinnhubDataClient(config)
        reported = {
            "data": [
                {
                    "filingDate": "2024-05-02",
                    "period": "2024-03-31",
                    "report": {
                        "ic": [
                            {"concept": "us-gaap_Revenues", "value": 100.0},
                            {"concept": "us-gaap_OperatingIncomeLoss", "value": 25.0},
                        ]
                    },
                }
            ]
        }
        with patch.object(client, "_get", return_value=reported):
            rows = client.search_line_items(
                "AAPL", ["revenue", "operating_margin", "gross_margin"], "2024-12-31",
            )
        assert len(rows) == 1
        row = rows[0]
        # Every requested key must exist, even if None
        assert "operating_margin" in row
        assert "gross_margin" in row
        # Derived operating_margin = 25 / 100
        assert row["operating_margin"] == 0.25
        # gross_margin can't be derived (no gross_profit) -> None, but key exists
        assert row["gross_margin"] is None

    def test_filters_future_filings(self, config):
        client = FinnhubDataClient(config)
        reported = {
            "data": [
                {"filingDate": "2025-05-02", "period": "2025-03-31", "report": {}},
            ]
        }
        with patch.object(client, "_get", return_value=reported):
            rows = client.search_line_items("AAPL", ["revenue"], "2024-12-31")
        assert rows == []


class TestFinnhubClient:
    def test_get_market_cap_from_profile(self, config):
        client = FinnhubDataClient(config)
        with patch.object(client, "_get", return_value={"marketCapitalization": 3000}) as mock_get:
            cap = client.get_market_cap("AAPL", "2024-01-31")
        assert cap == 3_000_000_000
        mock_get.assert_called_once()

    def test_get_company_facts_no_market_cap_attr(self, config):
        client = FinnhubDataClient(config)
        with patch.object(client, "_get", return_value={"name": "Apple Inc", "finnhubIndustry": "Technology", "marketCapitalization": 3000}):
            facts = client.get_company_facts("AAPL")
        assert facts is not None
        assert facts.name == "Apple Inc"
        assert not hasattr(facts, "market_cap") or getattr(facts, "market_cap", None) is None

    def test_get_earnings_history(self, config):
        client = FinnhubDataClient(config)
        with patch.object(client, "_get") as mock_get:
            mock_get.side_effect = [
                [
                    {"period": "2024-03-31", "actual": 1.5, "estimate": 1.4, "year": 2024, "quarter": 1},
                ],
                {"earningsCalendar": [{"year": 2024, "quarter": 1, "date": "2024-05-02"}]},
            ]
            records = client.get_earnings_history("AAPL", limit=1)
        assert len(records) == 1
        assert records[0].quarterly.eps_surprise == "BEAT"
        assert records[0].filing_date == "2024-05-02"


class TestCompositeClient:
    def test_routes_prices_to_alpaca(self, config):
        composite = CompositeDataClient(config)
        with patch.object(composite._alpaca, "get_prices", return_value=[]) as mock_prices:
            composite.get_prices("AAPL", "2024-01-01", "2024-01-31")
        mock_prices.assert_called_once()

    def test_routes_metrics_to_finnhub(self, config):
        composite = CompositeDataClient(config)
        with patch.object(composite._finnhub, "get_financial_metrics", return_value=[]) as mock_metrics:
            composite.get_financial_metrics("AAPL", "2024-01-31")
        mock_metrics.assert_called_once()


class TestV1Dispatch:
    def test_composite_provider_flag(self, monkeypatch):
        monkeypatch.setenv("DATA_PROVIDER", "composite")
        from integrations.data import use_composite_provider
        assert use_composite_provider() is True

    def test_get_prices_uses_composite(self, monkeypatch):
        monkeypatch.setenv("DATA_PROVIDER", "composite")
        from src.tools.api import get_prices

        mock_api = MagicMock()
        mock_api.get_prices.return_value = []
        monkeypatch.setattr("src.tools.api._composite_api", lambda: mock_api)

        get_prices("AAPL", "2024-01-01", "2024-01-31")
        mock_api.get_prices.assert_called_once()
