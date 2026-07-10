"""Snapshot store tests: roundtrip, latest resolution, CLI arg resolution."""

from __future__ import annotations

import pytest

from integrations.universe.models import FactorScore, TickerScore, UniverseSnapshot
from integrations.universe.store import (
    load_latest_universe,
    load_universe,
    resolve_universe_tickers,
    save_universe,
)


def _snapshot(as_of: str, tickers: list[str]) -> UniverseSnapshot:
    return UniverseSnapshot(
        as_of=as_of,
        generated_at="2026-07-10T00:00:00+00:00",
        size=len(tickers),
        tickers=tickers,
        scores=[
            TickerScore(
                ticker=t,
                composite=1.0 - i * 0.1,
                rank=i + 1,
                sector="TECH",
                factors={"dollar_volume": FactorScore(name="dollar_volume", raw=1.0, zscore=0.5, weight=1.0)},
            )
            for i, t in enumerate(tickers)
        ],
        stage_counts={"selected": len(tickers)},
    )


def test_save_load_roundtrip(tmp_path):
    snapshot = _snapshot("2026-07-01", ["AAPL", "MSFT"])
    path = save_universe(snapshot, tmp_path)
    loaded = load_universe(path)
    assert loaded == snapshot
    assert loaded.scores[0].factors["dollar_volume"].zscore == 0.5


def test_load_latest_picks_newest(tmp_path):
    save_universe(_snapshot("2026-06-01", ["OLD"]), tmp_path)
    save_universe(_snapshot("2026-07-01", ["NEW"]), tmp_path)
    (tmp_path / "notes.txt").write_text("ignore me")
    latest = load_latest_universe(tmp_path)
    assert latest is not None and latest.tickers == ["NEW"]


def test_load_latest_empty_dir(tmp_path):
    assert load_latest_universe(tmp_path) is None
    assert load_latest_universe(tmp_path / "missing") is None


def test_resolve_latest_and_path(tmp_path):
    path = save_universe(_snapshot("2026-07-01", ["AAPL", "NVDA"]), tmp_path)
    assert resolve_universe_tickers("latest", tmp_path) == ["AAPL", "NVDA"]
    assert resolve_universe_tickers(str(path), tmp_path) == ["AAPL", "NVDA"]


def test_resolve_errors(tmp_path):
    with pytest.raises(ValueError, match="No universe snapshots"):
        resolve_universe_tickers("latest", tmp_path)
    with pytest.raises(ValueError, match="not found"):
        resolve_universe_tickers(str(tmp_path / "nope.json"), tmp_path)
    save_universe(_snapshot("2026-07-01", []), tmp_path)
    with pytest.raises(ValueError, match="no tickers"):
        resolve_universe_tickers("latest", tmp_path)
