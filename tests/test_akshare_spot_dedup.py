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
    monkeypatch.setattr(api_akshare, "_spot_table_attempted", False, raising=False)
    monkeypatch.setattr(api_akshare, "_market_cap_cache", {})
    # Keep fallback providers deterministic so these tests isolate the AKShare
    # spot-table memoization behavior.
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    monkeypatch.delenv("TUSHARE_DATASETS_API_KEY", raising=False)
    monkeypatch.delenv("A_SHARE_USE_TUSHARE_VALUATION", raising=False)
    monkeypatch.setattr(api_akshare.api_tushare._get_pro, "_pro", None, raising=False)
    monkeypatch.setattr(api_akshare.api_efinance, "get_market_cap", lambda ticker: None)
    monkeypatch.setattr(api_akshare.api_yfinance, "get_market_cap", lambda ticker: None)
    return cache


def test_spot_failure_is_memoized_second_call_skips_refetch(fresh_akshare_state, monkeypatch):
    """A dead Eastmoney endpoint must not be re-retried on every market-cap call.

    10+ analysts each call get_market_cap per ticker; without memoizing the
    spot-table FAILURE, each call would re-pay the full ~30s retry backoff
    against a dead endpoint.
    """
    monkeypatch.setattr(api_akshare.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise ConnectionError("RemoteDisconnected")

    monkeypatch.setattr(api_akshare.ak, "stock_zh_a_spot_em", boom)
    # Per-ticker fallback must also fail, so get_market_cap returns None.
    monkeypatch.setattr(
        api_akshare.ak,
        "stock_individual_info_em",
        lambda symbol: (_ for _ in ()).throw(ConnectionError("dead")),
    )

    assert api_akshare.get_market_cap("600519.SH", "2026-07-07") is None
    after_first = calls["n"]
    assert after_first > 0, "first call should have attempted the spot endpoint"

    assert api_akshare.get_market_cap("603444.SH", "2026-07-07") is None
    after_second = calls["n"]
    # The second call must add ZERO spot fetches — the failure was memoized.
    # (Without memoization the second call would re-pay the full retry backoff.)
    assert after_second == after_first, (
        f"second get_market_cap re-fetched spot ({after_first} → {after_second})"
    )


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
