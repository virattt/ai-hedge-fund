"""Tests for the pre-warm step (:mod:`src.utils.data_warming`).

The warm step introspects the installed analyst modules to learn the union of
data they will request, fetches it once per distinct key *before* the analyst
fan-out, and seeds the shared cache. After warming, replaying every agent's
request must produce ZERO additional API calls.
"""
import threading

import pytest

from src.data.cache import Cache
from src.data.models import FinancialMetrics
from src.tools import api as api_mod

_FM_FIELDS = list(FinancialMetrics.model_fields)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _periods(limit):
    return [f"{2024 - i}-12-31" for i in range(limit)]


@pytest.fixture
def fresh_cache(monkeypatch):
    cache = Cache()
    monkeypatch.setattr(api_mod, "_cache", cache)
    return cache


@pytest.fixture
def counted_api(monkeypatch):
    """Thread-safe counting mock."""
    state = {"count": 0, "lock": threading.Lock()}

    def fake(url, headers, method="GET", json_data=None, max_retries=3):
        with state["lock"]:
            state["count"] += 1
        import re

        if "financial-metrics" in url:
            m = re.search(r"limit=(\d+)", url)
            limit = int(m.group(1)) if m else 10
            p = re.search(r"period=(\w+)", url)
            period = p.group(1) if p else "ttm"
            metrics = []
            for rp in _periods(limit):
                metric = {fn: None for fn in _FM_FIELDS}
                metric.update({"ticker": "AAPL", "report_period": rp, "period": period, "currency": "USD", "market_cap": 1e12})
                metrics.append(metric)
            return FakeResponse({"financial_metrics": metrics})
        if "line-items" in url:
            fields = json_data["line_items"]
            limit = json_data["limit"]
            period = json_data.get("period", "ttm")
            rows = []
            for idx, rp in enumerate(_periods(limit)):
                row = {"ticker": "AAPL", "report_period": rp, "period": period, "currency": "USD"}
                for f in fields:
                    row[f] = float(idx + 1)
                rows.append(row)
            return FakeResponse({"search_results": rows})
        return FakeResponse({}, status_code=404)

    monkeypatch.setattr(api_mod, "_make_api_request", fake)
    return state


class TestComputeAgentDataNeeds:
    def test_finds_metrics_periods_and_limits(self):
        from src.utils.data_warming import compute_agent_data_needs

        needs = compute_agent_data_needs()
        # The real agents request both annual and ttm metrics.
        assert "annual" in needs["metrics"]
        assert "ttm" in needs["metrics"]
        assert needs["metrics"]["annual"] >= 5
        assert needs["metrics"]["ttm"] >= 5

    def test_finds_line_item_keys_with_fields(self):
        from src.utils.data_warming import compute_agent_data_needs

        needs = compute_agent_data_needs()
        assert needs["line_items"], "expected line-item (period, limit) keys"
        # At least one annual and one ttm key, each with real fields.
        periods = {p for (p, _l) in needs["line_items"]}
        assert "annual" in periods
        assert "ttm" in periods
        for fields in needs["line_items"].values():
            assert len(fields) > 0


class TestWarmThenAgentsHitCache:
    def test_warm_seeds_cache_then_agents_make_zero_calls(self, fresh_cache, counted_api):
        from src.utils.data_warming import (
            extract_agent_data_requests,
            warm_cache_for_tickers,
        )

        warm_cache_for_tickers(["AAPL"], "2024-01-01")
        calls_after_warm = counted_api["count"]
        assert calls_after_warm > 0, "warm should have issued fetches"

        # Replay every agent's request exactly. With the cache pre-warmed, none
        # of these should reach the API.
        for req in extract_agent_data_requests():
            if req["kind"] == "metrics":
                api_mod.get_financial_metrics("AAPL", "2024-01-01", period=req["period"], limit=req["limit"])
            else:
                api_mod.search_line_items("AAPL", sorted(req["fields"]), "2024-01-01", period=req["period"], limit=req["limit"])

        assert counted_api["count"] == calls_after_warm, "agents triggered extra API calls after warm"

    def test_warm_is_idempotent(self, fresh_cache, counted_api):
        from src.utils.data_warming import warm_cache_for_tickers

        warm_cache_for_tickers(["AAPL"], "2024-01-01")
        first = counted_api["count"]
        warm_cache_for_tickers(["AAPL"], "2024-01-01")
        assert counted_api["count"] == first, "second warm re-fetched data"

    def test_warm_handles_multiple_tickers(self, fresh_cache, counted_api):
        from src.utils.data_warming import warm_cache_for_tickers

        warm_cache_for_tickers(["AAPL", "MSFT"], "2024-01-01")
        # Both tickers fetched; exact count is deterministic-ish (>= 2x one).
        assert counted_api["count"] >= 2


class TestStartNodeIntegration:
    def test_start_node_warms_cache_with_tickers_and_end_date(self, monkeypatch):
        import src.main as main_mod
        import src.utils.data_warming as dw

        captured = {}

        def fake_warm(tickers, end_date, api_key=None, max_workers=8):
            captured["tickers"] = list(tickers)
            captured["end_date"] = end_date

        monkeypatch.setattr(dw, "warm_cache_for_tickers", fake_warm)

        state = {"data": {"tickers": ["AAPL", "MSFT"], "end_date": "2024-01-01"}, "metadata": {}}
        result = main_mod.start(state)

        assert captured.get("tickers") == ["AAPL", "MSFT"]
        assert captured.get("end_date") == "2024-01-01"
        assert result is state  # start still returns state unchanged

    def test_start_node_skips_warm_when_no_tickers(self, monkeypatch):
        import src.main as main_mod
        import src.utils.data_warming as dw

        called = {"n": 0}

        def fake_warm(*args, **kwargs):
            called["n"] += 1

        monkeypatch.setattr(dw, "warm_cache_for_tickers", fake_warm)
        main_mod.start({"data": {"tickers": [], "end_date": "2024-01-01"}, "metadata": {}})
        assert called["n"] == 0
