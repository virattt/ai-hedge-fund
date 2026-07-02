"""Tests for the cross-agent data dedup in :mod:`src.tools.api`.

Two behaviours are verified here:

1. ``search_line_items`` keeps a per-key set of already-fetched fields and only
   asks the API for fields it has not seen before (field-level subset caching).
2. ``get_financial_metrics`` drops ``limit`` from the cache key and tracks the
   max limit fetched, so a request for a smaller limit reuses a larger fetch
   (subset-on-limit).

A final benchmark test parses the *real* analyst source files with :mod:`ast`,
replays every agent's exact data requests through a counting mock, and reports
the before/after API-call reduction.
"""
import ast
import pathlib
import re

import pytest

from src.data.cache import Cache
from src.data.models import FinancialMetrics
from src.tools import api as api_mod


AGENTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "src" / "agents"

# Every FinancialMetrics field is required (Pydantic v2 `float | None` with no
# default = required-but-nullable), so a realistic mock must populate them all.
_FM_FIELDS = list(FinancialMetrics.model_fields)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _periods(limit):
    """Deterministic, most-recent-first report periods for a given limit."""
    # Same period strings for the same limit, so two calls with the same
    # (ticker, period, limit) line up on identical report_periods for merging.
    years = [2024 - i for i in range(limit)]
    return [f"{y}-12-31" for y in years]


@pytest.fixture
def fresh_cache(monkeypatch):
    """Isolate each test from the global cache singleton."""
    cache = Cache()
    monkeypatch.setattr(api_mod, "_cache", cache)
    return cache


@pytest.fixture
def counted_api(monkeypatch):
    """Replace ``_make_api_request`` with a counter that returns synthetic data
    shaped exactly like the real financialdatasets responses."""
    state = {"count": 0, "line_item_calls": [], "metrics_calls": []}

    def fake(url, headers, method="GET", json_data=None, max_retries=3):
        state["count"] += 1

        if "financial-metrics" in url:
            m = re.search(r"limit=(\d+)", url)
            limit = int(m.group(1)) if m else 10
            p = re.search(r"period=(\w+)", url)
            period = p.group(1) if p else "ttm"
            metrics = []
            for rp in _periods(limit):
                metric = {fn: None for fn in _FM_FIELDS}
                metric.update(
                    {
                        "ticker": "AAPL",
                        "report_period": rp,
                        "period": period,
                        "currency": "USD",
                        "market_cap": float(1e12),
                    }
                )
                metrics.append(metric)
            state["metrics_calls"].append(limit)
            return FakeResponse({"financial_metrics": metrics})

        if "line-items" in url:
            fields = json_data["line_items"]
            limit = json_data["limit"]
            period = json_data.get("period", "ttm")
            rows = []
            for idx, rp in enumerate(_periods(limit)):
                row = {
                    "ticker": "AAPL",
                    "report_period": rp,
                    "period": period,
                    "currency": "USD",
                }
                for f in fields:
                    row[f] = float(idx + 1) * 10.0
                rows.append(row)
            state["line_item_calls"].append(list(fields))
            return FakeResponse({"search_results": rows})

        return FakeResponse({}, status_code=404)

    monkeypatch.setattr(api_mod, "_make_api_request", fake)
    return state


# --------------------------------------------------------------------------- #
# search_line_items: field-subset caching
# --------------------------------------------------------------------------- #
class TestSearchLineItemsDedup:
    def test_identical_request_hits_cache(self, fresh_cache, counted_api):
        api_mod.search_line_items("AAPL", ["revenue", "net_income"], "2024-01-01", period="annual", limit=5)
        api_mod.search_line_items("AAPL", ["revenue", "net_income"], "2024-01-01", period="annual", limit=5)
        assert counted_api["count"] == 1

    def test_overlap_fetches_only_missing_fields(self, fresh_cache, counted_api):
        api_mod.search_line_items("AAPL", ["revenue", "net_income"], "2024-01-01", period="annual", limit=5)
        out = api_mod.search_line_items("AAPL", ["net_income", "eps"], "2024-01-01", period="annual", limit=5)
        # one call for the first request, one call ONLY for the missing "eps"
        assert counted_api["count"] == 2
        assert counted_api["line_item_calls"][1] == ["eps"]
        # merged rows carry both the cached and the newly-fetched fields
        assert all(getattr(row, "net_income") is not None for row in out)
        assert all(getattr(row, "eps") is not None for row in out)

    def test_disjoint_fields_make_two_calls(self, fresh_cache, counted_api):
        api_mod.search_line_items("AAPL", ["revenue"], "2024-01-01", period="annual", limit=5)
        api_mod.search_line_items("AAPL", ["eps"], "2024-01-01", period="annual", limit=5)
        assert counted_api["count"] == 2

    def test_pure_subset_makes_no_extra_call(self, fresh_cache, counted_api):
        api_mod.search_line_items("AAPL", ["revenue", "net_income", "eps"], "2024-01-01", period="annual", limit=5)
        api_mod.search_line_items("AAPL", ["net_income"], "2024-01-01", period="annual", limit=5)
        assert counted_api["count"] == 1

    def test_different_period_is_separate_fetch(self, fresh_cache, counted_api):
        api_mod.search_line_items("AAPL", ["revenue"], "2024-01-01", period="annual", limit=5)
        api_mod.search_line_items("AAPL", ["revenue"], "2024-01-01", period="ttm", limit=5)
        assert counted_api["count"] == 2

    def test_different_limit_is_separate_fetch(self, fresh_cache, counted_api):
        api_mod.search_line_items("AAPL", ["revenue"], "2024-01-01", period="annual", limit=5)
        api_mod.search_line_items("AAPL", ["revenue"], "2024-01-01", period="annual", limit=10)
        assert counted_api["count"] == 2


