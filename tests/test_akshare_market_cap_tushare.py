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
    monkeypatch.setattr(api_akshare, "_market_cap_cache", {})


def test_market_cap_result_cached_per_ticker(fresh_state, monkeypatch):
    """The full attempt chain runs once per ticker; the 10+ analysts that
    re-call get_market_cap must hit the cache, not re-fire the Eastmoney fallback."""
    monkeypatch.setattr(api_akshare.time, "sleep", lambda *_: None)
    monkeypatch.setattr(api_tushare, "get_valuation", lambda ticker, as_of_date: None)  # no Tushare
    monkeypatch.setattr(api_akshare, "_get_spot_table", lambda: None)  # spot unavailable
    info_calls = {"n": 0}

    def counting_info(symbol):
        info_calls["n"] += 1
        return pd.DataFrame([{"item": "总市值", "value": 9.9e9}])

    monkeypatch.setattr(api_akshare.ak, "stock_individual_info_em", counting_info)

    # Three analysts each ask for the SAME ticker — the Eastmoney fallback
    # must fire exactly once, not three times.
    assert api_akshare.get_market_cap("603444.SH", "2026-07-07") == 9.9e9
    assert api_akshare.get_market_cap("603444.SH", "2026-07-07") == 9.9e9
    assert api_akshare.get_market_cap("603444.SH", "2026-07-07") == 9.9e9
    assert info_calls["n"] == 1, f"individual_info_em hit {info_calls['n']} times, expected 1"


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
