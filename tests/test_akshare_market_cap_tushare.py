"""Tests that get_market_cap prefers Tushare valuation and falls back when None."""
from __future__ import annotations

import pandas as pd
import pytest

from src.tools import api_akshare, api_tushare  # patch the module directly


@pytest.fixture
def fresh_state(monkeypatch):
    from src.data.cache import Cache

    monkeypatch.setattr(api_akshare, "_cache", Cache())
    monkeypatch.setattr(api_akshare, "_spot_table", None, raising=False)
    monkeypatch.setattr(api_akshare, "_spot_table_attempted", False, raising=False)


def test_tushare_value_is_returned_without_hitting_spot(fresh_state, monkeypatch):
    monkeypatch.setattr(
        api_tushare,
        "get_valuation",
        lambda ticker, as_of_date: {"market_cap": 2.0e12, "pe": 30.0, "pb": 8.0, "ps": 15.0, "trade_date": "20260707"},
    )
    monkeypatch.setattr(
        api_akshare,
        "_get_spot_table",
        lambda: pytest.fail("spot table must not be fetched when Tushare resolves"),
    )
    assert api_akshare.get_market_cap("600519.SH", "2026-07-07") == 2.0e12


def test_falls_back_to_spot_when_tushare_returns_none(fresh_state, monkeypatch):
    monkeypatch.setattr(api_tushare, "get_valuation", lambda ticker, as_of_date: None)
    spot = pd.DataFrame({"代码": ["600519"], "总市值": [1.5e12]})
    monkeypatch.setattr(api_akshare, "_get_spot_table", lambda: spot)
    assert api_akshare.get_market_cap("600519.SH", "2026-07-07") == 1.5e12
