from __future__ import annotations

import pandas as pd

from src.tools import api_yfinance


def test_yahoo_ticker_maps_a_share_suffixes():
    assert api_yfinance.yahoo_ticker("603444.SH") == "603444.SS"
    assert api_yfinance.yahoo_ticker("002415.SZ") == "002415.SZ"
    assert api_yfinance.yahoo_ticker("830799.BJ") is None


def test_get_prices_parses_yfinance_download(monkeypatch):
    frame = pd.DataFrame(
        [
            {
                "Open": 10.0,
                "High": 12.0,
                "Low": 9.5,
                "Close": 11.0,
                "Volume": 1234,
            }
        ],
        index=[pd.Timestamp("2026-07-06")],
    )
    calls = {}

    class FakeYF:
        @staticmethod
        def download(symbol, **kwargs):
            calls["symbol"] = symbol
            calls["end"] = kwargs["end"]
            return frame

    monkeypatch.setattr(api_yfinance, "yf", FakeYF)

    prices = api_yfinance.get_prices("603444.SH", "2026-07-01", "2026-07-06")

    assert calls == {"symbol": "603444.SS", "end": "2026-07-07"}
    assert len(prices) == 1
    assert prices[0].time == "2026-07-06"
    assert prices[0].close == 11.0
    assert prices[0].volume == 1234


def test_get_market_cap_prefers_fast_info(monkeypatch):
    class FakeTicker:
        fast_info = {"marketCap": 12_300_000_000}
        info = {"marketCap": 99}

    class FakeYF:
        @staticmethod
        def Ticker(symbol):
            assert symbol == "603444.SS"
            return FakeTicker()

    monkeypatch.setattr(api_yfinance, "yf", FakeYF)

    assert api_yfinance.get_market_cap("603444.SH") == 12_300_000_000


def test_get_market_cap_falls_back_to_info(monkeypatch):
    class FakeTicker:
        fast_info = {}
        info = {"marketCap": 8_800_000_000}

    class FakeYF:
        @staticmethod
        def Ticker(symbol):
            return FakeTicker()

    monkeypatch.setattr(api_yfinance, "yf", FakeYF)

    assert api_yfinance.get_market_cap("002415.SZ") == 8_800_000_000
