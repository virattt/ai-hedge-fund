"""Offline unit tests for LuckymanProvider — mocks every HTTP call."""
from unittest.mock import MagicMock, patch

import requests

import pytest

from hedge_fund.data.luckyman import LuckymanError, LuckymanProvider


def _resp(status, payload):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload
    m.text = str(payload)
    return m


class TestHappy:
    @patch("hedge_fund.data.luckyman.requests.Session.request")
    def test_get_prices_filters_dates(self, req):
        req.return_value = _resp(200, [
            {"date": "2026-01-04", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100},
            {"date": "2026-01-10", "open": 2, "high": 3, "low": 1, "close": 2.5, "volume": 200},
            {"date": "2025-12-31", "open": 0, "high": 0, "low": 0, "close": 0, "volume": 0},
        ])
        with LuckymanProvider() as lm:
            bars = lm.get_prices("AAPL", "2026-01-01", "2026-01-31")
        assert len(bars) == 2
        assert bars[0].time == "2026-01-04"
        assert bars[1].close == 2.5

    @patch("hedge_fund.data.luckyman.requests.Session.request")
    def test_get_snapshot(self, req):
        req.return_value = _resp(200, [{"symbol": "AAPL", "regularMarketPrice": 339.5, "marketCap": 5_000_000_000_000}])
        with LuckymanProvider() as lm:
            snap = lm.get_snapshot("AAPL")
        assert snap is not None and snap.price == 339.5

    @patch("hedge_fund.data.luckyman.requests.Session.request")
    def test_insider_none_amounts(self, req):
        req.return_value = _resp(200, [
            {"formType": "4", "filedAt": "2026-10-19T00:00:00.000Z", "documentURL": "https://x.xml"},
        ])
        with LuckymanProvider() as lm:
            trades = lm.get_insider_trades("AAPL", "2026-10-31", "2026-10-01")
        assert len(trades) == 1
        t = trades[0]
        assert t.filing_date == "2026-10-19"
        assert t.transaction_shares is None  # honest None — no amount in filings index

    @patch("hedge_fund.data.luckyman.requests.Session.request")
    def test_honest_empties(self, req):
        with LuckymanProvider() as lm:
            assert lm.get_news("AAPL", "2026-01-01") == []
            assert lm.get_financial_metrics("AAPL", "2026-01-01") == []
            assert lm.get_company_facts("AAPL") is None
            assert lm.get_earnings("AAPL") is None


class TestFailLoud:
    @patch("hedge_fund.data.luckyman.requests.Session.request")
    def test_500_raises(self, req):
        req.return_value = _resp(503, {"error": "boom"})
        with LuckymanProvider() as lm:
            with pytest.raises(LuckymanError):
                lm.get_prices("AAPL", "2026-01-01", "2026-02-01")

    @patch("hedge_fund.data.luckyman.requests.Session.request")
    def test_network_raises(self, req):
        req.side_effect = requests.exceptions.ConnectionError("no net")
        with LuckymanProvider() as lm:
            with pytest.raises(LuckymanError):
                lm.get_snapshot("AAPL")

    @patch("hedge_fund.data.luckyman.requests.Session.request")
    def test_404_returns_none(self, req):
        req.return_value = _resp(404, {})
        with LuckymanProvider() as lm:
            assert lm.get_snapshot("NOPE") is None


class TestContract:
    @patch("hedge_fund.data.luckyman.requests.Session.request")
    def test_non_day_interval_raises(self, req):
        with LuckymanProvider() as lm:
            with pytest.raises(LuckymanError):
                lm.get_prices("AAPL", "2026-01-01", "2026-02-01", interval="week")

    def test_runtime_protocol(self):
        from hedge_fund.data.protocol import DataClient
        assert isinstance(LuckymanProvider(), DataClient)
