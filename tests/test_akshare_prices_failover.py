"""Tests for the Eastmoney→Sina failover in api_akshare.get_prices.

Eastmoney stock_zh_a_hist has been persistently dropping connections; on
failure (or empty) get_prices must fall over to Sina stock_zh_a_daily, whose
columns are English and whose ``date`` is a datetime.date.
"""
from __future__ import annotations

import datetime

import pandas as pd
import pytest

from src.tools import api_akshare


@pytest.fixture
def fresh_cache(monkeypatch):
    from src.data.cache import Cache

    monkeypatch.setattr(api_akshare, "_cache", Cache())
    monkeypatch.setattr(api_akshare.api_efinance, "get_prices", lambda *args, **kwargs: [])
    monkeypatch.setattr(api_akshare.api_yfinance, "get_prices", lambda *args, **kwargs: [])


def _sina_row(d, o, h, l, c, v):
    return {
        "date": d,
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": v,
        "amount": 0.0,
        "outstanding_share": 0.0,
        "turnover": 0.0,
    }


def test_hist_failure_falls_over_to_sina(fresh_cache, monkeypatch):
    monkeypatch.setattr(api_akshare.time, "sleep", lambda *_: None)
    sina_df = pd.DataFrame(
        [_sina_row(datetime.date(2026, 7, 6), 1186.0, 1215.0, 1180.0, 1206.91, 4097001.0)]
    )
    monkeypatch.setattr(
        api_akshare.ak, "stock_zh_a_hist", lambda **kw: (_ for _ in ()).throw(ConnectionError("RemoteDisconnected"))
    )
    monkeypatch.setattr(api_akshare.ak, "stock_zh_a_daily", lambda **kw: sina_df)

    prices = api_akshare.get_prices("600519.SH", "2026-07-01", "2026-07-07")
    assert len(prices) == 1
    assert prices[0].close == 1206.91
    assert prices[0].time == "2026-07-06"  # datetime.date stringified


def test_hist_success_does_not_call_sina(fresh_cache, monkeypatch):
    monkeypatch.setattr(api_akshare.time, "sleep", lambda *_: None)
    hist_df = pd.DataFrame(
        [{"日期": "2026-07-06", "开盘": 1.0, "收盘": 2.0, "最高": 3.0, "最低": 0.5, "成交量": 100}]
    )
    monkeypatch.setattr(api_akshare.ak, "stock_zh_a_hist", lambda **kw: hist_df)
    monkeypatch.setattr(
        api_akshare.ak,
        "stock_zh_a_daily",
        lambda **kw: pytest.fail("Sina must not be called when Eastmoney succeeds"),
    )

    prices = api_akshare.get_prices("600519.SH", "2026-07-01", "2026-07-07")
    assert len(prices) == 1
    assert prices[0].close == 2.0


def test_hist_empty_falls_over_to_sina(fresh_cache, monkeypatch):
    monkeypatch.setattr(api_akshare.time, "sleep", lambda *_: None)
    sina_df = pd.DataFrame([_sina_row(datetime.date(2026, 7, 6), 1.0, 2.0, 0.5, 1.5, 10)])
    monkeypatch.setattr(api_akshare.ak, "stock_zh_a_hist", lambda **kw: pd.DataFrame())
    monkeypatch.setattr(api_akshare.ak, "stock_zh_a_daily", lambda **kw: sina_df)

    prices = api_akshare.get_prices("600519.SH", "2026-07-01", "2026-07-07")
    assert len(prices) == 1
    assert prices[0].close == 1.5


def test_hist_and_sina_failure_falls_over_to_efinance(fresh_cache, monkeypatch):
    monkeypatch.setattr(api_akshare.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        api_akshare.ak,
        "stock_zh_a_hist",
        lambda **kw: (_ for _ in ()).throw(ConnectionError("RemoteDisconnected")),
    )
    monkeypatch.setattr(
        api_akshare.ak,
        "stock_zh_a_daily",
        lambda **kw: (_ for _ in ()).throw(ConnectionError("RemoteDisconnected")),
    )

    fallback = [
        api_akshare.Price(
            time="2026-07-06",
            open=10.0,
            close=11.0,
            high=12.0,
            low=9.5,
            volume=1000,
        )
    ]
    monkeypatch.setattr(api_akshare.api_efinance, "get_prices", lambda *args, **kwargs: fallback)
    monkeypatch.setattr(
        api_akshare.api_yfinance,
        "get_prices",
        lambda *args, **kwargs: pytest.fail("Yahoo must not be called when efinance resolves"),
    )

    prices = api_akshare.get_prices("603444.SH", "2026-07-01", "2026-07-07")
    assert prices == fallback

    cached = api_akshare.get_prices("603444.SH", "2026-07-01", "2026-07-07")
    assert cached[0].close == 11.0


def test_hist_sina_and_efinance_failure_falls_over_to_yfinance(fresh_cache, monkeypatch):
    monkeypatch.setattr(api_akshare.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        api_akshare.ak,
        "stock_zh_a_hist",
        lambda **kw: (_ for _ in ()).throw(ConnectionError("RemoteDisconnected")),
    )
    monkeypatch.setattr(
        api_akshare.ak,
        "stock_zh_a_daily",
        lambda **kw: (_ for _ in ()).throw(ConnectionError("RemoteDisconnected")),
    )
    monkeypatch.setattr(api_akshare.api_efinance, "get_prices", lambda *args, **kwargs: [])
    fallback = [
        api_akshare.Price(
            time="2026-07-06",
            open=10.0,
            close=12.0,
            high=12.5,
            low=9.5,
            volume=2000,
        )
    ]
    monkeypatch.setattr(api_akshare.api_yfinance, "get_prices", lambda *args, **kwargs: fallback)

    prices = api_akshare.get_prices("603444.SH", "2026-07-01", "2026-07-07")
    assert prices == fallback
