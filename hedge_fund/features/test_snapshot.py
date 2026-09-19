"""FundamentalsSnapshot tests — mocked data client, no network."""

import pytest

from hedge_fund.data.models import CompanyFacts, FinancialMetrics
from hedge_fund.features.snapshot import InsufficientData, SnapshotCache, build_snapshot


class MockDataClient:
    """Returns canned metrics; records what it was asked for."""

    def __init__(self, metrics=None, facts=None):
        self._metrics = metrics or []
        self._facts = facts
        self.metrics_calls = []

    def get_financial_metrics(self, ticker, end_date, period="ttm", limit=10):
        self.metrics_calls.append(
            {"ticker": ticker, "end_date": end_date, "period": period, "limit": limit}
        )
        return self._metrics

    def get_company_facts(self, ticker):
        return self._facts


def _metric(report_period, **kwargs):
    defaults = {
        "ticker": "TEST",
        "period": "ttm",
        "filing_date": report_period,  # simplification for tests
        "return_on_equity": 0.20,
        "net_margin": 0.25,
        "gross_margin": 0.40,
        "book_value_per_share": 10.0,
        "debt_to_equity": 0.5,
        "market_cap": 1e9,
    }
    defaults.update(kwargs)
    return FinancialMetrics(report_period=report_period, **defaults)


def _history(n=8):
    """n periods, newest first, quarter-spaced."""
    quarters = ["2024-12-31", "2024-09-30", "2024-06-30", "2024-03-31",
                "2023-12-31", "2023-09-30", "2023-06-30", "2023-03-31"]
    return [_metric(q) for q in quarters[:n]]


def test_as_of_passes_through_to_data_client():
    client = MockDataClient(metrics=_history())
    build_snapshot("TEST", "2025-01-15", client)
    call = client.metrics_calls[0]
    assert call["end_date"] == "2025-01-15"
    assert call["ticker"] == "TEST"


def test_insufficient_data_raises():
    client = MockDataClient(metrics=_history(3))  # below MIN_PERIODS
    with pytest.raises(InsufficientData):
        build_snapshot("TEST", "2025-01-15", client)


def test_aggregates():
    metrics = _history(4)
    # oldest gross margin 0.30, newest 0.40 -> trend +0.10
    metrics[-1] = _metric("2024-03-31", gross_margin=0.30)
    # BVPS oldest 8.0 -> newest 10.0 over 3 quarters (0.75y)
    metrics[-1].book_value_per_share = 8.0
    client = MockDataClient(metrics=metrics)

    snap = build_snapshot("TEST", "2025-01-15", client)

    assert snap.roe_avg == pytest.approx(0.20)
    assert snap.gross_margin_trend == pytest.approx(0.10)
    assert snap.debt_to_equity_latest == pytest.approx(0.5)
    assert snap.market_cap_latest == pytest.approx(1e9)
    assert snap.bvps_cagr == pytest.approx((10.0 / 8.0) ** (1 / 0.75) - 1, abs=1e-4)


def test_market_cap_comes_from_pit_metrics_not_facts():
    """company_facts market cap is latest-only (lookahead); the snapshot must
    use the most recent FILED metrics row instead."""
    facts = CompanyFacts(ticker="TEST", sector="Tech")
    client = MockDataClient(metrics=_history(), facts=facts)

    snap = build_snapshot("TEST", "2020-06-30", client)

    assert snap.market_cap_latest == pytest.approx(1e9)  # from metrics row
    assert snap.sector == "Tech"  # facts used only for slow-moving attributes


def test_content_hash_stable_and_sensitive():
    client_a = MockDataClient(metrics=_history())
    client_b = MockDataClient(metrics=_history())
    snap_a = build_snapshot("TEST", "2025-01-15", client_a)
    snap_b = build_snapshot("TEST", "2025-01-15", client_b)
    assert snap_a.content_hash == snap_b.content_hash  # same data -> same key

    changed = _history()
    changed[0] = _metric("2024-12-31", return_on_equity=0.35)
    snap_c = build_snapshot("TEST", "2025-01-15", MockDataClient(metrics=changed))
    assert snap_c.content_hash != snap_a.content_hash  # new filing -> new key


