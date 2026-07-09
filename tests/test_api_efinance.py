from __future__ import annotations

import pandas as pd

from src.tools import api_efinance


def test_get_prices_parses_efinance_quote_history(monkeypatch):
    frame = pd.DataFrame(
        [
            {
                "股票名称": "吉比特",
                "股票代码": "603444",
                "日期": "2026-07-07",
                "开盘": 359.0,
                "收盘": 374.5,
                "最高": 390.0,
                "最低": 357.88,
                "成交量": 3818585,
            }
        ]
    )
    calls = {}

    class FakeStock:
        @staticmethod
        def get_quote_history(code, **kwargs):
            calls["code"] = code
            calls["beg"] = kwargs["beg"]
            calls["end"] = kwargs["end"]
            calls["klt"] = kwargs["klt"]
            calls["fqt"] = kwargs["fqt"]
            return frame

    class FakeEF:
        stock = FakeStock()

    monkeypatch.setattr(api_efinance, "ef", FakeEF)

    prices = api_efinance.get_prices("603444.SH", "2026-07-01", "2026-07-07")

    assert calls == {"code": "603444", "beg": "20260701", "end": "20260707", "klt": 101, "fqt": 1}
    assert len(prices) == 1
    assert prices[0].time == "2026-07-07"
    assert prices[0].close == 374.5
    assert prices[0].volume == 3818585


def test_get_realtime_valuation_parses_quote_table(monkeypatch):
    from src.data.cache import Cache

    monkeypatch.setattr(api_efinance, "_cache", Cache())
    monkeypatch.setattr(api_efinance, "_realtime_quotes", None)
    monkeypatch.setattr(api_efinance, "_realtime_quotes_attempted", False)
    frame = pd.DataFrame(
        [
            {
                "股票代码": "603444",
                "总市值": 26_979_392_324.5,
                "动态市盈率": 15.04,
                "市净率": 4.49,
                "市销率": 4.35,
            }
        ]
    )
    calls = {"n": 0}

    class FakeStock:
        @staticmethod
        def get_realtime_quotes():
            calls["n"] += 1
            return frame

    class FakeEF:
        stock = FakeStock()

    monkeypatch.setattr(api_efinance, "ef", FakeEF)

    first = api_efinance.get_realtime_valuation("603444.SH")
    second = api_efinance.get_realtime_valuation("603444.SH")

    assert first == {
        "market_cap": 26_979_392_324.5,
        "pe": 15.04,
        "pb": 4.49,
        "ps": 4.35,
    }
    assert second == first
    assert calls["n"] == 1


def test_get_realtime_valuation_matches_zero_padded_codes(monkeypatch):
    from src.data.cache import Cache

    monkeypatch.setattr(api_efinance, "_cache", Cache())
    monkeypatch.setattr(api_efinance, "_realtime_quotes", None)
    monkeypatch.setattr(api_efinance, "_realtime_quotes_attempted", False)
    frame = pd.DataFrame(
        [
            {
                "股票代码": 2415,
                "总市值": 100_000_000_000,
                "动态市盈率": 20.0,
            }
        ]
    )

    class FakeStock:
        @staticmethod
        def get_realtime_quotes():
            return frame

    class FakeEF:
        stock = FakeStock()

    monkeypatch.setattr(api_efinance, "ef", FakeEF)

    valuation = api_efinance.get_realtime_valuation("002415.SZ")
    assert valuation["market_cap"] == 100_000_000_000
    assert valuation["pe"] == 20.0
