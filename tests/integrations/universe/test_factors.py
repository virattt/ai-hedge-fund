"""Factor unit tests against synthetic series with known properties."""

from __future__ import annotations

import pandas as pd
import pytest

from integrations.universe.config import UniverseConfig
from integrations.universe.factors.crowding import (
    MomentumExtremenessFactor,
    ShortabilityFactor,
    VolumeSurgeFactor,
)
from integrations.universe.factors.data_quality import (
    BarCoverageFactor,
    FundamentalsCoverageFactor,
)
from integrations.universe.factors.event_risk import (
    EarningsGapRiskFactor,
    MaxGapFactor,
    TailRiskFactor,
)
from integrations.universe.factors.liquidity import (
    AmihudIlliquidityFactor,
    DollarVolumeFactor,
    EstimatedSpreadFactor,
    ZeroVolumeDaysFactor,
)
from integrations.universe.factors.predictability import (
    AutocorrelationFactor,
    VarianceRatioFactor,
)
from integrations.universe.factors.volatility import VolatilityBandFactor, VolStabilityFactor

from tests.integrations.universe.universe_fixtures import make_context, make_prices


# ---------------------------------------------------------------------------
# Liquidity
# ---------------------------------------------------------------------------

def test_dollar_volume_prefers_liquid_names():
    liquid = make_context("LIQ", make_prices(volume=10_000_000))
    thin = make_context("THIN", make_prices(volume=100_000))
    assert DollarVolumeFactor().compute(liquid) > DollarVolumeFactor().compute(thin)


def test_amihud_prefers_low_price_impact():
    # Same volatility, 100x the dollar volume -> lower price impact.
    deep = make_context("DEEP", make_prices(volume=50_000_000))
    shallow = make_context("SHAL", make_prices(volume=500_000))
    assert AmihudIlliquidityFactor().compute(deep) > AmihudIlliquidityFactor().compute(shallow)


def test_estimated_spread_prefers_tight_ranges():
    tight = make_context("TIGHT", make_prices(daily_vol=0.005))
    wide = make_context("WIDE", make_prices(daily_vol=0.06))
    assert EstimatedSpreadFactor().compute(tight) > EstimatedSpreadFactor().compute(wide)


def test_zero_volume_days_penalized():
    prices = make_prices()
    prices.iloc[-10:, prices.columns.get_loc("volume")] = 0.0
    gappy = make_context("GAP", prices)
    clean = make_context("CLEAN", make_prices())
    assert ZeroVolumeDaysFactor().compute(clean) > ZeroVolumeDaysFactor().compute(gappy)


# ---------------------------------------------------------------------------
# Volatility
# ---------------------------------------------------------------------------

def test_volatility_band_prefers_sweet_spot():
    config = UniverseConfig()
    # ~32% annualized sits inside the [25%, 60%] band
    in_band = make_context("MID", make_prices(daily_vol=0.02), config)
    sleepy = make_context("LOW", make_prices(daily_vol=0.003), config)
    wild = make_context("WILD", make_prices(daily_vol=0.08), config)

    factor = VolatilityBandFactor()
    assert factor.compute(in_band) == 0.0
    assert factor.compute(sleepy) < 0.0
    assert factor.compute(wild) < 0.0


def test_vol_stability_penalizes_regime_shifts():
    stable = make_context("STAB", make_prices(daily_vol=0.015))
    shifting = make_prices(daily_vol=0.01)
    # Double the volatility in the last third of the window
    third = len(shifting) // 3
    returns_scale = shifting["close"].pct_change().fillna(0)
    scaled = shifting["close"].iloc[-third - 1] * (1 + returns_scale.iloc[-third:] * 4).cumprod()
    shifting.iloc[-third:, shifting.columns.get_loc("close")] = scaled.values
    unstable = make_context("SHIFT", shifting)
    assert VolStabilityFactor().compute(stable) > VolStabilityFactor().compute(unstable)


# ---------------------------------------------------------------------------
# Predictability
# ---------------------------------------------------------------------------

def test_autocorrelation_detects_structure():
    trending = make_context("AR", make_prices(ar1=0.4, seed=3))
    random_walk = make_context("RW", make_prices(ar1=0.0, seed=3))
    assert AutocorrelationFactor().compute(trending) > AutocorrelationFactor().compute(random_walk)


def test_variance_ratio_detects_non_random_walk():
    mean_reverting = make_context("MR", make_prices(ar1=-0.4, seed=11))
    random_walk = make_context("RW", make_prices(ar1=0.0, seed=11))
    assert VarianceRatioFactor().compute(mean_reverting) > VarianceRatioFactor().compute(random_walk)