def test_same_data_different_as_of_same_render_and_hash():
    """Between filings the snapshot is unchanged — the hash and the rendered
    prompt must be identical on any as-of date, or the LLM cache never hits."""
    snap_jan = build_snapshot("TEST", "2025-01-15", MockDataClient(metrics=_history()))
    snap_feb = build_snapshot("TEST", "2025-02-15", MockDataClient(metrics=_history()))

    assert snap_jan.as_of != snap_feb.as_of  # the field itself still differs
    assert snap_jan.content_hash == snap_feb.content_hash
    assert snap_jan.render() == snap_feb.render()


def test_render_contains_the_facts():
    snap = build_snapshot("TEST", "2025-01-15", MockDataClient(metrics=_history()))
    text = snap.render()
    assert "2025-01-15" not in text  # as_of must never leak into the prompt
    assert "2024-12-31" in text
    assert "publicly filed" in text


# ---------------------------------------------------------------------------
# Cycle-scoped cache — one snapshot per (ticker, as_of)
# ---------------------------------------------------------------------------

class DriftClient(MockDataClient):
    """Each metrics fetch mutates D/E and ROE — a live feed mid-cycle."""

    def __init__(self, facts=None):
        super().__init__(metrics=_history(), facts=facts)
        self._n = 0

    def get_financial_metrics(self, ticker, end_date, period="ttm", limit=10):
        self._n += 1
        metrics = _history()
        metrics[0] = _metric(
            "2024-12-31",
            debt_to_equity=0.5 * self._n,
            return_on_equity=0.10 * self._n,
        )
        self.metrics_calls.append(
            {"ticker": ticker, "end_date": end_date, "period": period, "limit": limit}
        )
        return metrics


def test_uncached_builds_see_feed_drift():
    """Without a cache, two builds of the same name can disagree — the bug."""
    client = DriftClient()
    first = build_snapshot("TEST", "2025-01-15", client)
    second = build_snapshot("TEST", "2025-01-15", client)
    assert first.debt_to_equity_latest != second.debt_to_equity_latest
    assert first.periods[0].return_on_equity != second.periods[0].return_on_equity
    assert first.content_hash != second.content_hash


def test_cache_freezes_metrics_across_gets():
    """Same ticker, same as_of → the same object, first-fetch numbers."""
    client = DriftClient()
    cache = SnapshotCache()
    first = cache.get("TEST", "2025-01-15", client)
    second = cache.get("TEST", "2025-01-15", client)

    assert first is second
    assert first.debt_to_equity_latest == pytest.approx(0.5)
    assert first.periods[0].return_on_equity == pytest.approx(0.10)
    assert first.content_hash == second.content_hash
    assert first.render() == second.render()
    assert len(client.metrics_calls) == 1


def test_active_cache_makes_build_snapshot_reuse():
    """build_snapshot joins the cycle cache when one is bound."""
    client = DriftClient()
    with SnapshotCache():
        first = build_snapshot("TEST", "2025-01-15", client)
        second = build_snapshot("TEST", "2025-01-15", client)
    assert first is second
    assert first.debt_to_equity_latest == pytest.approx(0.5)
    assert len(client.metrics_calls) == 1


def test_cache_is_keyed_by_ticker():
    client = DriftClient()
    cache = SnapshotCache()
    aapl = cache.get("AAPL", "2025-01-15", client)
    msft = cache.get("MSFT", "2025-01-15", client)
    assert aapl is not msft
    assert aapl.ticker == "AAPL"
    assert msft.ticker == "MSFT"
    assert len(client.metrics_calls) == 2


def test_cache_memoizes_insufficient_data():
    client = MockDataClient(metrics=_history(2))
    cache = SnapshotCache()
    with pytest.raises(InsufficientData):
        cache.get("TEST", "2025-01-15", client)
    with pytest.raises(InsufficientData):
        cache.get("TEST", "2025-01-15", client)
    assert len(client.metrics_calls) == 1
