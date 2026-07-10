"""Factor registry.

Stage 1 factors need only price bars and asset flags (cheap — computed for
every Stage-0 survivor). Stage 2 factors need per-ticker API data or signal
replay (computed for the shortlist only). To add a factor, append it to the
right list and give it a weight in ``UniverseConfig.factor_weights``; to
remove one, drop it here or set its weight to 0.
"""

from __future__ import annotations

from integrations.universe.factors.alpha_learnability import AlphaLearnabilityFactor
from integrations.universe.factors.base import Factor, FactorContext
from integrations.universe.factors.crowding import (
    MomentumExtremenessFactor,
    ShortabilityFactor,
    VolumeSurgeFactor,
)
from integrations.universe.factors.data_quality import (
    BarCoverageFactor,
    FundamentalsCoverageFactor,
    ListingAgeFactor,
    NewsCoverageFactor,
)
from integrations.universe.factors.event_risk import (
    EarningsGapRiskFactor,
    EarningsProximityFactor,
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
    EfficiencyRatioFactor,
    StatStabilityFactor,
    VarianceRatioFactor,
)
from integrations.universe.factors.volatility import VolatilityBandFactor, VolStabilityFactor

__all__ = ["Factor", "FactorContext", "stage1_factors", "stage2_factors", "all_factors"]


def stage1_factors() -> list[Factor]:
    """Price/flag-based factors, computed for every Stage-0 survivor."""
    return [
        DollarVolumeFactor(),
        AmihudIlliquidityFactor(),
        EstimatedSpreadFactor(),
        ZeroVolumeDaysFactor(),
        VolatilityBandFactor(),
        VolStabilityFactor(),
        AutocorrelationFactor(),
        VarianceRatioFactor(),
        EfficiencyRatioFactor(),
        StatStabilityFactor(),
        BarCoverageFactor(),
        ListingAgeFactor(),
        TailRiskFactor(),
        MaxGapFactor(),
        VolumeSurgeFactor(),
        MomentumExtremenessFactor(),
        ShortabilityFactor(),
    ]


def stage2_factors() -> list[Factor]:
    """Factors that need per-ticker API data or signal replay (shortlist only)."""
    return [
        FundamentalsCoverageFactor(),
        NewsCoverageFactor(),
        EarningsGapRiskFactor(),
        EarningsProximityFactor(),
        AlphaLearnabilityFactor(),
    ]


def all_factors() -> list[Factor]:
    return stage1_factors() + stage2_factors()