# --------------------------------------------------------------------------- #
# get_financial_metrics: subset-on-limit
# --------------------------------------------------------------------------- #
class TestFinancialMetricsLimitSubset:
    def test_smaller_limit_reuses_larger_fetch(self, fresh_cache, counted_api):
        api_mod.get_financial_metrics("AAPL", "2024-01-01", period="ttm", limit=10)
        api_mod.get_financial_metrics("AAPL", "2024-01-01", period="ttm", limit=5)
        assert counted_api["count"] == 1

    def test_larger_limit_triggers_refetch(self, fresh_cache, counted_api):
        api_mod.get_financial_metrics("AAPL", "2024-01-01", period="ttm", limit=5)
        api_mod.get_financial_metrics("AAPL", "2024-01-01", period="ttm", limit=10)
        assert counted_api["count"] == 2

    def test_different_period_separate(self, fresh_cache, counted_api):
        api_mod.get_financial_metrics("AAPL", "2024-01-01", period="ttm", limit=10)
        api_mod.get_financial_metrics("AAPL", "2024-01-01", period="annual", limit=10)
        assert counted_api["count"] == 2


# --------------------------------------------------------------------------- #
# Realistic benchmark: parse agent source, replay every request, count calls.
# --------------------------------------------------------------------------- #
def _extract_agent_requests():
    """Walk src/agents/*.py and collect every literal data request."""
    line_item_reqs = []  # (fields:list[str], period:str, limit:int)
    metrics_reqs = []  # (period:str, limit:int)

    for path in sorted(AGENTS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fname = node.func.id if isinstance(node.func, ast.Name) else None
            kws = {kw.arg: kw.value for kw in node.keywords}

            if fname == "search_line_items" and len(node.args) >= 2 and isinstance(node.args[1], ast.List):
                try:
                    fields = ast.literal_eval(node.args[1])
                except Exception:
                    continue
                period = ast.literal_eval(kws["period"]) if "period" in kws and isinstance(kws["period"], ast.Constant) else "ttm"
                limit = ast.literal_eval(kws["limit"]) if "limit" in kws and isinstance(kws["limit"], ast.Constant) else 10
                line_item_reqs.append((list(fields), period, int(limit)))

            elif fname == "get_financial_metrics":
                period = ast.literal_eval(kws["period"]) if "period" in kws and isinstance(kws["period"], ast.Constant) else "ttm"
                limit = ast.literal_eval(kws["limit"]) if "limit" in kws and isinstance(kws["limit"], ast.Constant) else 10
                metrics_reqs.append((period, int(limit)))

    return line_item_reqs, metrics_reqs


class TestDedupBenchmark:
    def test_real_agent_footprint_reduces_api_calls(self, fresh_cache, counted_api, capsys):
        li_reqs, fm_reqs = _extract_agent_requests()
        assert li_reqs, "expected to find search_line_items calls in agent source"
        assert fm_reqs, "expected to find get_financial_metrics calls in agent source"

        # Replay every request exactly as the agents would issue them.
        for fields, period, limit in li_reqs:
            api_mod.search_line_items("AAPL", fields, "2024-01-01", period=period, limit=limit)
        for period, limit in fm_reqs:
            api_mod.get_financial_metrics("AAPL", "2024-01-01", period=period, limit=limit)

        naive = len(li_reqs) + len(fm_reqs)
        actual = counted_api["count"]

        # Distinct (period, limit) keys — the absolute minimum fetches possible
        # if field-overlap were perfect.
        distinct_li_keys = len({(p, l) for _, p, l in li_reqs})
        distinct_fm_keys = len({(p, l) for p, l in fm_reqs})

        out = capsys.readouterr().out
        print(
            "\n================ dedup 回测效果 ================\n"
            f"line_items requests (agents) : {len(li_reqs)}\n"
            f"  distinct (period,limit)    : {distinct_li_keys}\n"
            f"  line_items API calls       : {len(counted_api['line_item_calls'])}\n"
            f"metrics requests (agents)    : {len(fm_reqs)}\n"
            f"  distinct (period,limit)    : {distinct_fm_keys}\n"
            f"  metrics API calls          : {len(counted_api['metrics_calls'])}\n"
            f"------------------------------------------------\n"
            f"naive total (1 call/req)     : {naive}\n"
            f"actual API calls (cached)    : {actual}\n"
            f"reduction                    : {naive - actual} ({(1 - actual / naive) * 100:.1f}%)\n"
            "================================================"
        )

        # Cache must help. The line_items gate is the meaningful one: with
        # caching, overlapping field requests across agents must collapse well
        # below the number of requests. (Currently every request = 1 call.)
        assert actual < naive, "cache did not reduce calls at all"
        assert len(counted_api["line_item_calls"]) < len(li_reqs), "line_items not deduped across agents"
        assert len(counted_api["metrics_calls"]) <= distinct_fm_keys, "metrics not deduped across limits"
