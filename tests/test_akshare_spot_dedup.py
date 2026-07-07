"""Tests for the all-market spot-table memoization in ``get_market_cap``.

``ak.stock_zh_a_spot_em`` returns the realtime spot row for *every* A-share
(~5,000 rows) in a single call. ``get_market_cap`` therefore must fetch it once
per process and look each ticker up from the shared table. Without that, the
concurrent analyst fan-out fires the heavy endpoint once per agent per ticker
and Eastmoney rate-limits the run — closing the connection mid-flight
(``RemoteDisconnected``).
"""
from __future__ import annotations

import threading

import pandas as pd
import pytest

from src.tools import api_akshare


@pytest.fixture
def fresh_akshare_state(monkeypatch):
    """Isolate each test from the global cache singleton and spot-table memo."""
    from src.data.cache import Cache

    cache = Cache()
    monkeypatch.setattr(api_akshare, "_cache", cache)
    # ``_spot_table`` is added by the fix; ``raising=False`` lets this test
    # also run against the unfixed code so the bug shows up as an assertion
    # failure (N calls) rather than a setup error.
    monkeypatch.setattr(api_akshare, "_spot_table", None, raising=False)
    # get_market_cap now consults Tushare first; force the no-token path so
    # these spot-path tests are deterministic even if TUSHARE_TOKEN is in env.
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    return cache


def test_get_market_cap_fetches_spot_table_once_across_callers(fresh_akshare_state, monkeypatch):
    """Many concurrent ``get_market_cap`` calls must trigger exactly one
    ``stock_zh_a_spot_em()`` call — the shared table covers every ticker."""
    counts = {"n": 0}
    guard = threading.Lock()

    def fake_spot_em():
        # Simulate the heavy endpoint and race-window other callers would
        # double-fetch through if the memo weren't serialised.
        with guard:
            counts["n"] += 1
        return pd.DataFrame(
            {
                "代码": ["600519", "603444", "000001"],
                "总市值": [2.0e12, 5.0e9, 3.0e11],
            }
        )

    monkeypatch.setattr(api_akshare.ak, "stock_zh_a_spot_em", fake_spot_em)
    monkeypatch.setattr(
        api_akshare.ak,
        "stock_individual_info_em",
        lambda symbol: pytest.fail("fallback must not run when the spot table resolves"),
    )

    tickers = ["600519.SH", "603444.SH", "000001.SZ"] * 6  # 18 calls, 3 distinct
    results: list[float | None] = [None] * len(tickers)

    def worker(i, ticker):
        results[i] = api_akshare.get_market_cap(ticker, "2026-07-02")

    threads = [threading.Thread(target=worker, args=(i, t)) for i, t in enumerate(tickers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert counts["n"] == 1, f"spot endpoint hit {counts['n']} times, expected 1"
    expected = {
        "600519.SH": 2.0e12,
        "603444.SH": 5.0e9,
        "000001.SZ": 3.0e11,
    }
    for ticker, cap in zip(tickers, results):
        assert cap == expected[ticker], f"{ticker}: got {cap}, want {expected[ticker]}"


def test_get_market_cap_falls_back_when_spot_fetch_fails(fresh_akshare_state, monkeypatch):
    """If the spot endpoint fails outright, fall back to the per-ticker call."""
    monkeypatch.setattr(api_akshare.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        api_akshare.ak,
        "stock_zh_a_spot_em",
        lambda: (_ for _ in ()).throw(ConnectionError("Remote end closed connection")),
    )

    def fake_info(symbol):
        return pd.DataFrame([{"item": "总市值", "value": 1.23e10}, {"item": "other", "value": 0}])

    monkeypatch.setattr(api_akshare.ak, "stock_individual_info_em", fake_info)

    cap = api_akshare.get_market_cap("603444.SH", "2026-07-02")
    assert cap == 1.23e10
