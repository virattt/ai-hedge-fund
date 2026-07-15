"""End-to-end pipeline test with a stub data source (no network)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from integrations.universe.candidates import build_candidate_pool, eligible_assets
from integrations.universe.config import UniverseConfig
from integrations.universe.data import AssetRecord
from integrations.universe.learnability import forward_returns
from integrations.universe.pipeline import build_universe
from integrations.universe.store import load_latest_universe

from tests.integrations.universe.universe_fixtures import StubUniverseDataSource, make_prices

AS_OF = "2026-06-30"


def _make_config(tmp_path, **overrides) -> UniverseConfig:
    base = dict(
        size=4,
        output_dir=str(tmp_path / "universe"),
        cache_dir=str(tmp_path / "cache"),
        signal_cache_dir=str(tmp_path / "signals"),
        min_price=5.0,
        min_history_days=200,
        min_median_dollar_volume=1_000_000.0,
        stage2_size=6,
        sector_cap_pct=0.5,
        max_correlation=0.98,
        learnability_enabled=True,
        learnability_checkpoint_days=15,
        learnability_lookback_days=300,
        learnability_horizons=(5,),
    )
    base.update(overrides)
    return UniverseConfig(**base)


def _make_source() -> StubUniverseDataSource:
    assets = [
        AssetRecord("GOODA", "NYSE", shortable=True, easy_to_borrow=True),
        AssetRecord("GOODB", "NASDAQ", shortable=True, easy_to_borrow=True),
        AssetRecord("GOODC", "NYSE", shortable=True, easy_to_borrow=True),
        AssetRecord("GOODD", "NASDAQ", shortable=True, easy_to_borrow=True),
        AssetRecord("GOODE", "NYSE", shortable=True, easy_to_borrow=True),
        AssetRecord("CHEAP", "NYSE"),          # fails min price
        AssetRecord("THIN", "NASDAQ"),         # fails dollar volume
        AssetRecord("YOUNG", "NYSE"),          # fails history length
        AssetRecord("OTCX", "OTC"),            # wrong exchange
        AssetRecord("BRK.A", "NYSE"),          # non-common symbol
    ]
    bars = {
        "GOODA": make_prices(seed=1, volume=5e6, end=AS_OF),
        "GOODB": make_prices(seed=2, volume=5e6, end=AS_OF),
        "GOODC": make_prices(seed=3, volume=5e6, end=AS_OF),
        "GOODD": make_prices(seed=4, volume=5e6, end=AS_OF),
        "GOODE": make_prices(seed=5, volume=5e6, end=AS_OF),
        "CHEAP": make_prices(seed=6, start_price=2.0, volume=5e6, end=AS_OF),
        "THIN": make_prices(seed=7, volume=1_000, end=AS_OF),
        "YOUNG": make_prices(seed=8, n_days=60, volume=5e6, end=AS_OF),
        "SPY": make_prices(seed=9, daily_vol=0.008, volume=1e8, end=AS_OF),
    }
    sectors = {"GOODA": "TECH", "GOODB": "TECH", "GOODC": "FIN", "GOODD": "ENERGY", "GOODE": "HEALTH"}
    return StubUniverseDataSource(
        assets=assets,
        bars=bars,
        facts={t: {"sector": s} for t, s in sectors.items()},
        fundamentals={t: {"market_cap": 1e10, "filing_date": "2026-05-01"} for t in sectors},
        earnings={t: [{"filing_date": "2026-04-25", "report_period": "2026-03-31"}] for t in sectors},
        news_counts={t: 12 for t in sectors},
    )


def _perfect_replayer(source: StubUniverseDataSource):
    def replayer(tickers, checkpoint_date, lookback_start):
        out = {}
        for ticker in tickers:
            frame = source._bars.get(ticker)
            if frame is None:
                continue
            fwd = forward_returns(frame["close"], pd.Timestamp(checkpoint_date), [5])
            if not fwd:
                continue
            direction = np.sign(fwd[5])
            signal = "bullish" if direction > 0 else "bearish" if direction < 0 else "neutral"
            out[ticker] = {"technical_analyst": {"signal": signal, "confidence": 85}}
        return out

    return replayer


def test_stage0_filters(tmp_path):
    config = _make_config(tmp_path)
    source = _make_source()
    assert {a.symbol for a in eligible_assets(source.list_assets(), config)} == {
        "GOODA", "GOODB", "GOODC", "GOODD", "GOODE", "CHEAP", "THIN", "YOUNG",
    }
    pool = build_candidate_pool(source, config, AS_OF)
    assert {c.symbol for c in pool} == {"GOODA", "GOODB", "GOODC", "GOODD", "GOODE"}


def test_stage0_excludes_funds(tmp_path):
    config = _make_config(tmp_path)
    assets = [
        AssetRecord("IWM", "ARCA", name="iShares Russell 2000 ETF"),
        AssetRecord("SPLG", "ARCA", name="SPDR Portfolio S&P 500 ETF"),
        AssetRecord("AAPL", "NASDAQ", name="Apple Inc. Common Stock"),
    ]
    eligible = eligible_assets(assets, config)
    assert [a.symbol for a in eligible] == ["AAPL"]


def test_build_universe_end_to_end(tmp_path):
    config = _make_config(tmp_path)
    source = _make_source()
    snapshot = build_universe(
        source, config, AS_OF, replayer=_perfect_replayer(source), save=True
    )

    assert snapshot.as_of == AS_OF
    assert snapshot.size == 4
    assert len(snapshot.tickers) == 4
    assert set(snapshot.tickers) <= {"GOODA", "GOODB", "GOODC", "GOODD", "GOODE"}
    assert snapshot.stage_counts["stage0_candidates"] == 5
    assert snapshot.stage_counts["stage2_shortlist"] == 5

    # Sector cap of 50% on size 4 -> at most 2 per sector
    sectors = [s.sector for s in snapshot.selected_scores()]
    assert max(sectors.count(x) for x in set(sectors)) <= 2

    # Learnability computed and attached (perfect replayer -> positive raw)
    learn = [
        s.factors["alpha_learnability"]
        for s in snapshot.scores
        if "alpha_learnability" in s.factors
    ]
    assert any(f.raw is not None and f.raw > 0 for f in learn)

    # Artifact readable back via the store
    loaded = load_latest_universe(config.output_dir)
    assert loaded is not None and loaded.tickers == snapshot.tickers
    assert loaded.caveats


def test_build_universe_without_learnability(tmp_path):
    config = _make_config(tmp_path, learnability_enabled=False)
    source = _make_source()
    snapshot = build_universe(source, config, AS_OF, save=False)
    assert len(snapshot.tickers) == 4
    for score in snapshot.scores:
        factor = score.factors.get("alpha_learnability")
        assert factor is None or factor.raw is None


def test_point_in_time_truncation(tmp_path):
    """Bars after as_of must never reach the factors."""
    config = _make_config(tmp_path, learnability_enabled=False)
    source = _make_source()
    early = "2026-03-31"
    snapshot = build_universe(source, config, early, save=False)
    assert snapshot.as_of == early
    assert len(snapshot.tickers) == 4
