"""Tests for the Tushare valuation provider.

No real token or network is required: the SDK is mocked via sys.modules and
``_get_pro`` is monkeypatched to return a fake pro client.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import Mock

import pandas as pd
import pytest

from src.tools import api_tushare


@pytest.fixture
def fresh(monkeypatch):
    """Token enabled, breaker reset, table memo cleared."""
    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")
    monkeypatch.setattr(api_tushare, "_disabled", False)
    monkeypatch.setattr(api_tushare, "_daily_basic_tables", {})
    # Reset any cached pro client from a prior test.
    monkeypatch.setattr(api_tushare._get_pro, "_pro", None, raising=False)
    return monkeypatch


def test_get_pro_returns_none_when_no_token(monkeypatch):
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    assert api_tushare._get_pro() is None


def test_get_pro_returns_cached_client_when_token_set(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")
    fake_ts = types.ModuleType("tushare")
    fake_ts.set_token = lambda token: None
    client = object()
    pro_api = Mock(return_value=client)
    fake_ts.pro_api = pro_api
    monkeypatch.setitem(sys.modules, "tushare", fake_ts)
    monkeypatch.setattr(api_tushare._get_pro, "_pro", None, raising=False)

    first = api_tushare._get_pro()
    second = api_tushare._get_pro()
    assert first is client
    assert second is client
    assert pro_api.call_count == 1  # cached → pro_api constructed only once


def test_to_float_rejects_nan_inf_and_garbage():
    """Tushare daily_basic yields pe=price/eps, which is inf for loss-makers;
    those must not leak into the valuation block."""
    assert api_tushare._to_float(None) is None
    assert api_tushare._to_float(float("nan")) is None
    assert api_tushare._to_float(float("inf")) is None
    assert api_tushare._to_float(float("-inf")) is None
    assert api_tushare._to_float("not-a-number") is None
    assert api_tushare._to_float("3.14") == 3.14
    assert api_tushare._to_float(0.0) == 0.0


def _valuation_frame(ts_code="600519.SH", total_mv=2.0e7, pe=30.0, pb=8.0, ps=15.0):
    """total_mv is in 万元 (2.0e7 万元 == 2.0e11 元)."""
    return pd.DataFrame(
        [
            {
                "ts_code": ts_code,
                "trade_date": "20260707",
                "total_mv": total_mv,
                "pe": pe,
                "pb": pb,
                "ps": ps,
                "circ_mv": total_mv,
            }
        ]
    )


def _fake_pro_with(daily_basic_fn):
    pro = types.SimpleNamespace()
    pro.daily_basic = daily_basic_fn
    return pro


def test_permission_error_trips_breaker_and_second_call_is_free(fresh, monkeypatch):
    calls = {"n": 0}

    def bad(trade_date=""):
        calls["n"] += 1
        raise RuntimeError("抱歉，您权限不足，需要 2000 积分")

    monkeypatch.setattr(api_tushare, "_get_pro", lambda: _fake_pro_with(bad))

    assert api_tushare._daily_basic_table("20260707") is None
    assert api_tushare._disabled is True
    assert api_tushare._daily_basic_table("20260707") is None  # short-circuit
    assert calls["n"] == 1  # breaker prevented a second SDK call


def test_transient_error_does_not_trip_breaker(fresh, monkeypatch):
    def flaky(trade_date=""):
        raise ConnectionError("RemoteDisconnected")

    monkeypatch.setattr(api_tushare, "_get_pro", lambda: _fake_pro_with(flaky))

    assert api_tushare._daily_basic_table("20260707") is None
    assert api_tushare._disabled is False  # transient must NOT latch


def test_empty_frame_returns_none_without_tripping(fresh, monkeypatch):
    monkeypatch.setattr(
        api_tushare, "_get_pro", lambda: _fake_pro_with(lambda trade_date="": pd.DataFrame())
    )
    assert api_tushare._daily_basic_table("20260707") is None
    assert api_tushare._disabled is False


def test_table_is_memoized_per_trade_date(fresh, monkeypatch):
    calls = {"n": 0}

    def single(trade_date=""):
        calls["n"] += 1
        return _valuation_frame()

    monkeypatch.setattr(api_tushare, "_get_pro", lambda: _fake_pro_with(single))

    first = api_tushare._daily_basic_table("20260707")
    second = api_tushare._daily_basic_table("20260707")
    assert first is second  # same cached DataFrame object
    assert calls["n"] == 1


def test_no_token_returns_none_without_calling_sdk(fresh, monkeypatch):
    calls = {"n": 0}

    def boom(trade_date=""):
        calls["n"] += 1
        raise AssertionError("SDK must not be called without a token")

    monkeypatch.setattr(api_tushare, "_get_pro", lambda: None)
    assert api_tushare._daily_basic_table("20260707") is None
    assert calls["n"] == 0


def test_get_valuation_converts_units_and_returns_ratios(fresh, monkeypatch):
    monkeypatch.setattr(
        api_tushare,
        "_get_pro",
        lambda: _fake_pro_with(
            lambda trade_date="": _valuation_frame() if trade_date == "20260707" else pd.DataFrame()
        ),
    )

    v = api_tushare.get_valuation("600519.SH", "2026-07-07")
    assert v is not None
    assert v["market_cap"] == pytest.approx(2.0e7 * 1e4)  # 万元 → 元
    assert v["pe"] == 30.0
    assert v["pb"] == 8.0
    assert v["ps"] == 15.0
    assert v["trade_date"] == "20260707"


def test_get_valuation_walks_back_to_nearest_trading_day(fresh, monkeypatch):
    # 2026-07-04 is a Saturday; only Friday 2026-07-03 has data.
    def fake(trade_date=""):
        return _valuation_frame() if trade_date == "20260703" else pd.DataFrame()

    monkeypatch.setattr(api_tushare, "_get_pro", lambda: _fake_pro_with(fake))

    v = api_tushare.get_valuation("600519.SH", "2026-07-04")
    assert v is not None
    assert v["trade_date"] == "20260703"


def test_get_valuation_missing_ticker_returns_none(fresh, monkeypatch):
    monkeypatch.setattr(
        api_tushare, "_get_pro", lambda: _fake_pro_with(lambda trade_date="": _valuation_frame())
    )
    assert api_tushare.get_valuation("999999.SH", "2026-07-07") is None


def test_get_valuation_disabled_short_circuits(monkeypatch):
    monkeypatch.setattr(api_tushare, "_disabled", True)
    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")
    assert api_tushare.get_valuation("600519.SH", "2026-07-07") is None
