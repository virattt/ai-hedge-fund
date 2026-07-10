"""Tests for A-share financial metric valuation source selection."""
from __future__ import annotations

import pandas as pd
import pytest

from src.tools import api_akshare, api_tushare  # patch the module directly


@pytest.fixture
def fresh_state(monkeypatch):
    from src.data.cache import Cache

    monkeypatch.setattr(api_akshare, "_cache", Cache())
    monkeypatch.delenv("A_SHARE_USE_TUSHARE_VALUATION", raising=False)


def _fake_abstract():
    # Two annual periods with one indicator; just enough for the function to
    # build FinancialMetrics records and exercise latest-vs-historical
    # valuation behavior.
    return pd.DataFrame(
        [{"选项": "财务摘要", "指标": "毛利率", "20241231": 91.5, "20231231": 88.2}]
    )


def test_latest_metrics_use_free_efinance_valuation_by_default(fresh_state, monkeypatch):
    monkeypatch.setattr(api_akshare.ak, "stock_financial_abstract", lambda symbol: _fake_abstract())
    monkeypatch.setattr(
        api_akshare.api_efinance,
        "get_realtime_valuation",
        lambda ticker: {
            "market_cap": 2.0e12,
            "pe": 30.0,
            "pb": 8.0,
            "ps": 15.0,
        },
    )
    monkeypatch.setattr(
        api_tushare,
        "get_valuation",
        lambda ticker, as_of_date: pytest.fail("Tushare must be opt-in"),
    )

    metrics = api_akshare.get_financial_metrics("600519.SH", "2025-12-31", period="annual", limit=5)
    assert len(metrics) == 2

    latest = metrics[0]
    assert latest.report_period == "2024-12-31"
    assert latest.market_cap == 2.0e12
    assert latest.price_to_earnings_ratio == 30.0
    assert latest.price_to_book_ratio == 8.0
    assert latest.price_to_sales_ratio == 15.0

    historical = metrics[1]
    assert historical.report_period == "2023-12-31"
    assert historical.market_cap is None
    assert historical.price_to_earnings_ratio is None
    assert historical.price_to_book_ratio is None
    assert historical.price_to_sales_ratio is None


def test_metrics_without_free_valuation_do_not_call_tushare_by_default(fresh_state, monkeypatch):
    monkeypatch.setattr(api_akshare.ak, "stock_financial_abstract", lambda symbol: _fake_abstract())
    monkeypatch.setattr(api_akshare.api_efinance, "get_realtime_valuation", lambda ticker: None)
    monkeypatch.setattr(
        api_tushare,
        "get_valuation",
        lambda ticker, as_of_date: pytest.fail("Tushare must be opt-in"),
    )

    metrics = api_akshare.get_financial_metrics("600519.SH", "2025-12-31", period="annual", limit=5)
    assert len(metrics) == 2
    for metric in metrics:
        assert metric.market_cap is None
        assert metric.price_to_earnings_ratio is None
        assert metric.price_to_book_ratio is None
        assert metric.price_to_sales_ratio is None


def test_metrics_use_tushare_only_when_opted_in(fresh_state, monkeypatch):
    monkeypatch.setenv("A_SHARE_USE_TUSHARE_VALUATION", "1")
    monkeypatch.setattr(api_akshare.ak, "stock_financial_abstract", lambda symbol: _fake_abstract())
    monkeypatch.setattr(api_akshare.api_efinance, "get_realtime_valuation", lambda ticker: None)
    monkeypatch.setattr(
        api_tushare,
        "get_valuation",
        lambda ticker, as_of_date: {
            "market_cap": 2.0e12,
            "pe": 30.0,
            "pb": 8.0,
            "ps": 15.0,
            "trade_date": as_of_date.replace("-", ""),
        },
    )

    metrics = api_akshare.get_financial_metrics("600519.SH", "2025-12-31", period="annual", limit=5)
    assert len(metrics) >= 1
    m = metrics[0]
    assert m.market_cap == 2.0e12
    assert m.price_to_earnings_ratio == 30.0
    assert m.price_to_book_ratio == 8.0
    assert m.price_to_sales_ratio == 15.0
