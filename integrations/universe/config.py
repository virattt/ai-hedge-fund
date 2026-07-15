"""Universe selection configuration.

Every knob is env-overridable (``UNIVERSE_*``) so the daemon and CI can tune
the ranking without code changes. Factor weights are a plain name->weight
mapping — setting a weight to 0 removes the factor from the composite, and
new factors only need a registry entry plus a weight here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from integrations.alpaca.strategy import LIGHT_ANALYSTS

load_dotenv()

# Default weight per factor. Grouped by theme; relative magnitudes express
# how much each theme should drive the composite score.
DEFAULT_FACTOR_WEIGHTS: dict[str, float] = {
    # Liquidity / transaction cost
    "dollar_volume": 1.0,
    "amihud_illiquidity": 0.5,
    "estimated_spread": 0.75,
    "zero_volume_days": 0.25,
    # Tradable volatility
    "volatility_band": 1.0,
    "vol_stability": 0.5,
    # Statistical predictability
    "autocorrelation": 0.5,
    "variance_ratio": 0.5,
    "efficiency_ratio": 0.5,
    "stat_stability": 0.5,
    # Data quality
    "bar_coverage": 0.5,
    "listing_age": 0.25,
    "fundamentals_coverage": 0.5,
    "news_coverage": 0.25,
    # Event risk
    "tail_risk": 0.5,
    "max_gap": 0.5,
    "earnings_gap_risk": 0.5,
    "earnings_proximity": 0.5,
    # Crowding / shortability
    "volume_surge": 0.5,
    "momentum_extremeness": 0.25,
    "shortability": 0.5,
    # Alpha learnability — how well our own pipeline predicts this name
    "alpha_learnability": 2.0,
}


@dataclass(frozen=True)
class UniverseConfig:
    """All parameters of the universe build."""

    size: int = 127
    output_dir: str = "data/universe"
    cache_dir: str = "data/universe/cache"
    signal_cache_dir: str = "data/universe/signals"

    # Stage 0 — cheap eligibility filters
    min_price: float = 5.0
    min_history_days: int = 252
    min_median_dollar_volume: float = 5_000_000.0
    lookback_calendar_days: int = 750  # ~2 trading years of daily bars
    exchanges: tuple[str, ...] = ("NYSE", "NASDAQ", "AMEX", "ARCA", "BATS")
    # Exclude ETFs/ETNs/closed-end funds via asset-name markers at Stage 0.
    exclude_funds: bool = True
    # Hard-drop shortlist tickers with zero fundamentals filings. Funds and
    # trusts that slip past the name markers (e.g. "Invesco QQQ Trust") file
    # no financial statements, and names without fundamentals can't be
    # analyzed by most of the rule-based pipeline anyway.
    require_fundamentals: bool = True

    # Stage 2 shortlist size (learnability + fundamentals are computed on
    # these survivors only — this bounds the expensive API work)
    stage2_size: int = 300

    # Final diversified selection
    sector_cap_pct: float = 0.20
    max_correlation: float = 0.90
    correlation_window_days: int = 126

    # Alpha learnability replay. Only analysts whose inputs are point-in-time
    # at historical checkpoints belong here: the fundamentals-based analysts
    # (fundamentals/valuation/growth) pull *current* ratios from the provider,
    # which would leak today's data into historical replays — and cost tens of
    # thousands of rate-limited API calls per build.
    learnability_enabled: bool = True
    learnability_analysts: tuple[str, ...] = ("technical_analyst", "sentiment_analyst")
    learnability_checkpoint_days: int = 21  # trading days between checkpoints
    learnability_lookback_days: int = 504  # trading days of replay history
    learnability_horizons: tuple[int, ...] = (5, 21)

    # Volatility sweet-spot band (annualized)
    vol_band_low: float = 0.25
    vol_band_high: float = 0.60

    factor_weights: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_FACTOR_WEIGHTS)
    )


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not value or not value.strip():
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_weights(value: str | None) -> dict[str, float]:
    """Parse ``name:weight,name:weight`` overrides on top of the defaults."""
    weights = dict(DEFAULT_FACTOR_WEIGHTS)
    if not value or not value.strip():
        return weights
    for pair in value.split(","):
        if ":" not in pair:
            continue
        name, _, raw = pair.partition(":")
        try:
            weights[name.strip()] = float(raw)
        except ValueError:
            continue
    return weights


def load_universe_config() -> UniverseConfig:
    defaults = UniverseConfig()
    return UniverseConfig(
        size=int(os.getenv("UNIVERSE_SIZE", str(defaults.size))),
        output_dir=os.getenv("UNIVERSE_OUTPUT_DIR", defaults.output_dir),
        cache_dir=os.getenv("UNIVERSE_CACHE_DIR", defaults.cache_dir),
        signal_cache_dir=os.getenv("UNIVERSE_SIGNAL_CACHE_DIR", defaults.signal_cache_dir),
        min_price=float(os.getenv("UNIVERSE_MIN_PRICE", str(defaults.min_price))),
        min_history_days=int(os.getenv("UNIVERSE_MIN_HISTORY_DAYS", str(defaults.min_history_days))),
        min_median_dollar_volume=float(
            os.getenv("UNIVERSE_MIN_DOLLAR_VOLUME", str(defaults.min_median_dollar_volume))
        ),
        lookback_calendar_days=int(
            os.getenv("UNIVERSE_LOOKBACK_DAYS", str(defaults.lookback_calendar_days))
        ),
        exchanges=_parse_csv(os.getenv("UNIVERSE_EXCHANGES"), defaults.exchanges),
        exclude_funds=_parse_bool(os.getenv("UNIVERSE_EXCLUDE_FUNDS"), defaults.exclude_funds),
        require_fundamentals=_parse_bool(
            os.getenv("UNIVERSE_REQUIRE_FUNDAMENTALS"), defaults.require_fundamentals
        ),
        stage2_size=int(os.getenv("UNIVERSE_STAGE2_SIZE", str(defaults.stage2_size))),
        sector_cap_pct=float(os.getenv("UNIVERSE_SECTOR_CAP_PCT", str(defaults.sector_cap_pct))),
        max_correlation=float(os.getenv("UNIVERSE_MAX_CORRELATION", str(defaults.max_correlation))),
        correlation_window_days=int(
            os.getenv("UNIVERSE_CORRELATION_WINDOW", str(defaults.correlation_window_days))
        ),
        learnability_enabled=_parse_bool(
            os.getenv("UNIVERSE_LEARNABILITY"), defaults.learnability_enabled
        ),
        learnability_analysts=_parse_csv(
            os.getenv("UNIVERSE_LEARNABILITY_ANALYSTS"), defaults.learnability_analysts
        ),
        learnability_checkpoint_days=int(
            os.getenv("UNIVERSE_LEARNABILITY_CHECKPOINT_DAYS", str(defaults.learnability_checkpoint_days))
        ),
        learnability_lookback_days=int(
            os.getenv("UNIVERSE_LEARNABILITY_LOOKBACK_DAYS", str(defaults.learnability_lookback_days))
        ),
        vol_band_low=float(os.getenv("UNIVERSE_VOL_BAND_LOW", str(defaults.vol_band_low))),
        vol_band_high=float(os.getenv("UNIVERSE_VOL_BAND_HIGH", str(defaults.vol_band_high))),
        factor_weights=_parse_weights(os.getenv("UNIVERSE_FACTOR_WEIGHTS")),
    )
