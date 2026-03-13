"""Tests for World Monitor cache job helpers."""

from autoresearch.cache_worldmonitor_signals import (
    _extract_quotes,
    _global_risk_from_quotes,
    fetch_and_cache_worldmonitor_signals,
)


def test_extract_quotes_handles_common_shapes():
    raw = {"quotes": [{"symbol": "VIX", "price": 22.5}, {"ticker": "SPY", "last": 500.0}]}
    out = _extract_quotes(raw)
    assert out["VIX"] == 22.5
    assert out["SPY"] == 500.0


def test_global_risk_from_quotes_vix_mapping():
    assert _global_risk_from_quotes({"VIX": 20.0}) == 40.0
    assert _global_risk_from_quotes({"VIX": 30.0}) == 80.0


def test_fetch_and_cache_worldmonitor_signals_with_mocked_client(monkeypatch):
    class _FakeClient:
        def get_json(self, path, params=None):
            assert "list-market-quotes" in path
            return {"quotes": [{"symbol": "VIX", "price": 25.0}]}

    monkeypatch.setattr(
        "autoresearch.cache_worldmonitor_signals.WorldMonitorClient",
        lambda: _FakeClient(),
    )
    snapshot = fetch_and_cache_worldmonitor_signals()
    assert snapshot["wm_global_risk_score"] == 60.0
    assert snapshot["wm_macro_regime"] == "neutral"