def test_predictability_returns_none_on_short_history():
    stub = make_context("SHORT", make_prices(n_days=30))
    assert AutocorrelationFactor().compute(stub) is None


# ---------------------------------------------------------------------------
# Event risk
# ---------------------------------------------------------------------------

def test_tail_risk_penalizes_fat_tails():
    prices = make_prices(seed=5)
    # Inject a few 15% crash days inside the factor's 252-day window
    for offset in (-40, -120, -200):
        prices.iloc[offset, prices.columns.get_loc("close")] *= 0.85
    jumpy = make_context("JUMP", prices)
    smooth = make_context("SMOOTH", make_prices(seed=5))
    assert TailRiskFactor().compute(smooth) > TailRiskFactor().compute(jumpy)


def test_max_gap_penalizes_overnight_gaps():
    prices = make_prices(seed=9)
    prices.iloc[-30, prices.columns.get_loc("open")] = (
        prices.iloc[-31, prices.columns.get_loc("close")] * 0.80
    )
    gapper = make_context("GAPPER", prices)
    smooth = make_context("SMOOTH", make_prices(seed=9))
    assert MaxGapFactor().compute(smooth) > MaxGapFactor().compute(gapper)


def test_earnings_gap_risk_uses_filing_dates():
    prices = make_prices(seed=13)
    filing_day = prices.index[-40]
    prices.loc[filing_day, "close"] = prices["close"].iloc[-41] * 1.20  # +20% reaction

    violent = make_context(
        "VIOL", prices, earnings_events=[{"filing_date": filing_day.strftime("%Y-%m-%d")}]
    )
    calm = make_context(
        "CALM",
        make_prices(seed=13),
        earnings_events=[{"filing_date": filing_day.strftime("%Y-%m-%d")}],
    )
    assert EarningsGapRiskFactor().compute(calm) > EarningsGapRiskFactor().compute(violent)


# ---------------------------------------------------------------------------
# Crowding / shortability
# ---------------------------------------------------------------------------

def test_volume_surge_penalized():
    surging = make_prices(seed=21)
    surging.iloc[-21:, surging.columns.get_loc("volume")] *= 8.0
    hot = make_context("HOT", surging)
    normal = make_context("NORM", make_prices(seed=21))
    assert VolumeSurgeFactor().compute(normal) > VolumeSurgeFactor().compute(hot)


def test_momentum_extremeness_penalizes_parabolic_moves():
    parabolic = make_context("PARA", make_prices(drift=0.008, seed=17))
    steady = make_context("STDY", make_prices(drift=0.0002, seed=17))
    assert (
        MomentumExtremenessFactor().compute(steady)
        > MomentumExtremenessFactor().compute(parabolic)
    )


def test_shortability_ladder():
    factor = ShortabilityFactor()
    etb = make_context("A", shortable=True, easy_to_borrow=True)
    htb = make_context("B", shortable=True, easy_to_borrow=False)
    none = make_context("C", shortable=False, easy_to_borrow=False)
    assert factor.compute(etb) > factor.compute(htb) > factor.compute(none)


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------

def test_bar_coverage_penalizes_missing_bars():
    full = make_context("FULL", make_prices())
    sparse_prices = make_prices().iloc[::2]  # every other day missing
    sparse = make_context("SPARSE", sparse_prices)
    assert BarCoverageFactor().compute(full) > BarCoverageFactor().compute(sparse)


def test_fundamentals_coverage_scores_populated_and_fresh():
    factor = FundamentalsCoverageFactor()
    rich = make_context(
        "RICH",
        fundamentals={
            "market_cap": 1e9,
            "price_to_earnings_ratio": 20.0,
            "price_to_book_ratio": 3.0,
            "return_on_equity": 0.2,
            "net_margin": 0.15,
            "operating_margin": 0.2,
            "revenue_growth": 0.1,
            "earnings_growth": 0.1,
            "debt_to_equity": 0.5,
            "current_ratio": 1.5,
            "free_cash_flow_per_share": 5.0,
            "earnings_per_share": 6.0,
            "filing_date": "2026-05-15",
        },
    )
    empty = make_context("EMPTY", fundamentals=None)
    assert factor.compute(rich) > factor.compute(empty)
    assert factor.compute(empty) == 0.0


@pytest.mark.parametrize(
    "factor_cls",
    [DollarVolumeFactor, EstimatedSpreadFactor, VolatilityBandFactor, TailRiskFactor],
)
def test_factors_handle_empty_prices(factor_cls):
    empty = make_context("EMPTY", pd.DataFrame(columns=["open", "high", "low", "close", "volume"]))
    assert factor_cls().compute(empty) is None
