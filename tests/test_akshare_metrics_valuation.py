"""Tests that get_financial_metrics fills market_cap/pe/pb/ps from Tushare
for each report period, and leaves them None when Tushare returns None."""
from __future__ import annotations

import pandas as pd
import pytest

from src.tools import api_akshare, api_tushare  # patch the module directly


@pytest.fixture
def fresh_state(monkeypatch):
    from src.data.cache import Cache

    monkeypatch.setattr(api_akshare, "_cache", Cache())


def _fake_abstract():
    # One annual period (2024-12-31) with one indicator; just enough for the
    # function to build a FinancialMetrics record.
    return pd.DataFrame([{"选项": "财务摘要", "指标": "毛利率", "20241231": 91.5}])


def test_metrics_filled_with_tushare_valuation(fresh_state, monkeypatch):
    monkeypatch.setattr(api_akshare.ak, "stock_financial_abstract", lambda symbol: _fake_abstract())
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


def test_metrics_valuation_none_keeps_fields_none(fresh_state, monkeypatch):
    monkeypatch.setattr(api_akshare.ak, "stock_financial_abstract", lambda symbol: _fake_abstract())
    monkeypatch.setattr(api_tushare, "get_valuation", lambda ticker, as_of_date: None)

    metrics = api_akshare.get_financial_metrics("600519.SH", "2025-12-31", period="annual", limit=5)
    assert len(metrics) >= 1
    m = metrics[0]
    assert m.market_cap is None
    assert m.price_to_earnings_ratio is None
    assert m.price_to_book_ratio is None
    assert m.price_to_sales_ratio is None
